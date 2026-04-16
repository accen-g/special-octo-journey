"""Rename all tables to BIC_CCD_ prefix convention.

Revision:   d4e5f6a7b8c9
Down rev:   c3d4e5f6a7b8
Created:    2026-04-16

What this migration does
========================
Renames every application table to the BIC_CCD_<TABLE_NAME> convention,
aligning with the enterprise naming standard across:
  - The 23 BIC Oracle tables (CCB_ prefix → BIC_CCD_)
  - Extra application tables (no/BIC_ prefix → BIC_CCD_)

For EXISTING databases this migration renames the physical tables.
For FRESH databases, Base.metadata.create_all() creates tables with the
new names directly (models already use BIC_CCD_*), so this migration is
effectively a no-op (renamed tables don't exist yet — the op is skipped
by the try/except guard).

Down-grade path
===============
Renames all tables back to their original names (in reverse order to
satisfy FK dependencies).
"""
from __future__ import annotations

import logging

from alembic import op

logger = logging.getLogger("alembic.bic_ccd_rename")

# (old_name, new_name) — ordered so dependent tables come after their parents
TABLE_RENAMES: list[tuple[str, str]] = [
    # ── BIC 23 tables (CCB_ → BIC_CCD_) ──────────────────────────────────────
    ("CCB_REGION",                         "BIC_CCD_REGION"),
    ("CCB_KRI_CATEGORY",                   "BIC_CCD_KRI_CATEGORY"),
    ("CCB_KRI_CONTROL",                    "BIC_CCD_KRI_CONTROL"),
    ("CCB_KRI_STATUS",                     "BIC_CCD_KRI_STATUS"),
    ("CCB_KRI_CONFIG",                     "BIC_CCD_KRI_CONFIG"),
    ("CCB_KRI_METRIC",                     "BIC_CCD_KRI_METRIC"),
    ("CCB_KRI_COMMENT",                    "BIC_CCD_KRI_COMMENT"),
    ("CCB_KRI_CONTROL_STATUS_TRACKER",     "BIC_CCD_KRI_CONTROL_STATUS_TRACKER"),
    ("CCB_KRI_CONTROL_EVIDENCE_AUDIT",     "BIC_CCD_KRI_CONTROL_EVIDENCE_AUDIT"),
    ("CCB_KRI_EVIDENCE",                   "BIC_CCD_KRI_EVIDENCE"),
    ("CCB_KRI_USER_ROLE",                  "BIC_CCD_KRI_USER_ROLE"),
    ("CCB_ROLE_REGION_MAPPING",            "BIC_CCD_ROLE_REGION_MAPPING"),
    ("CCB_KRI_DATA_SOURCE_MAPPING",        "BIC_CCD_KRI_DATA_SOURCE_MAPPING"),
    ("CCB_KRI_DATA_SOURCE_STATUS_TRACKER", "BIC_CCD_KRI_DATA_SOURCE_STATUS_TRACKER"),
    ("CCB_KRI_ASSIGNMENT_TRACKER",         "BIC_CCD_KRI_ASSIGNMENT_TRACKER"),
    ("CCB_KRI_ASSIGNMENT_AUDIT",           "BIC_CCD_KRI_ASSIGNMENT_AUDIT"),
    ("CCB_SCORECARD",                      "BIC_CCD_SCORECARD"),
    ("CCB_SCORECARD_APPROVER",             "BIC_CCD_SCORECARD_APPROVER"),
    ("CCB_SCORECARD_ACTIVITY_LOG",         "BIC_CCD_SCORECARD_ACTIVITY_LOG"),
    ("CCB_CASE",                           "BIC_CCD_CASE"),
    ("CCB_CASE_FILE",                      "BIC_CCD_CASE_FILE"),
    ("CCB_EMAIL_AUDIT",                    "BIC_CCD_EMAIL_AUDIT"),
    ("CCB_SHED_LOCK",                      "BIC_CCD_SHED_LOCK"),
    # ── Extra application tables ───────────────────────────────────────────────
    ("APP_USER",                           "BIC_CCD_APP_USER"),
    ("USER_ROLE_MAPPING",                  "BIC_CCD_USER_ROLE_MAPPING"),
    ("KRI_CONFIGURATION",                  "BIC_CCD_KRI_CONFIGURATION"),
    ("MAKER_CHECKER_SUBMISSION",           "BIC_CCD_MAKER_CHECKER_SUBMISSION"),
    ("APPROVAL_AUDIT_TRAIL",               "BIC_CCD_APPROVAL_AUDIT_TRAIL"),
    ("VARIANCE_SUBMISSION",                "BIC_CCD_VARIANCE_SUBMISSION"),
    ("ESCALATION_CONFIG",                  "BIC_CCD_ESCALATION_CONFIG"),
    ("NOTIFICATION",                       "BIC_CCD_NOTIFICATION"),
    ("APPROVAL_ASSIGNMENT_RULE",           "BIC_CCD_APPROVAL_ASSIGNMENT_RULE"),
    ("SAVED_VIEW",                         "BIC_CCD_SAVED_VIEW"),
    # ── KRI onboarding / audit evidence tables (BIC_KRI_ → BIC_CCD_KRI_) ─────
    ("BIC_KRI_BLUESHEET",                  "BIC_CCD_KRI_BLUESHEET"),
    ("BIC_KRI_APPROVAL_LOG",               "BIC_CCD_KRI_APPROVAL_LOG"),
    ("BIC_KRI_EVIDENCE_METADATA",          "BIC_CCD_KRI_EVIDENCE_METADATA"),
    ("BIC_KRI_EMAIL_ITERATION",            "BIC_CCD_KRI_EMAIL_ITERATION"),
    ("BIC_KRI_AUDIT_SUMMARY",              "BIC_CCD_KRI_AUDIT_SUMMARY"),
]


def _table_exists(conn, table_name: str) -> bool:
    """Return True if the physical table exists in the current DB."""
    from sqlalchemy import inspect
    return inspect(conn).has_table(table_name)


def upgrade() -> None:
    conn = op.get_bind()
    renamed = 0
    skipped = 0
    for old, new in TABLE_RENAMES:
        if _table_exists(conn, old):
            logger.info("Renaming %s → %s", old, new)
            op.rename_table(old, new)
            renamed += 1
        elif _table_exists(conn, new):
            logger.info("Table %s already renamed to %s — skipping", old, new)
            skipped += 1
        else:
            logger.info("Table %s not found (fresh install?) — skipping", old)
            skipped += 1
    logger.info("Rename upgrade complete: %d renamed, %d skipped.", renamed, skipped)


def downgrade() -> None:
    conn = op.get_bind()
    for old, new in reversed(TABLE_RENAMES):
        if _table_exists(conn, new):
            logger.info("Reverting %s → %s", new, old)
            op.rename_table(new, old)
        else:
            logger.info("Table %s not found — skipping downgrade for %s", new, old)
