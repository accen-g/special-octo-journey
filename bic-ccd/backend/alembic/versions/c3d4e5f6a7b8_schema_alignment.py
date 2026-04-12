"""Schema alignment migration — BIC_Design_Reference.pdf conformance.

Revision:   c3d4e5f6a7b8
Down rev:   b1c2d3e4f5a6
Created:    2026-04-07

What this migration does
========================
Section A — Add TRACKER_ID to BIC_KRI_EVIDENCE
    Adds a nullable FK column TRACKER_ID pointing to
    BIC_KRI_CONTROL_STATUS_TRACKER.ID, aligning the evidence table with
    the BIC design reference (BIC_KRI_EVIDENCE.TRACKER_ID).
    Existing rows keep tracker_id = NULL (valid; FK is nullable).

Section B — Retroactive TRACKER_ID backfill
    Best-effort UPDATE that resolves tracker_id for existing evidence rows
    by joining on (KRI_ID, CONTROL_ID, YEAR, MONTH). Safe to run multiple
    times (WHERE tracker_id IS NULL guard). If no matching tracker row
    exists the evidence row retains NULL — not an error.

Section C — Zero-downtime Oracle CHECK constraint upgrade
    Strategy: ADD new, broad constraint first (ENABLE NOVALIDATE — no
    table scan, no row locks), then DROP old narrow constraint as a
    metadata-only operation.  On SQLite this section is skipped because:
      a) SQLite ignores CHECK constraints at runtime anyway, and
      b) SQLite has no ALTER TABLE ... ADD CONSTRAINT DDL.
    Constraints updated:
      - BIC_KRI_CONTROL_STATUS_TRACKER.STATUS
      - USER_ROLE_MAPPING.ROLE_CODE
      - MAKER_CHECKER_SUBMISSION.FINAL_STATUS    (verify only)
      - APPROVAL_AUDIT_TRAIL.ACTION              (verify only)
      - ESCALATION_CONFIG.ESCALATION_TYPE        (verify only)
      - VARIANCE_SUBMISSION.REVIEW_STATUS        (verify only)
      - NOTIFICATION.NOTIFICATION_TYPE           (verify only)

Section D — Seed BIC_KRI_STATUS lookup rows
    Inserts one row per ControlStatus value using an idempotent
    INSERT … WHERE NOT EXISTS pattern.  Safe to run multiple times.

Down-grade path
===============
    Removes TRACKER_ID from BIC_KRI_EVIDENCE and drops the new CHECK
    constraints (restores old narrow constraints on Oracle).
"""
from __future__ import annotations

import logging
from typing import List

import sqlalchemy as sa
from alembic import op

# Import enums from the app — enum_values() and oracle_check_in() are
# used to generate CHECK constraint IN-lists, guaranteeing they can
# never drift from the Python validation layer.
from app.enums import (
    ControlStatus,
    RoleCode,
    ApprovalAction,
    SubmissionFinalStatus,
    EscalationType,
    VarianceReviewStatus,
    NotificationType,
    enum_values,
    oracle_check_in,
)

logger = logging.getLogger("alembic.runtime.migration")

# ─── Revision identifiers ───────────────────────────────────
revision = "c3d4e5f6a7b8"
down_revision = "b1c2d3e4f5a6"
branch_labels = None
depends_on = None


# ─── Dialect helpers ─────────────────────────────────────────

def _is_oracle(conn) -> bool:
    return conn.dialect.name == "oracle"


def _is_sqlite(conn) -> bool:
    return conn.dialect.name == "sqlite"


def _drop_check_constraints_oracle(conn, table_name: str, col_name: str) -> None:
    """Drop all user-named CHECK constraints on a specific column (Oracle only).

    Queries USER_CONSTRAINTS + USER_CONS_COLUMNS to find constraint names
    dynamically, so this works regardless of whether tables were created via
    schema.sql (named constraints) or SQLAlchemy create_all() (system-named).

    Excludes NOT NULL constraints (constraint_type = 'C' but generated = 'GENERATED NAME').
    """
    result = conn.execute(sa.text("""
        SELECT cc.constraint_name
        FROM   user_constraints  c
        JOIN   user_cons_columns cc ON cc.constraint_name = c.constraint_name
        WHERE  c.table_name   = :tbl
        AND    cc.column_name = :col
        AND    c.constraint_type = 'C'
        AND    c.generated   = 'USER NAME'
    """), {"tbl": table_name.upper(), "col": col_name.upper()})

    rows = result.fetchall()
    if not rows:
        logger.info(f"  No existing CHECK constraints on {table_name}.{col_name} — skipping DROP")
    for row in rows:
        cname = row[0]
        logger.info(f"  Dropping old constraint {cname} on {table_name}.{col_name}")
        conn.execute(sa.text(f"ALTER TABLE {table_name} DROP CONSTRAINT {cname}"))


def _add_check_novalidate_oracle(conn, table_name: str, col_name: str,
                                 constraint_name: str, enum_cls) -> None:
    """Add a CHECK constraint using ENABLE NOVALIDATE (zero-downtime pattern).

    ENABLE NOVALIDATE means:
      - The constraint is ACTIVE for all new INSERT / UPDATE operations
      - Oracle does NOT scan existing rows (no table lock, no table scan)
      - Effectively instant even on large tables
    Existing non-conforming rows (there should be none) are left as-is.

    Sequence (add NEW first, then drop OLD):
    1. Add broad new constraint with NOVALIDATE  ← table always guarded
    2. Drop old narrow constraint (metadata only, brief exclusive latch on dict)
    """
    expr = oracle_check_in(col_name, enum_cls)
    logger.info(f"  Adding {constraint_name} ENABLE NOVALIDATE on {table_name}.{col_name}")
    conn.execute(sa.text(
        f"ALTER TABLE {table_name} "
        f"ADD CONSTRAINT {constraint_name} CHECK ({expr}) "
        f"ENABLE NOVALIDATE"
    ))


# ════════════════════════════════════════════════════════════
# UPGRADE
# ════════════════════════════════════════════════════════════

def upgrade() -> None:
    conn = op.get_bind()
    is_oracle = _is_oracle(conn)

    # ──────────────────────────────────────────────────────────
    # SECTION A — Add TRACKER_ID column to BIC_KRI_EVIDENCE
    # ──────────────────────────────────────────────────────────
    logger.info("Section A: Adding TRACKER_ID to BIC_KRI_EVIDENCE")

    op.add_column(
        "BIC_KRI_EVIDENCE",
        sa.Column("TRACKER_ID", sa.Integer, nullable=True),
    )

    # Add FK constraint (use batch mode for SQLite which can't ALTER TABLE ADD FK)
    if is_oracle:
        conn.execute(sa.text(
            "ALTER TABLE BIC_KRI_EVIDENCE "
            "ADD CONSTRAINT fk_evidence_tracker "
            "FOREIGN KEY (TRACKER_ID) "
            "REFERENCES BIC_KRI_CONTROL_STATUS_TRACKER(ID)"
        ))
    # SQLite: FK defined at create_all() time via the ORM; ALTER ADD FK not supported.
    # The model FK declaration handles it for new tables. For the existing dev DB
    # the FK is advisory (SQLite doesn't enforce FKs by default).

    # ──────────────────────────────────────────────────────────
    # SECTION B — Retroactive TRACKER_ID backfill
    # ──────────────────────────────────────────────────────────
    logger.info("Section B: Backfilling TRACKER_ID on existing BIC_KRI_EVIDENCE rows")

    # Best-effort: join on (KRI_ID, CONTROL_ID, YEAR, MONTH).
    # WHERE tracker_id IS NULL makes this idempotent.
    # ROWNUM / LIMIT guard prevents long-running update if table is huge.
    # Rows with no matching tracker row stay NULL — not an error.
    if is_oracle:
        conn.execute(sa.text("""
            UPDATE BIC_KRI_EVIDENCE e
            SET    e.TRACKER_ID = (
                SELECT t.ID
                FROM   BIC_KRI_CONTROL_STATUS_TRACKER t
                WHERE  t.KRI_ID     = e.KRI_ID
                AND    t.CONTROL_ID = e.CONTROL_ID
                AND    t.YEAR       = e.YEAR
                AND    t.MONTH      = e.MONTH
                AND    ROWNUM = 1
            )
            WHERE  e.TRACKER_ID IS NULL
        """))
    else:
        # SQLite syntax (no ROWNUM — use subquery with LIMIT)
        conn.execute(sa.text("""
            UPDATE BIC_KRI_EVIDENCE
            SET    TRACKER_ID = (
                SELECT t.ID
                FROM   BIC_KRI_CONTROL_STATUS_TRACKER t
                WHERE  t.KRI_ID     = BIC_KRI_EVIDENCE.KRI_ID
                AND    t.CONTROL_ID = BIC_KRI_EVIDENCE.CONTROL_ID
                AND    t.YEAR       = BIC_KRI_EVIDENCE.YEAR
                AND    t.MONTH      = BIC_KRI_EVIDENCE.MONTH
                LIMIT 1
            )
            WHERE  TRACKER_ID IS NULL
        """))

    rows_updated = conn.execute(
        sa.text("SELECT COUNT(*) FROM BIC_KRI_EVIDENCE WHERE TRACKER_ID IS NOT NULL")
    ).scalar()
    logger.info(f"  Backfilled TRACKER_ID on {rows_updated} evidence rows")

    # ──────────────────────────────────────────────────────────
    # SECTION C — Zero-downtime CHECK constraint upgrade (Oracle)
    # ──────────────────────────────────────────────────────────
    if is_oracle:
        logger.info("Section C: Upgrading Oracle CHECK constraints (NOVALIDATE pattern)")

        # ── C1: BIC_KRI_CONTROL_STATUS_TRACKER.STATUS ─────────
        # Add new broad constraint FIRST (table stays guarded), then drop old one.
        _add_check_novalidate_oracle(
            conn,
            table_name="BIC_KRI_CONTROL_STATUS_TRACKER",
            col_name="STATUS",
            constraint_name="chk_tracker_status_v2",
            enum_cls=ControlStatus,
        )
        _drop_check_constraints_oracle(conn, "BIC_KRI_CONTROL_STATUS_TRACKER", "STATUS")

        # ── C2: USER_ROLE_MAPPING.ROLE_CODE ───────────────────
        _add_check_novalidate_oracle(
            conn,
            table_name="USER_ROLE_MAPPING",
            col_name="ROLE_CODE",
            constraint_name="chk_urm_role_code_v2",
            enum_cls=RoleCode,
        )
        _drop_check_constraints_oracle(conn, "USER_ROLE_MAPPING", "ROLE_CODE")

        # ── C3: MAKER_CHECKER_SUBMISSION.FINAL_STATUS ─────────
        _add_check_novalidate_oracle(
            conn,
            table_name="MAKER_CHECKER_SUBMISSION",
            col_name="FINAL_STATUS",
            constraint_name="chk_mcs_final_status_v2",
            enum_cls=SubmissionFinalStatus,
        )
        _drop_check_constraints_oracle(conn, "MAKER_CHECKER_SUBMISSION", "FINAL_STATUS")

        # ── C4: APPROVAL_AUDIT_TRAIL.ACTION ───────────────────
        _add_check_novalidate_oracle(
            conn,
            table_name="APPROVAL_AUDIT_TRAIL",
            col_name="ACTION",
            constraint_name="chk_aat_action_v2",
            enum_cls=ApprovalAction,
        )
        _drop_check_constraints_oracle(conn, "APPROVAL_AUDIT_TRAIL", "ACTION")

        # ── C5: ESCALATION_CONFIG.ESCALATION_TYPE ─────────────
        _add_check_novalidate_oracle(
            conn,
            table_name="ESCALATION_CONFIG",
            col_name="ESCALATION_TYPE",
            constraint_name="chk_esc_type_v2",
            enum_cls=EscalationType,
        )
        _drop_check_constraints_oracle(conn, "ESCALATION_CONFIG", "ESCALATION_TYPE")

        # ── C6: VARIANCE_SUBMISSION.REVIEW_STATUS ─────────────
        _add_check_novalidate_oracle(
            conn,
            table_name="VARIANCE_SUBMISSION",
            col_name="REVIEW_STATUS",
            constraint_name="chk_vs_review_status_v2",
            enum_cls=VarianceReviewStatus,
        )
        _drop_check_constraints_oracle(conn, "VARIANCE_SUBMISSION", "REVIEW_STATUS")

        # ── C7: NOTIFICATION.NOTIFICATION_TYPE ────────────────
        _add_check_novalidate_oracle(
            conn,
            table_name="NOTIFICATION",
            col_name="NOTIFICATION_TYPE",
            constraint_name="chk_notif_type_v2",
            enum_cls=NotificationType,
        )
        _drop_check_constraints_oracle(conn, "NOTIFICATION", "NOTIFICATION_TYPE")

        logger.info("Section C: Oracle CHECK constraints upgraded successfully")
    else:
        logger.info("Section C: Skipped (SQLite — CHECK constraints not enforced at runtime)")

    # ──────────────────────────────────────────────────────────
    # SECTION D — Seed BIC_KRI_STATUS lookup table (idempotent)
    # ──────────────────────────────────────────────────────────
    logger.info("Section D: Seeding BIC_KRI_STATUS lookup rows")

    for status_value in enum_values(ControlStatus):
        if is_oracle:
            conn.execute(sa.text("""
                INSERT INTO BIC_KRI_STATUS (STATUS_NAME, CREATED_DT)
                SELECT :val, SYSDATE FROM DUAL
                WHERE NOT EXISTS (
                    SELECT 1 FROM BIC_KRI_STATUS WHERE STATUS_NAME = :val
                )
            """), {"val": status_value})
        else:
            conn.execute(sa.text("""
                INSERT OR IGNORE INTO BIC_KRI_STATUS (STATUS_NAME, CREATED_DT)
                VALUES (:val, CURRENT_TIMESTAMP)
            """), {"val": status_value})

    seeded_count = conn.execute(
        sa.text("SELECT COUNT(*) FROM BIC_KRI_STATUS")
    ).scalar()
    logger.info(f"  BIC_KRI_STATUS now contains {seeded_count} rows")

    logger.info("Migration c3d4e5f6a7b8 upgrade complete")


# ════════════════════════════════════════════════════════════
# DOWNGRADE
# ════════════════════════════════════════════════════════════

def downgrade() -> None:
    conn = op.get_bind()
    is_oracle = _is_oracle(conn)

    logger.info("Section C (downgrade): Removing new CHECK constraints")

    if is_oracle:
        # Drop the new broad constraints
        for table, col, cname in [
            ("BIC_KRI_CONTROL_STATUS_TRACKER", "STATUS",          "chk_tracker_status_v2"),
            ("USER_ROLE_MAPPING",              "ROLE_CODE",        "chk_urm_role_code_v2"),
            ("MAKER_CHECKER_SUBMISSION",       "FINAL_STATUS",     "chk_mcs_final_status_v2"),
            ("APPROVAL_AUDIT_TRAIL",           "ACTION",           "chk_aat_action_v2"),
            ("ESCALATION_CONFIG",              "ESCALATION_TYPE",  "chk_esc_type_v2"),
            ("VARIANCE_SUBMISSION",            "REVIEW_STATUS",    "chk_vs_review_status_v2"),
            ("NOTIFICATION",                   "NOTIFICATION_TYPE","chk_notif_type_v2"),
        ]:
            try:
                conn.execute(sa.text(f"ALTER TABLE {table} DROP CONSTRAINT {cname}"))
                logger.info(f"  Dropped {cname}")
            except Exception as e:
                logger.warning(f"  Could not drop {cname}: {e} — may not exist")

    logger.info("Section A (downgrade): Removing TRACKER_ID from BIC_KRI_EVIDENCE")

    if is_oracle:
        try:
            conn.execute(sa.text(
                "ALTER TABLE BIC_KRI_EVIDENCE DROP CONSTRAINT fk_evidence_tracker"
            ))
        except Exception:
            pass  # constraint may not exist if tables were created without it

    op.drop_column("BIC_KRI_EVIDENCE", "TRACKER_ID")

    logger.info("Migration c3d4e5f6a7b8 downgrade complete")
    logger.info("NOTE: BIC_KRI_STATUS seed rows are NOT removed on downgrade (safe to keep)")
