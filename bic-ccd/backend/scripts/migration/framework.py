"""
Data migration framework for CCB_* → BIC_CCD_* cutover.

Usage pattern per wave:
    from scripts.migration.framework import MigrationRunner
    runner = MigrationRunner(engine)
    runner.validate_counts("CCB_KRI_REGION", "BIC_CCD_REGION")
    runner.run_insert_select("CCB_KRI_REGION", "BIC_CCD_REGION", column_map)
    runner.validate_counts("CCB_KRI_REGION", "BIC_CCD_REGION")  # post-check
    runner.rollback_table("BIC_CCD_REGION")
"""
from __future__ import annotations

import logging
import sys
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from sqlalchemy import Engine, text

log = logging.getLogger(__name__)

# ─── Phase 5: Cutover order ────────────────────────────────────────────────
# Waves ordered by FK dependency depth + reference count (lowest risk first).
# AppUser / ApprovalAuditTrail / MakerCheckerSubmission are shared tables —
# they are NOT CCB_* prefixed and are NOT migrated.

CUTOVER_WAVES: list[dict] = [
    {
        "wave": 1,
        "name": "Infrastructure",
        "tables": [
            ("CCB_SHED_LOCK", "BIC_CCD_SHED_LOCK"),
        ],
        "files_affected": ["app/scheduler.py"],
        "risk": "LOW — 2 queries, distributed-lock only",
    },
    {
        "wave": 2,
        "name": "Master / Lookup tables",
        "tables": [
            ("CCB_KRI_REGION",   "BIC_CCD_REGION"),
            ("CCB_KRI_CATEGORY", "BIC_CCD_KRI_CATEGORY"),
            ("CCB_KRI_CONTROL",  "BIC_CCD_KRI_CONTROL"),
            ("CCB_KRI_STATUS",   "BIC_CCD_KRI_STATUS"),
        ],
        "files_affected": [
            "app/repositories/__init__.py",
            "app/services/__init__.py",
            "app/utils/cache.py",
            "app/main.py",
        ],
        "risk": "MEDIUM — referenced by 10+ files but no inbound FK from BIC_CCD_ wave",
    },
    {
        "wave": 3,
        "name": "Config / Mapping tables",
        "tables": [
            ("CCB_KRI_CONFIG",              "BIC_CCD_KRI_CONFIG"),
            ("KRI_CONFIGURATION",           "BIC_CCD_KRI_CONFIGURATION"),
            ("CCB_KRI_DATA_SOURCE_MAPPING", "BIC_CCD_KRI_DATA_SOURCE_MAPPING"),
            ("CCB_ROLE_REGION_MAPPING",     "BIC_CCD_ROLE_REGION_MAPPING"),
            ("CCB_KRI_USER_ROLE",           "BIC_CCD_KRI_USER_ROLE"),
        ],
        "files_affected": [
            "app/repositories/__init__.py",
            "app/services/__init__.py",
            "app/services/verification.py",
            "app/routers/kri_onboarding.py",
            "app/routers/audit_evidence.py",
        ],
        "risk": "HIGH — KriMaster (KRI_CONFIG) has 30+ references; must migrate Wave 2 first",
    },
    {
        "wave": 4,
        "name": "Tracker / Status tables",
        "tables": [
            ("CCB_KRI_CONTROL_STATUS_TRACKER",     "BIC_CCD_KRI_CONTROL_STATUS_TRACKER"),
            ("CCB_KRI_DATA_SOURCE_STATUS_TRACKER", "BIC_CCD_KRI_DATA_SOURCE_STATUS_TRACKER"),
            ("CCB_KRI_ASSIGNMENT_TRACKER",         "BIC_CCD_KRI_ASSIGNMENT_TRACKER"),
        ],
        "files_affected": [
            "app/repositories/__init__.py",
            "app/services/verification.py",
            "app/services/email.py",
            "app/routers/__init__.py",
            "app/routers/scorecard.py",
        ],
        "risk": "HIGH — MonthlyControlStatus has 25+ references; core scheduler job writes here",
    },
    {
        "wave": 5,
        "name": "Activity / Evidence / Audit tables",
        "tables": [
            ("CCB_KRI_METRIC",                "BIC_CCD_KRI_METRIC"),
            ("CCB_KRI_EVIDENCE",              "BIC_CCD_KRI_EVIDENCE"),
            ("CCB_KRI_COMMENT",               "BIC_CCD_KRI_COMMENT"),
            ("CCB_KRI_ASSIGNMENT_AUDIT",      "BIC_CCD_KRI_ASSIGNMENT_AUDIT"),
            ("CCB_KRI_CONTROL_EVIDENCE_AUDIT","BIC_CCD_KRI_CONTROL_EVIDENCE_AUDIT"),
        ],
        "files_affected": [
            "app/routers/audit_evidence.py",
            "app/repositories/__init__.py",
        ],
        "risk": "MEDIUM — dependent on Wave 4 tracker PKs for FKs",
    },
    {
        "wave": 6,
        "name": "Scorecard & Case tables",
        "tables": [
            ("CCB_KRI_SCORECARD",          "BIC_CCD_SCORECARD"),
            ("CCB_KRI_SCORECARD_APPROVER", "BIC_CCD_SCORECARD_APPROVER"),
            ("CCB_KRI_SCORECARD_ACTIVITY_LOG","BIC_CCD_SCORECARD_ACTIVITY_LOG"),
            ("CCB_CASE",      "BIC_CCD_CASE"),
            ("CCB_CASE_FILE", "BIC_CCD_CASE_FILE"),
        ],
        "files_affected": ["app/routers/scorecard.py"],
        "risk": "MEDIUM — relatively isolated module",
    },
    {
        "wave": 7,
        "name": "Email / Audit trail",
        "tables": [
            ("CCB_EMAIL_AUDIT", "BIC_CCD_EMAIL_AUDIT"),
        ],
        "files_affected": ["app/services/email.py"],
        "risk": "LOW — audit-only table; write-after-action, no inbound FKs from app logic",
    },
]


# ─── Runner ───────────────────────────────────────────────────────────────────

@dataclass
class MigrationResult:
    src_table: str
    dst_table: str
    src_count: int = 0
    dst_count_before: int = 0
    dst_count_after: int = 0
    rows_inserted: int = 0
    success: bool = False
    errors: list[str] = field(default_factory=list)


class MigrationRunner:
    def __init__(self, engine: Engine, dry_run: bool = False):
        self.engine = engine
        self.dry_run = dry_run
        self.results: list[MigrationResult] = []

    # ── Validation ────────────────────────────────────────────────────────────

    def count(self, table: str) -> int:
        with self.engine.connect() as conn:
            row = conn.execute(text(f"SELECT COUNT(*) FROM {table}")).fetchone()
            return row[0] if row else 0

    def validate_counts(self, src: str, dst: str) -> tuple[int, int]:
        s, d = self.count(src), self.count(dst)
        match = "OK" if s == d else "MISMATCH"
        log.info("[%s] %s=%d  %s=%d", match, src, s, dst, d)
        return s, d

    def validate_pk_coverage(self, src: str, dst: str, pk_col: str) -> bool:
        """Check every PK in src exists in dst."""
        sql = f"""
            SELECT COUNT(*) FROM {src} s
            WHERE NOT EXISTS (
                SELECT 1 FROM {dst} d WHERE d.{pk_col} = s.{pk_col}
            )
        """
        with self.engine.connect() as conn:
            missing = conn.execute(text(sql)).scalar()
        if missing:
            log.error("[PK_COVERAGE] %d rows in %s missing from %s", missing, src, dst)
            return False
        log.info("[PK_COVERAGE] OK — all %s PKs present in %s", src, dst)
        return True

    # ── Insert-select ─────────────────────────────────────────────────────────

    def run_insert_select(
        self,
        src: str,
        dst: str,
        column_map: dict[str, str],
        where: Optional[str] = None,
        batch_size: int = 5000,
    ) -> MigrationResult:
        """
        Copy rows from src to dst using a column map.

        column_map: {dst_col: src_col}  e.g. {"REGION_ID": "REGION_ID", "REGION_CODE": "REGION_CODE"}
        where:      optional SQL fragment appended as WHERE clause (Oracle syntax)
        batch_size: rows per commit (Oracle bulk insert)

        NOTE: column_map bodies are TODO until old schemas are provided.
        """
        result = MigrationResult(src_table=src, dst_table=dst)
        result.src_count = self.count(src)
        result.dst_count_before = self.count(dst)

        dst_cols = ", ".join(column_map.keys())
        src_cols = ", ".join(column_map.values())
        where_clause = f"WHERE {where}" if where else ""

        sql = f"""
            INSERT INTO {dst} ({dst_cols})
            SELECT {src_cols}
            FROM   {src}
            {where_clause}
        """

        if self.dry_run:
            log.info("[DRY-RUN] Would execute:\n%s", sql.strip())
            result.success = True
            return result

        try:
            with self.engine.begin() as conn:
                conn.execute(text(sql))
            result.dst_count_after = self.count(dst)
            result.rows_inserted = result.dst_count_after - result.dst_count_before
            result.success = result.rows_inserted == result.src_count
            if not result.success:
                result.errors.append(
                    f"Expected {result.src_count} rows, got {result.rows_inserted}"
                )
        except Exception as exc:
            result.errors.append(str(exc))
            log.exception("Insert-select failed for %s → %s", src, dst)

        self.results.append(result)
        return result

    # ── Rollback ──────────────────────────────────────────────────────────────

    def rollback_table(self, dst: str, confirm: bool = False) -> None:
        """DELETE all rows from dst table. Requires explicit confirm=True."""
        if not confirm:
            raise RuntimeError(
                f"rollback_table({dst!r}) called without confirm=True — aborting"
            )
        if self.dry_run:
            log.info("[DRY-RUN] Would DELETE FROM %s", dst)
            return
        with self.engine.begin() as conn:
            conn.execute(text(f"DELETE FROM {dst}"))
        log.warning("[ROLLBACK] Deleted all rows from %s", dst)

    # ── Summary ───────────────────────────────────────────────────────────────

    def print_summary(self) -> None:
        print("\n── Migration Summary ─────────────────────────────────────")
        for r in self.results:
            status = "OK" if r.success else "FAIL"
            print(
                f"  [{status}] {r.src_table} → {r.dst_table}  "
                f"src={r.src_count}  inserted={r.rows_inserted}"
            )
            for e in r.errors:
                print(f"         ERROR: {e}")
        print("─────────────────────────────────────────────────────────\n")
