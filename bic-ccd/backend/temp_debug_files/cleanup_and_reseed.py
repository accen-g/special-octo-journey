"""
Oracle cleanup + seed reset script.
Writes full output to cleanup_result.txt
"""
import sys
import traceback
from sqlalchemy import create_engine, text
from app.config import get_settings

settings = get_settings()
engine = create_engine(settings.database_url)

lines = []

CLEANUP_STEPS = [
    "DELETE FROM APPROVAL_AUDIT_TRAIL WHERE STATUS_ID NOT IN (SELECT ID FROM BIC_KRI_CONTROL_STATUS_TRACKER)",
    "DELETE FROM MAKER_CHECKER_SUBMISSION WHERE STATUS_ID NOT IN (SELECT ID FROM BIC_KRI_CONTROL_STATUS_TRACKER)",
    "DELETE FROM USER_ROLE_MAPPING WHERE REGION_ID NOT IN (SELECT REGION_ID FROM BIC_REGION)",
    "DELETE FROM KRI_CONFIGURATION WHERE KRI_ID NOT IN (SELECT KRI_ID FROM BIC_KRI_CONFIG)",
]

lines.append("=== BEFORE CLEANUP ===")
with engine.connect() as conn:
    for tbl in ["BIC_REGION", "APP_USER", "USER_ROLE_MAPPING", "BIC_KRI_CONFIG",
                "KRI_CONFIGURATION", "MAKER_CHECKER_SUBMISSION", "APPROVAL_AUDIT_TRAIL",
                "BIC_KRI_CONTROL_STATUS_TRACKER"]:
        try:
            cnt = conn.execute(text(f'SELECT COUNT(*) FROM {tbl}')).scalar()
            lines.append(f"  {tbl}: {cnt}")
        except Exception as e:
            lines.append(f"  {tbl}: ERROR - {e}")

lines.append("\n=== RUNNING CLEANUP ===")
with engine.begin() as conn:
    for sql in CLEANUP_STEPS:
        try:
            result = conn.execute(text(sql))
            lines.append(f"  OK ({result.rowcount} rows): {sql[:80]}")
        except Exception as e:
            lines.append(f"  SKIP/ERR: {e}")

lines.append("\n=== AFTER CLEANUP ===")
with engine.connect() as conn:
    for tbl in ["BIC_REGION", "APP_USER", "USER_ROLE_MAPPING", "KRI_CONFIGURATION",
                "BIC_KRI_CONTROL_STATUS_TRACKER"]:
        try:
            cnt = conn.execute(text(f'SELECT COUNT(*) FROM {tbl}')).scalar()
            lines.append(f"  {tbl}: {cnt}")
        except Exception as e:
            lines.append(f"  {tbl}: ERROR - {e}")

lines.append("\n=== RUNNING SEED ===")
try:
    from app.main import seed_database
    seed_database()
    lines.append("SUCCESS: Seed completed!")
except Exception as e:
    lines.append("SEED FAILED:")
    lines.append("".join(traceback.format_exception(type(e), e, e.__traceback__)))

output = "\n".join(lines)
with open("cleanup_result.txt", "w", encoding="utf-8") as f:
    f.write(output)
print("Done. Results in cleanup_result.txt")
