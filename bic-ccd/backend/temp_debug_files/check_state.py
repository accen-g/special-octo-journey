from sqlalchemy import create_engine, text
from app.config import get_settings

settings = get_settings()
engine = create_engine(settings.database_url)

out = []
# Check what REGION_MASTER looks like
with engine.connect() as conn:
    out.append("=== REGION_MASTER columns ===")
    rs = conn.execute(text(
        "SELECT column_name, data_type, nullable "
        "FROM all_tab_columns WHERE table_name = 'REGION_MASTER' "
        "ORDER BY column_id"
    ))
    for row in rs:
        out.append(f"  {row[0]} ({row[1]}, nullable={row[2]})")

    out.append("\n=== REGION_MASTER rows ===")
    rs2 = conn.execute(text("SELECT * FROM REGION_MASTER"))
    for row in rs2:
        out.append("  " + str(row))

    out.append("\n=== BIC_REGION columns ===")
    rs3 = conn.execute(text(
        "SELECT column_name, data_type, nullable "
        "FROM all_tab_columns WHERE table_name = 'BIC_REGION' "
        "ORDER BY column_id"
    ))
    for row in rs3:
        out.append(f"  {row[0]} ({row[1]}, nullable={row[2]})")

with open('table_diff.txt', 'w') as f:
    f.write('\n'.join(out))
print("Done. Look at table_diff.txt")
