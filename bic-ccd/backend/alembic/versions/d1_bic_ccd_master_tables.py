"""d1 — BIC_CCD_* master tables (all 38, create-if-not-exists)

Revision ID: d1bic_ccd_0001
Revises:
Create Date: 2026-04-27

Tracked by ALEMBIC_VERSION_BIC_CCD (separate from legacy alembic_version).

Run with:
  ALEMBIC_TARGET=bic_ccd alembic upgrade head

Rollback with:
  ALEMBIC_TARGET=bic_ccd alembic downgrade base

Creates all 38 BIC_CCD_* tables (24 original + 14 app-owned Option A tables).
Each table is skipped if it already exists in the schema — safe to re-run.
No CCB_* tables are touched.  No data is moved.
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect as sa_inspect


revision: str = "d1bic_ccd_0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(table_name: str) -> bool:
    bind = op.get_bind()
    existing = {t.upper() for t in sa_inspect(bind).get_table_names()}
    return table_name.upper() in existing


def _constraint_exists(constraint_name: str, table_name: str) -> bool:
    bind = op.get_bind()
    try:
        result = bind.execute(
            sa.text(
                "SELECT COUNT(*) FROM user_constraints "
                "WHERE constraint_name = :c AND table_name = :t"
            ),
            {"c": constraint_name.upper(), "t": table_name.upper()},
        )
        return result.scalar() > 0
    except Exception:
        return False


def upgrade() -> None:

    # ── Tier 0: no FK dependencies ───────────────────────────────────────────

    if not _table_exists("BIC_CCD_REGION"):
        op.create_table(
            "BIC_CCD_REGION",
            sa.Column("REGION_ID", sa.Integer(), sa.Identity(start=1), nullable=False),
            sa.Column("REGION_NAME", sa.String(200), nullable=False),
            sa.Column("CTRL_LEAD", sa.String(200), nullable=True),
            sa.Column("GOV_TEAM", sa.String(200), nullable=True),
            sa.Column("REGION_CODE", sa.String(10), nullable=True),
            sa.Column("IS_ACTIVE", sa.Boolean(), nullable=False),
            sa.Column("CREATED_DT", sa.DateTime(), nullable=False),
            sa.Column("UPDATED_DT", sa.DateTime(), nullable=False),
            sa.Column("CREATED_BY", sa.String(50), nullable=False),
            sa.Column("UPDATED_BY", sa.String(50), nullable=False),
            sa.PrimaryKeyConstraint("REGION_ID", name="pk_BIC_CCD_REGION"),
            sa.UniqueConstraint("REGION_CODE", name="uq_BIC_CCD_REGION_REGION_CODE"),
        )

    if not _table_exists("BIC_CCD_KRI_CATEGORY"):
        op.create_table(
            "BIC_CCD_KRI_CATEGORY",
            sa.Column("CATEGORY_ID", sa.Integer(), sa.Identity(start=1), nullable=False),
            sa.Column("CATEGORY_NAME", sa.String(200), nullable=False),
            sa.Column("CATEGORY_CODE", sa.String(30), nullable=True),
            sa.Column("DESCRIPTION", sa.String(500), nullable=True),
            sa.Column("IS_ACTIVE", sa.Boolean(), nullable=False),
            sa.Column("CREATED_DT", sa.DateTime(), nullable=False),
            sa.Column("UPDATED_DT", sa.DateTime(), nullable=False),
            sa.Column("CREATED_BY", sa.String(50), nullable=False),
            sa.Column("UPDATED_BY", sa.String(50), nullable=False),
            sa.PrimaryKeyConstraint("CATEGORY_ID", name="pk_BIC_CCD_KRI_CATEGORY"),
            sa.UniqueConstraint("CATEGORY_CODE", name="uq_BIC_CCD_KRI_CATEGORY_CATEGORY_CODE"),
        )

    if not _table_exists("BIC_CCD_KRI_CONTROL"):
        op.create_table(
            "BIC_CCD_KRI_CONTROL",
            sa.Column("CONTROL_ID", sa.Integer(), sa.Identity(start=1), nullable=False),
            sa.Column("CONTROL_NAME", sa.String(200), nullable=False),
            sa.Column("FREEZE_BUSINESS_DAYS", sa.Integer(), nullable=True),
            sa.Column("DIMENSION_CODE", sa.String(30), nullable=True),
            sa.Column("DISPLAY_ORDER", sa.Integer(), nullable=False),
            sa.Column("DESCRIPTION", sa.String(500), nullable=True),
            sa.Column("IS_ACTIVE", sa.Boolean(), nullable=False),
            sa.Column("CREATED_DT", sa.DateTime(), nullable=False),
            sa.Column("UPDATED_DT", sa.DateTime(), nullable=False),
            sa.Column("CREATED_BY", sa.String(50), nullable=False),
            sa.Column("UPDATED_BY", sa.String(50), nullable=False),
            sa.PrimaryKeyConstraint("CONTROL_ID", name="pk_BIC_CCD_KRI_CONTROL"),
            sa.UniqueConstraint("DIMENSION_CODE", name="uq_BIC_CCD_KRI_CONTROL_DIMENSION_CODE"),
        )

    if not _table_exists("BIC_CCD_KRI_STATUS"):
        op.create_table(
            "BIC_CCD_KRI_STATUS",
            sa.Column("STATUS_ID", sa.Integer(), sa.Identity(start=1), nullable=False),
            sa.Column("STATUS_NAME", sa.String(50), nullable=False),
            sa.Column("CREATED_DT", sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint("STATUS_ID", name="pk_BIC_CCD_KRI_STATUS"),
            sa.UniqueConstraint("STATUS_NAME", name="uq_BIC_CCD_KRI_STATUS_STATUS_NAME"),
        )

    if not _table_exists("BIC_CCD_ROLE_REGION_MAPPING"):
        op.create_table(
            "BIC_CCD_ROLE_REGION_MAPPING",
            sa.Column("ID", sa.Integer(), sa.Identity(start=1), nullable=False),
            sa.Column("ROLE", sa.String(100), nullable=False),
            sa.Column("REGION", sa.String(50), nullable=False),
            sa.Column("CREATED_DT", sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint("ID", name="pk_BIC_CCD_ROLE_REGION_MAPPING"),
            sa.UniqueConstraint("ROLE", "REGION", name="uq_bic_ccd_role_region"),
        )

    if not _table_exists("BIC_CCD_SHED_LOCK"):
        op.create_table(
            "BIC_CCD_SHED_LOCK",
            sa.Column("NAME", sa.String(100), nullable=False),
            sa.Column("LOCK_UNTIL", sa.DateTime(), nullable=False),
            sa.Column("LOCKED_AT", sa.DateTime(), nullable=False),
            sa.Column("LOCKED_BY", sa.String(100), nullable=False),
            sa.Column("IS_LOCKED", sa.Boolean(), nullable=False),
            sa.PrimaryKeyConstraint("NAME", name="pk_BIC_CCD_SHED_LOCK"),
        )

    if not _table_exists("BIC_CCD_CASE"):
        op.create_table(
            "BIC_CCD_CASE",
            sa.Column("TRANSACTION_ID", sa.Integer(), sa.Identity(start=1), nullable=False),
            sa.Column("CASE_ID", sa.String(50), nullable=True),
            sa.Column("CASE_STATUS", sa.String(20), nullable=False),
            sa.Column("IS_ACTIVE", sa.Boolean(), nullable=False),
            sa.Column("CREATED_DT", sa.DateTime(), nullable=False),
            sa.Column("UPDATED_DT", sa.DateTime(), nullable=False),
            sa.Column("CREATED_BY", sa.String(50), nullable=False),
            sa.Column("UPDATED_BY", sa.String(50), nullable=False),
            sa.PrimaryKeyConstraint("TRANSACTION_ID", name="pk_BIC_CCD_CASE"),
        )

    if not _table_exists("BIC_CCD_APP_USER"):
        op.create_table(
            "BIC_CCD_APP_USER",
            sa.Column("USER_ID", sa.Integer(), sa.Identity(start=1), nullable=False),
            sa.Column("SOE_ID", sa.String(20), nullable=False),
            sa.Column("FULL_NAME", sa.String(200), nullable=False),
            sa.Column("EMAIL", sa.String(200), nullable=False),
            sa.Column("DEPARTMENT", sa.String(100), nullable=True),
            sa.Column("IS_ACTIVE", sa.Boolean(), nullable=False),
            sa.Column("LAST_LOGIN_DT", sa.DateTime(), nullable=True),
            sa.Column("CREATED_DT", sa.DateTime(), nullable=False),
            sa.Column("UPDATED_DT", sa.DateTime(), nullable=False),
            sa.Column("CREATED_BY", sa.String(50), nullable=False),
            sa.Column("UPDATED_BY", sa.String(50), nullable=False),
            sa.PrimaryKeyConstraint("USER_ID", name="pk_BIC_CCD_APP_USER"),
            sa.UniqueConstraint("SOE_ID", name="uq_BIC_CCD_APP_USER_SOE_ID"),
        )

    # ── EMAIL_AUDIT created early; FKs to KRI_CONFIG / STATUS_TRACKER added later ─

    if not _table_exists("BIC_CCD_EMAIL_AUDIT"):
        op.create_table(
            "BIC_CCD_EMAIL_AUDIT",
            sa.Column("ID", sa.Integer(), sa.Identity(start=1), nullable=False),
            sa.Column("EMAIL_TO", sa.String(500), nullable=False),
            sa.Column("EMAIL_CC", sa.String(500), nullable=True),
            sa.Column("SUBJECT", sa.String(500), nullable=False),
            sa.Column("TEMPLATE_NAME", sa.String(100), nullable=True),
            sa.Column("STATUS", sa.String(20), nullable=False),
            sa.Column("EMAIL_BODY", sa.Text(), nullable=True),
            sa.Column("ERROR_MESSAGE", sa.String(1000), nullable=True),
            sa.Column("UUID", sa.String(100), nullable=True),
            sa.Column("CREATED_DT", sa.DateTime(), nullable=False),
            sa.Column("RECIPIENT_NAME", sa.String(200), nullable=True),
            sa.Column("SENT_DT", sa.DateTime(), nullable=True),
            sa.Column("RELATED_KRI_ID", sa.Integer(), nullable=True),
            sa.Column("RELATED_STATUS_ID", sa.Integer(), nullable=True),
            sa.PrimaryKeyConstraint("ID", name="pk_BIC_CCD_EMAIL_AUDIT"),
        )

    # ── Tier 1: depend on Tier 0 ─────────────────────────────────────────────

    if not _table_exists("BIC_CCD_KRI_CONFIG"):
        op.create_table(
            "BIC_CCD_KRI_CONFIG",
            sa.Column("KRI_ID", sa.Integer(), sa.Identity(start=1), nullable=False),
            sa.Column("KRI_NAME", sa.String(300), nullable=False),
            sa.Column("KRI_TITLE", sa.String(300), nullable=True),
            sa.Column("SCORECARD_NAME", sa.String(200), nullable=True),
            sa.Column("REGION_ID", sa.Integer(), nullable=False),
            sa.Column("CATEGORY_ID", sa.Integer(), nullable=False),
            sa.Column("LEGAL_ENTITIES", sa.Text(), nullable=True),
            sa.Column("FREQUENCY", sa.String(50), nullable=True),
            sa.Column("DATA_SOURCES", sa.Text(), nullable=True),
            sa.Column("SLA_CHECK", sa.Boolean(), nullable=True),
            sa.Column("SLA_START", sa.Integer(), nullable=True),
            sa.Column("SLA_END", sa.Integer(), nullable=True),
            sa.Column("REMINDER_DATE", sa.Integer(), nullable=True),
            sa.Column("ESCALATION_DATE", sa.Integer(), nullable=True),
            sa.Column("ACCURACY_CHECK", sa.Boolean(), nullable=True),
            sa.Column("COMPLETENESS_CHECK", sa.Boolean(), nullable=True),
            sa.Column("EVIDENCE_FOLDER", sa.String(500), nullable=True),
            sa.Column("RAG_THRESHOLD", sa.Text(), nullable=True),
            sa.Column("METRIC_VALUE_TYPE", sa.String(50), nullable=True),
            sa.Column("DECIMAL_PLACE", sa.Integer(), nullable=True),
            sa.Column("IS_ACTIVE", sa.Boolean(), nullable=False),
            sa.Column("KRI_CODE", sa.String(30), nullable=True),
            sa.Column("DESCRIPTION", sa.Text(), nullable=True),
            sa.Column("RISK_LEVEL", sa.String(20), nullable=False),
            sa.Column("FRAMEWORK", sa.String(100), nullable=True),
            sa.Column("IS_DCRM", sa.Boolean(), nullable=False, server_default="0"),
            sa.Column("ONBOARDED_DT", sa.DateTime(), nullable=True),
            sa.Column("CREATED_DT", sa.DateTime(), nullable=False),
            sa.Column("UPDATED_DT", sa.DateTime(), nullable=False),
            sa.Column("CREATED_BY", sa.String(50), nullable=False),
            sa.Column("UPDATED_BY", sa.String(50), nullable=False),
            sa.ForeignKeyConstraint(
                ["REGION_ID"], ["BIC_CCD_REGION.REGION_ID"],
                name="fk_BIC_CCD_KRI_CONFIG_REGION_ID_BIC_CCD_REGION",
            ),
            sa.ForeignKeyConstraint(
                ["CATEGORY_ID"], ["BIC_CCD_KRI_CATEGORY.CATEGORY_ID"],
                name="fk_BIC_CCD_KRI_CONFIG_CATEGORY_ID_BIC_CCD_KRI_CATEGORY",
            ),
            sa.PrimaryKeyConstraint("KRI_ID", name="pk_BIC_CCD_KRI_CONFIG"),
            sa.UniqueConstraint("KRI_CODE", name="uq_BIC_CCD_KRI_CONFIG_KRI_CODE"),
        )

    if not _table_exists("BIC_CCD_CASE_FILE"):
        op.create_table(
            "BIC_CCD_CASE_FILE",
            sa.Column("FILE_ID", sa.Integer(), sa.Identity(start=1), nullable=False),
            sa.Column("CASE_ID", sa.Integer(), nullable=True),
            sa.Column("REVIEW_STATUS", sa.String(20), nullable=True),
            sa.Column("FILE_UPLOAD_ID", sa.String(100), nullable=True),
            sa.Column("FILE_PATH", sa.String(500), nullable=False),
            sa.Column("FILE_SIZE", sa.Integer(), nullable=True),
            sa.Column("FILE_NAME", sa.String(500), nullable=True),
            sa.Column("CREATED_BY", sa.String(50), nullable=False),
            sa.Column("CREATED_DT", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(
                ["CASE_ID"], ["BIC_CCD_CASE.TRANSACTION_ID"],
                name="fk_BIC_CCD_CASE_FILE_CASE_ID_BIC_CCD_CASE",
            ),
            sa.PrimaryKeyConstraint("FILE_ID", name="pk_BIC_CCD_CASE_FILE"),
        )

    if not _table_exists("BIC_CCD_USER_ROLE_MAPPING"):
        op.create_table(
            "BIC_CCD_USER_ROLE_MAPPING",
            sa.Column("MAPPING_ID", sa.Integer(), sa.Identity(start=1), nullable=False),
            sa.Column("USER_ID", sa.Integer(), nullable=False),
            sa.Column("ROLE_CODE", sa.String(30), nullable=False),
            sa.Column("REGION_ID", sa.Integer(), nullable=True),
            sa.Column("IS_ACTIVE", sa.Boolean(), nullable=False),
            sa.Column("EFFECTIVE_FROM", sa.Date(), nullable=False),
            sa.Column("EFFECTIVE_TO", sa.Date(), nullable=True),
            sa.Column("CREATED_DT", sa.DateTime(), nullable=False),
            sa.Column("UPDATED_DT", sa.DateTime(), nullable=False),
            sa.Column("CREATED_BY", sa.String(50), nullable=False),
            sa.Column("UPDATED_BY", sa.String(50), nullable=False),
            sa.ForeignKeyConstraint(
                ["USER_ID"], ["BIC_CCD_APP_USER.USER_ID"],
                name="fk_BIC_CCD_USER_ROLE_MAPPING_USER_ID_BIC_CCD_APP_USER",
            ),
            sa.ForeignKeyConstraint(
                ["REGION_ID"], ["BIC_CCD_REGION.REGION_ID"],
                name="fk_BIC_CCD_USER_ROLE_MAPPING_REGION_ID_BIC_CCD_REGION",
            ),
            sa.PrimaryKeyConstraint("MAPPING_ID", name="pk_BIC_CCD_USER_ROLE_MAPPING"),
            sa.UniqueConstraint(
                "USER_ID", "ROLE_CODE", "REGION_ID",
                name="uq_bic_ccd_user_role_region",
            ),
        )

    if not _table_exists("BIC_CCD_ESCALATION_CONFIG"):
        op.create_table(
            "BIC_CCD_ESCALATION_CONFIG",
            sa.Column("CONFIG_ID", sa.Integer(), sa.Identity(start=1), nullable=False),
            sa.Column("REGION_ID", sa.Integer(), nullable=True),
            sa.Column("ESCALATION_TYPE", sa.String(30), nullable=False),
            sa.Column("THRESHOLD_HOURS", sa.Integer(), nullable=False),
            sa.Column("REMINDER_HOURS", sa.Integer(), nullable=False),
            sa.Column("MAX_REMINDERS", sa.Integer(), nullable=False),
            sa.Column("ESCALATE_TO_ROLE", sa.String(30), nullable=False),
            sa.Column("EMAIL_TEMPLATE", sa.Text(), nullable=True),
            sa.Column("IS_ACTIVE", sa.Boolean(), nullable=False),
            sa.Column("CREATED_DT", sa.DateTime(), nullable=False),
            sa.Column("UPDATED_DT", sa.DateTime(), nullable=False),
            sa.Column("CREATED_BY", sa.String(50), nullable=False),
            sa.Column("UPDATED_BY", sa.String(50), nullable=False),
            sa.ForeignKeyConstraint(
                ["REGION_ID"], ["BIC_CCD_REGION.REGION_ID"],
                name="fk_BIC_CCD_ESCALATION_CONFIG_REGION_ID_BIC_CCD_REGION",
            ),
            sa.PrimaryKeyConstraint("CONFIG_ID", name="pk_BIC_CCD_ESCALATION_CONFIG"),
        )

    if not _table_exists("BIC_CCD_NOTIFICATION"):
        op.create_table(
            "BIC_CCD_NOTIFICATION",
            sa.Column("NOTIFICATION_ID", sa.Integer(), sa.Identity(start=1), nullable=False),
            sa.Column("USER_ID", sa.Integer(), nullable=False),
            sa.Column("TITLE", sa.String(300), nullable=False),
            sa.Column("MESSAGE", sa.String(2000), nullable=False),
            sa.Column("NOTIFICATION_TYPE", sa.String(30), nullable=True),
            sa.Column("IS_READ", sa.Boolean(), nullable=False),
            sa.Column("LINK_URL", sa.String(500), nullable=True),
            sa.Column("CREATED_DT", sa.DateTime(), nullable=False),
            sa.Column("UPDATED_DT", sa.DateTime(), nullable=False),
            sa.Column("CREATED_BY", sa.String(50), nullable=False),
            sa.Column("UPDATED_BY", sa.String(50), nullable=False),
            sa.ForeignKeyConstraint(
                ["USER_ID"], ["BIC_CCD_APP_USER.USER_ID"],
                name="fk_BIC_CCD_NOTIFICATION_USER_ID_BIC_CCD_APP_USER",
            ),
            sa.PrimaryKeyConstraint("NOTIFICATION_ID", name="pk_BIC_CCD_NOTIFICATION"),
        )

    if not _table_exists("BIC_CCD_SAVED_VIEW"):
        op.create_table(
            "BIC_CCD_SAVED_VIEW",
            sa.Column("VIEW_ID", sa.Integer(), sa.Identity(start=1), nullable=False),
            sa.Column("USER_ID", sa.Integer(), nullable=False),
            sa.Column("VIEW_NAME", sa.String(200), nullable=False),
            sa.Column("VIEW_TYPE", sa.String(30), nullable=False),
            sa.Column("FILTERS_JSON", sa.Text(), nullable=True),
            sa.Column("IS_DEFAULT", sa.Boolean(), nullable=False),
            sa.Column("CREATED_DT", sa.DateTime(), nullable=False),
            sa.Column("UPDATED_DT", sa.DateTime(), nullable=False),
            sa.Column("CREATED_BY", sa.String(50), nullable=False),
            sa.Column("UPDATED_BY", sa.String(50), nullable=False),
            sa.ForeignKeyConstraint(
                ["USER_ID"], ["BIC_CCD_APP_USER.USER_ID"],
                name="fk_BIC_CCD_SAVED_VIEW_USER_ID_BIC_CCD_APP_USER",
            ),
            sa.PrimaryKeyConstraint("VIEW_ID", name="pk_BIC_CCD_SAVED_VIEW"),
        )

    # ── Tier 2: depend on KRI_CONFIG ─────────────────────────────────────────

    if not _table_exists("BIC_CCD_KRI_CONFIGURATION"):
        op.create_table(
            "BIC_CCD_KRI_CONFIGURATION",
            sa.Column("CONFIG_ID", sa.Integer(), sa.Identity(start=1), nullable=False),
            sa.Column("KRI_ID", sa.Integer(), nullable=False),
            sa.Column("CONTROL_ID", sa.Integer(), nullable=False),
            sa.Column("SLA_DAYS", sa.Integer(), nullable=False),
            sa.Column("VARIANCE_THRESHOLD", sa.Float(), nullable=False),
            sa.Column("RAG_GREEN_MAX", sa.Float(), nullable=True),
            sa.Column("RAG_AMBER_MAX", sa.Float(), nullable=True),
            sa.Column("REQUIRES_EVIDENCE", sa.Boolean(), nullable=False),
            sa.Column("REQUIRES_APPROVAL", sa.Boolean(), nullable=False),
            sa.Column("FREEZE_DAY", sa.Integer(), nullable=False),
            sa.Column("SLA_START_DAY", sa.Integer(), nullable=True),
            sa.Column("SLA_END_DAY", sa.Integer(), nullable=True),
            sa.Column("RAG_THRESHOLDS", sa.Text(), nullable=True),
            sa.Column("IS_ACTIVE", sa.Boolean(), nullable=False),
            sa.Column("CREATED_DT", sa.DateTime(), nullable=False),
            sa.Column("UPDATED_DT", sa.DateTime(), nullable=False),
            sa.Column("CREATED_BY", sa.String(50), nullable=False),
            sa.Column("UPDATED_BY", sa.String(50), nullable=False),
            sa.ForeignKeyConstraint(
                ["KRI_ID"], ["BIC_CCD_KRI_CONFIG.KRI_ID"],
                name="fk_BIC_CCD_KRI_CONFIGURATION_KRI_ID_BIC_CCD_KRI_CONFIG",
            ),
            sa.ForeignKeyConstraint(
                ["CONTROL_ID"], ["BIC_CCD_KRI_CONTROL.CONTROL_ID"],
                name="fk_BIC_CCD_KRI_CONFIGURATION_CONTROL_ID_BIC_CCD_KRI_CONTROL",
            ),
            sa.PrimaryKeyConstraint("CONFIG_ID", name="pk_BIC_CCD_KRI_CONFIGURATION"),
            sa.UniqueConstraint("KRI_ID", "CONTROL_ID", name="uq_bic_ccd_kri_config_dim"),
        )

    if not _table_exists("BIC_CCD_KRI_DATA_SOURCE_MAPPING"):
        op.create_table(
            "BIC_CCD_KRI_DATA_SOURCE_MAPPING",
            sa.Column("ID", sa.Integer(), sa.Identity(start=1), nullable=False),
            sa.Column("KRI_ID", sa.Integer(), nullable=False),
            sa.Column("DATA_SOURCE", sa.String(200), nullable=False),
            sa.Column("DATA_PAYLOAD", sa.String(200), nullable=True),
            sa.Column("DATA_TABLE", sa.String(200), nullable=True),
            sa.Column("DATA_COLUMN", sa.String(200), nullable=True),
            sa.Column("TABLE_SCHEMA", sa.String(200), nullable=True),
            sa.Column("MAPPING_TYPE", sa.String(20), nullable=True),
            sa.Column("SOURCE_TYPE", sa.String(50), nullable=True),
            sa.Column("CONNECTION_INFO", sa.String(500), nullable=True),
            sa.Column("QUERY_TEMPLATE", sa.Text(), nullable=True),
            sa.Column("SCHEDULE_CRON", sa.String(50), nullable=True),
            sa.Column("IS_ACTIVE", sa.Boolean(), nullable=False),
            sa.Column("CREATED_DT", sa.DateTime(), nullable=False),
            sa.Column("UPDATED_DT", sa.DateTime(), nullable=False),
            sa.Column("CREATED_BY", sa.String(50), nullable=False),
            sa.Column("UPDATED_BY", sa.String(50), nullable=False),
            sa.ForeignKeyConstraint(
                ["KRI_ID"], ["BIC_CCD_KRI_CONFIG.KRI_ID"],
                name="fk_BIC_CCD_KRI_DATA_SOURCE_MAPPING_KRI_ID_BIC_CCD_KRI_CONFIG",
            ),
            sa.PrimaryKeyConstraint("ID", name="pk_BIC_CCD_KRI_DATA_SOURCE_MAPPING"),
        )

    if not _table_exists("BIC_CCD_KRI_USER_ROLE"):
        op.create_table(
            "BIC_CCD_KRI_USER_ROLE",
            sa.Column("ID", sa.Integer(), sa.Identity(start=1), nullable=False),
            sa.Column("KRI_ID", sa.Integer(), nullable=False),
            sa.Column("USER_ID", sa.Integer(), nullable=False),
            sa.Column("DATA_PROVIDER", sa.Boolean(), nullable=False),
            sa.Column("METRIC_OWNER", sa.Boolean(), nullable=False),
            sa.Column("REMEDIATION_OWNER", sa.Boolean(), nullable=False),
            sa.Column("MAKER", sa.Boolean(), nullable=False),
            sa.Column("CHECKER", sa.Boolean(), nullable=False),
            sa.Column("BI_METRIC_LEAD", sa.Boolean(), nullable=False),
            sa.Column("CREATED_DT", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(
                ["KRI_ID"], ["BIC_CCD_KRI_CONFIG.KRI_ID"],
                name="fk_BIC_CCD_KRI_USER_ROLE_KRI_ID_BIC_CCD_KRI_CONFIG",
            ),
            sa.ForeignKeyConstraint(
                ["USER_ID"], ["BIC_CCD_APP_USER.USER_ID"],
                name="fk_BIC_CCD_KRI_USER_ROLE_USER_ID_BIC_CCD_APP_USER",
            ),
            sa.PrimaryKeyConstraint("ID", name="pk_BIC_CCD_KRI_USER_ROLE"),
            sa.UniqueConstraint("KRI_ID", "USER_ID", name="uq_bic_ccd_kri_user_role"),
        )

    if not _table_exists("BIC_CCD_APPROVAL_ASSIGNMENT_RULE"):
        op.create_table(
            "BIC_CCD_APPROVAL_ASSIGNMENT_RULE",
            sa.Column("RULE_ID", sa.Integer(), sa.Identity(start=1), nullable=False),
            sa.Column("ROLE_CODE", sa.String(20), nullable=False),
            sa.Column("USER_ID", sa.Integer(), nullable=True),
            sa.Column("REGION_ID", sa.Integer(), nullable=True),
            sa.Column("KRI_ID", sa.Integer(), nullable=True),
            sa.Column("CATEGORY_ID", sa.Integer(), nullable=True),
            sa.Column("PRIORITY", sa.Integer(), nullable=False),
            sa.Column("IS_ACTIVE", sa.Boolean(), nullable=False),
            sa.Column("CREATED_DT", sa.DateTime(), nullable=False),
            sa.Column("UPDATED_DT", sa.DateTime(), nullable=False),
            sa.Column("CREATED_BY", sa.String(50), nullable=False),
            sa.Column("UPDATED_BY", sa.String(50), nullable=False),
            sa.ForeignKeyConstraint(
                ["USER_ID"], ["BIC_CCD_APP_USER.USER_ID"],
                name="fk_BIC_CCD_APPROVAL_ASSIGNMENT_RULE_USER_ID_BIC_CCD_APP_USER",
            ),
            sa.ForeignKeyConstraint(
                ["REGION_ID"], ["BIC_CCD_REGION.REGION_ID"],
                name="fk_BIC_CCD_APPROVAL_ASSIGNMENT_RULE_REGION_ID_BIC_CCD_REGION",
            ),
            sa.ForeignKeyConstraint(
                ["KRI_ID"], ["BIC_CCD_KRI_CONFIG.KRI_ID"],
                name="fk_BIC_CCD_APPROVAL_ASSIGNMENT_RULE_KRI_ID_BIC_CCD_KRI_CONFIG",
            ),
            sa.ForeignKeyConstraint(
                ["CATEGORY_ID"], ["BIC_CCD_KRI_CATEGORY.CATEGORY_ID"],
                name="fk_BIC_CCD_APPROVAL_ASSIGNMENT_RULE_CATEGORY_ID_BIC_CCD_KRI_CATEGORY",
            ),
            sa.PrimaryKeyConstraint("RULE_ID", name="pk_BIC_CCD_APPROVAL_ASSIGNMENT_RULE"),
        )
        op.create_index(
            "idx_bic_ccd_aar_role_region",
            "BIC_CCD_APPROVAL_ASSIGNMENT_RULE", ["ROLE_CODE", "REGION_ID"],
        )

    if not _table_exists("BIC_CCD_KRI_BLUESHEET"):
        op.create_table(
            "BIC_CCD_KRI_BLUESHEET",
            sa.Column("BLUESHEET_ID", sa.Integer(), sa.Identity(start=1), nullable=False),
            sa.Column("KRI_ID", sa.Integer(), nullable=False),
            sa.Column("LEGACY_KRI_ID", sa.String(50), nullable=True),
            sa.Column("THRESHOLD", sa.String(100), nullable=True),
            sa.Column("CIRCUIT_BREAKER", sa.String(100), nullable=True),
            sa.Column("CONTROL_IDS", sa.String(500), nullable=True),
            sa.Column("DQ_OBJECTIVES", sa.Text(), nullable=True),
            sa.Column("PRIMARY_SENIOR_MANAGER", sa.String(200), nullable=True),
            sa.Column("METRIC_OWNER_NAME", sa.String(200), nullable=True),
            sa.Column("REMEDIATION_OWNER_NAME", sa.String(200), nullable=True),
            sa.Column("BI_METRICS_LEAD", sa.String(200), nullable=True),
            sa.Column("DATA_PROVIDER_NAME", sa.String(200), nullable=True),
            sa.Column("SC_UK", sa.Boolean(), nullable=False),
            sa.Column("SC_FINANCE", sa.Boolean(), nullable=False),
            sa.Column("SC_RISK", sa.Boolean(), nullable=False),
            sa.Column("SC_LIQUIDITY", sa.Boolean(), nullable=False),
            sa.Column("SC_CAPITAL", sa.Boolean(), nullable=False),
            sa.Column("SC_RISK_REPORTS", sa.Boolean(), nullable=False),
            sa.Column("SC_MARKETS", sa.Boolean(), nullable=False),
            sa.Column("WHY_SELECTED", sa.Text(), nullable=True),
            sa.Column("THRESHOLD_RATIONALE", sa.Text(), nullable=True),
            sa.Column("LIMITATIONS", sa.Text(), nullable=True),
            sa.Column("KRI_CALCULATION", sa.Text(), nullable=True),
            sa.Column("RUNBOOK_S3_PATH", sa.String(500), nullable=True),
            sa.Column("RUNBOOK_FILENAME", sa.String(300), nullable=True),
            sa.Column("RUNBOOK_VERSION", sa.String(20), nullable=True),
            sa.Column("RUNBOOK_REVIEW_DATE", sa.Date(), nullable=True),
            sa.Column("RUNBOOK_NOTES", sa.Text(), nullable=True),
            sa.Column("APPROVAL_STATUS", sa.String(20), nullable=False),
            sa.Column("SUBMITTED_BY", sa.Integer(), nullable=True),
            sa.Column("SUBMITTED_DT", sa.DateTime(), nullable=True),
            sa.Column("CREATED_DT", sa.DateTime(), nullable=False),
            sa.Column("UPDATED_DT", sa.DateTime(), nullable=False),
            sa.Column("CREATED_BY", sa.String(50), nullable=False),
            sa.Column("UPDATED_BY", sa.String(50), nullable=False),
            sa.ForeignKeyConstraint(
                ["KRI_ID"], ["BIC_CCD_KRI_CONFIG.KRI_ID"],
                name="fk_BIC_CCD_KRI_BLUESHEET_KRI_ID_BIC_CCD_KRI_CONFIG",
            ),
            sa.ForeignKeyConstraint(
                ["SUBMITTED_BY"], ["BIC_CCD_APP_USER.USER_ID"],
                name="fk_BIC_CCD_KRI_BLUESHEET_SUBMITTED_BY_BIC_CCD_APP_USER",
            ),
            sa.PrimaryKeyConstraint("BLUESHEET_ID", name="pk_BIC_CCD_KRI_BLUESHEET"),
            sa.UniqueConstraint("KRI_ID", name="uq_BIC_CCD_KRI_BLUESHEET_KRI_ID"),
        )

    if not _table_exists("BIC_CCD_KRI_APPROVAL_LOG"):
        op.create_table(
            "BIC_CCD_KRI_APPROVAL_LOG",
            sa.Column("LOG_ID", sa.Integer(), sa.Identity(start=1), nullable=False),
            sa.Column("KRI_ID", sa.Integer(), nullable=False),
            sa.Column("ACTION", sa.String(20), nullable=False),
            sa.Column("PERFORMED_BY", sa.Integer(), nullable=False),
            sa.Column("PERFORMED_DT", sa.DateTime(), nullable=False),
            sa.Column("COMMENTS", sa.Text(), nullable=True),
            sa.Column("PREVIOUS_STATUS", sa.String(20), nullable=True),
            sa.Column("NEW_STATUS", sa.String(20), nullable=True),
            sa.ForeignKeyConstraint(
                ["KRI_ID"], ["BIC_CCD_KRI_CONFIG.KRI_ID"],
                name="fk_BIC_CCD_KRI_APPROVAL_LOG_KRI_ID_BIC_CCD_KRI_CONFIG",
            ),
            sa.ForeignKeyConstraint(
                ["PERFORMED_BY"], ["BIC_CCD_APP_USER.USER_ID"],
                name="fk_BIC_CCD_KRI_APPROVAL_LOG_PERFORMED_BY_BIC_CCD_APP_USER",
            ),
            sa.PrimaryKeyConstraint("LOG_ID", name="pk_BIC_CCD_KRI_APPROVAL_LOG"),
        )

    if not _table_exists("BIC_CCD_SCORECARD"):
        op.create_table(
            "BIC_CCD_SCORECARD",
            sa.Column("TRANSACTION_ID", sa.Integer(), sa.Identity(start=1), nullable=False),
            sa.Column("CASE_ID", sa.String(50), nullable=True),
            sa.Column("CASE_STATUS", sa.String(20), nullable=False),
            sa.Column("REQUEST_TITLE", sa.String(500), nullable=False),
            sa.Column("PRODUCT_LEVEL_VALUE", sa.String(200), nullable=True),
            sa.Column("FILE_ID", sa.Integer(), nullable=True),
            sa.Column("REGION_ID", sa.Integer(), nullable=False),
            sa.Column("NOTES", sa.Text(), nullable=True),
            sa.Column("MONTH", sa.Integer(), nullable=True),
            sa.Column("YEAR", sa.Integer(), nullable=True),
            sa.Column("DUE_DATE", sa.Date(), nullable=True),
            sa.Column("SUBMITTED_DT", sa.DateTime(), nullable=True),
            sa.Column("KRI_ID", sa.Integer(), nullable=True),
            sa.Column("CREATED_BY_USER_ID", sa.Integer(), nullable=False),
            sa.Column("CREATED_DT", sa.DateTime(), nullable=False),
            sa.Column("UPDATED_DT", sa.DateTime(), nullable=False),
            sa.Column("CREATED_BY", sa.String(50), nullable=False),
            sa.Column("UPDATED_BY", sa.String(50), nullable=False),
            sa.ForeignKeyConstraint(
                ["FILE_ID"], ["BIC_CCD_CASE_FILE.FILE_ID"],
                name="fk_BIC_CCD_SCORECARD_FILE_ID_BIC_CCD_CASE_FILE",
            ),
            sa.ForeignKeyConstraint(
                ["REGION_ID"], ["BIC_CCD_REGION.REGION_ID"],
                name="fk_BIC_CCD_SCORECARD_REGION_ID_BIC_CCD_REGION",
            ),
            sa.ForeignKeyConstraint(
                ["KRI_ID"], ["BIC_CCD_KRI_CONFIG.KRI_ID"],
                name="fk_BIC_CCD_SCORECARD_KRI_ID_BIC_CCD_KRI_CONFIG",
            ),
            sa.ForeignKeyConstraint(
                ["CREATED_BY_USER_ID"], ["BIC_CCD_APP_USER.USER_ID"],
                name="fk_BIC_CCD_SCORECARD_CREATED_BY_USER_ID_BIC_CCD_APP_USER",
            ),
            sa.PrimaryKeyConstraint("TRANSACTION_ID", name="pk_BIC_CCD_SCORECARD"),
        )

    # ── Tier 3: depend on KRI_CONFIG + KRI_CONTROL + (APP_USER / DATA_SOURCE) ─

    if not _table_exists("BIC_CCD_KRI_CONTROL_STATUS_TRACKER"):
        op.create_table(
            "BIC_CCD_KRI_CONTROL_STATUS_TRACKER",
            sa.Column("ID", sa.Integer(), sa.Identity(start=1), nullable=False),
            sa.Column("KRI_ID", sa.Integer(), nullable=False),
            sa.Column("CONTROL_ID", sa.Integer(), nullable=False),
            sa.Column("YEAR", sa.Integer(), nullable=False),
            sa.Column("MONTH", sa.Integer(), nullable=False),
            sa.Column("STATUS", sa.String(30), nullable=False),
            sa.Column("STATUS_ID", sa.Integer(), nullable=True),
            sa.Column("SLA_START", sa.DateTime(), nullable=True),
            sa.Column("SLA_END", sa.DateTime(), nullable=True),
            sa.Column("SLA_CHECK", sa.Boolean(), nullable=True),
            sa.Column("ACCURACY_CHECK", sa.Boolean(), nullable=True),
            sa.Column("COMPLETENESS_CHECK", sa.Boolean(), nullable=True),
            sa.Column("KRI_VERSION", sa.String(20), nullable=True),
            sa.Column("SHORT_COMMENT", sa.String(200), nullable=True),
            sa.Column("LONG_COMMENT", sa.Text(), nullable=True),
            sa.Column("VERSION_COMMENT", sa.String(500), nullable=True),
            sa.Column("RETRY_COUNT", sa.Integer(), nullable=False),
            sa.Column("ASSIGNED_TO", sa.Integer(), nullable=True),
            sa.Column("ADMIN_UPDATE", sa.String(200), nullable=True),
            sa.Column("ADMIN_UPDATE_DT", sa.DateTime(), nullable=True),
            sa.Column("RAG_STATUS", sa.String(10), nullable=True),
            sa.Column("SLA_DUE_DT", sa.DateTime(), nullable=True),
            sa.Column("SLA_MET", sa.Boolean(), nullable=True),
            sa.Column("COMPLETED_DT", sa.DateTime(), nullable=True),
            sa.Column("CURRENT_APPROVER", sa.Integer(), nullable=True),
            sa.Column("APPROVAL_LEVEL", sa.String(10), nullable=True),
            sa.Column("CREATED_DT", sa.DateTime(), nullable=False),
            sa.Column("UPDATED_DT", sa.DateTime(), nullable=False),
            sa.Column("CREATED_BY", sa.String(50), nullable=False),
            sa.Column("UPDATED_BY", sa.String(50), nullable=False),
            sa.ForeignKeyConstraint(
                ["KRI_ID"], ["BIC_CCD_KRI_CONFIG.KRI_ID"],
                name="fk_BIC_CCD_KRI_CTRL_STAT_TRK_KRI_ID",
            ),
            sa.ForeignKeyConstraint(
                ["CONTROL_ID"], ["BIC_CCD_KRI_CONTROL.CONTROL_ID"],
                name="fk_BIC_CCD_KRI_CTRL_STAT_TRK_CONTROL_ID",
            ),
            sa.ForeignKeyConstraint(
                ["STATUS_ID"], ["BIC_CCD_KRI_STATUS.STATUS_ID"],
                name="fk_BIC_CCD_KRI_CTRL_STAT_TRK_STATUS_ID",
            ),
            sa.ForeignKeyConstraint(
                ["ASSIGNED_TO"], ["BIC_CCD_APP_USER.USER_ID"],
                name="fk_BIC_CCD_KRI_CTRL_STAT_TRK_ASSIGNED_TO",
            ),
            sa.ForeignKeyConstraint(
                ["CURRENT_APPROVER"], ["BIC_CCD_APP_USER.USER_ID"],
                name="fk_BIC_CCD_KRI_CTRL_STAT_TRK_CURRENT_APPROVER",
            ),
            sa.PrimaryKeyConstraint("ID", name="pk_BIC_CCD_KRI_CONTROL_STATUS_TRACKER"),
            sa.UniqueConstraint(
                "KRI_ID", "CONTROL_ID", "YEAR", "MONTH",
                name="uq_bic_ccd_status_tracker_period",
            ),
        )
        op.create_index(
            "idx_bic_ccd_status_tracker_period",
            "BIC_CCD_KRI_CONTROL_STATUS_TRACKER", ["YEAR", "MONTH"],
        )

    if not _table_exists("BIC_CCD_KRI_DATA_SOURCE_STATUS_TRACKER"):
        op.create_table(
            "BIC_CCD_KRI_DATA_SOURCE_STATUS_TRACKER",
            sa.Column("ID", sa.Integer(), sa.Identity(start=1), nullable=False),
            sa.Column("MAPPING_ID", sa.Integer(), nullable=False),
            sa.Column("MONTH", sa.Integer(), nullable=False),
            sa.Column("YEAR", sa.Integer(), nullable=False),
            sa.Column("STATUS_ID", sa.Integer(), nullable=True),
            sa.Column("STATUS", sa.String(30), nullable=False),
            sa.Column("RECEIVED_DT", sa.DateTime(), nullable=True),
            sa.Column("UPDATED_DT", sa.DateTime(), nullable=False),
            sa.Column("CREATED_DT", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(
                ["MAPPING_ID"], ["BIC_CCD_KRI_DATA_SOURCE_MAPPING.ID"],
                name="fk_BIC_CCD_KRI_DATA_SOURCE_STATUS_TRACKER_MAPPING_ID",
            ),
            sa.ForeignKeyConstraint(
                ["STATUS_ID"], ["BIC_CCD_KRI_STATUS.STATUS_ID"],
                name="fk_BIC_CCD_KRI_DATA_SOURCE_STATUS_TRACKER_STATUS_ID",
            ),
            sa.PrimaryKeyConstraint("ID", name="pk_BIC_CCD_KRI_DATA_SOURCE_STATUS_TRACKER"),
            sa.UniqueConstraint("MAPPING_ID", "MONTH", "YEAR", name="uq_bic_ccd_ds_tracker"),
        )

    if not _table_exists("BIC_CCD_KRI_ASSIGNMENT_TRACKER"):
        op.create_table(
            "BIC_CCD_KRI_ASSIGNMENT_TRACKER",
            sa.Column("ID", sa.Integer(), sa.Identity(start=1), nullable=False),
            sa.Column("KRI_ID", sa.Integer(), nullable=False),
            sa.Column("CONTROL_ID", sa.Integer(), nullable=False),
            sa.Column("MONTH", sa.Integer(), nullable=True),
            sa.Column("YEAR", sa.Integer(), nullable=True),
            sa.Column("ASSIGNED_TO", sa.Integer(), nullable=False),
            sa.Column("STATUS_ID", sa.Integer(), nullable=True),
            sa.Column("APPROVER_TYPE", sa.String(30), nullable=False),
            sa.Column("COMMENTS", sa.Text(), nullable=True),
            sa.Column("IS_ACTIVE", sa.Boolean(), nullable=False),
            sa.Column("CREATED_DT", sa.DateTime(), nullable=False),
            sa.Column("UPDATED_DT", sa.DateTime(), nullable=False),
            sa.Column("CREATED_BY", sa.String(50), nullable=False),
            sa.Column("UPDATED_BY", sa.String(50), nullable=False),
            sa.ForeignKeyConstraint(
                ["KRI_ID"], ["BIC_CCD_KRI_CONFIG.KRI_ID"],
                name="fk_BIC_CCD_KRI_ASSIGNMENT_TRACKER_KRI_ID_BIC_CCD_KRI_CONFIG",
            ),
            sa.ForeignKeyConstraint(
                ["CONTROL_ID"], ["BIC_CCD_KRI_CONTROL.CONTROL_ID"],
                name="fk_BIC_CCD_KRI_ASSIGNMENT_TRACKER_CONTROL_ID_BIC_CCD_KRI_CONTROL",
            ),
            sa.ForeignKeyConstraint(
                ["ASSIGNED_TO"], ["BIC_CCD_APP_USER.USER_ID"],
                name="fk_BIC_CCD_KRI_ASSIGNMENT_TRACKER_ASSIGNED_TO_BIC_CCD_APP_USER",
            ),
            sa.ForeignKeyConstraint(
                ["STATUS_ID"], ["BIC_CCD_KRI_STATUS.STATUS_ID"],
                name="fk_BIC_CCD_KRI_ASSIGNMENT_TRACKER_STATUS_ID_BIC_CCD_KRI_STATUS",
            ),
            sa.PrimaryKeyConstraint("ID", name="pk_BIC_CCD_KRI_ASSIGNMENT_TRACKER"),
        )

    if not _table_exists("BIC_CCD_KRI_METRIC"):
        op.create_table(
            "BIC_CCD_KRI_METRIC",
            sa.Column("METRIC_ID", sa.Integer(), sa.Identity(start=1), nullable=False),
            sa.Column("KRI_ID", sa.Integer(), nullable=False),
            sa.Column("CONTROL_ID", sa.Integer(), nullable=False),
            sa.Column("YEAR", sa.Integer(), nullable=False),
            sa.Column("MONTH", sa.Integer(), nullable=False),
            sa.Column("METRIC_VALUE", sa.Float(), nullable=True),
            sa.Column("RAG_STATUS", sa.String(10), nullable=True),
            sa.Column("RUN_DATE", sa.DateTime(), nullable=True),
            sa.Column("PREVIOUS_VALUE", sa.Float(), nullable=True),
            sa.Column("VARIANCE_PCT", sa.Float(), nullable=True),
            sa.Column("VARIANCE_STATUS", sa.String(10), nullable=True),
            sa.Column("SOURCE_ID", sa.Integer(), nullable=True),
            sa.Column("CAPTURED_DT", sa.DateTime(), nullable=True),
            sa.Column("CREATED_DT", sa.DateTime(), nullable=False),
            sa.Column("UPDATED_DT", sa.DateTime(), nullable=False),
            sa.Column("CREATED_BY", sa.String(50), nullable=False),
            sa.Column("UPDATED_BY", sa.String(50), nullable=False),
            sa.ForeignKeyConstraint(
                ["KRI_ID"], ["BIC_CCD_KRI_CONFIG.KRI_ID"],
                name="fk_BIC_CCD_KRI_METRIC_KRI_ID_BIC_CCD_KRI_CONFIG",
            ),
            sa.ForeignKeyConstraint(
                ["CONTROL_ID"], ["BIC_CCD_KRI_CONTROL.CONTROL_ID"],
                name="fk_BIC_CCD_KRI_METRIC_CONTROL_ID_BIC_CCD_KRI_CONTROL",
            ),
            sa.ForeignKeyConstraint(
                ["SOURCE_ID"], ["BIC_CCD_KRI_DATA_SOURCE_MAPPING.ID"],
                name="fk_BIC_CCD_KRI_METRIC_SOURCE_ID_BIC_CCD_KRI_DATA_SOURCE_MAPPING",
            ),
            sa.PrimaryKeyConstraint("METRIC_ID", name="pk_BIC_CCD_KRI_METRIC"),
        )

    if not _table_exists("BIC_CCD_SCORECARD_APPROVER"):
        op.create_table(
            "BIC_CCD_SCORECARD_APPROVER",
            sa.Column("ID", sa.Integer(), sa.Identity(start=1), nullable=False),
            sa.Column("CASE_ID", sa.Integer(), nullable=False),
            sa.Column("USER_ID", sa.Integer(), nullable=False),
            sa.Column("APPROVED_AT", sa.DateTime(), nullable=True),
            sa.Column("ACTION", sa.String(20), nullable=True),
            sa.Column("COMMENTS", sa.Text(), nullable=True),
            sa.ForeignKeyConstraint(
                ["CASE_ID"], ["BIC_CCD_SCORECARD.TRANSACTION_ID"],
                name="fk_BIC_CCD_SCORECARD_APPROVER_CASE_ID_BIC_CCD_SCORECARD",
            ),
            sa.ForeignKeyConstraint(
                ["USER_ID"], ["BIC_CCD_APP_USER.USER_ID"],
                name="fk_BIC_CCD_SCORECARD_APPROVER_USER_ID_BIC_CCD_APP_USER",
            ),
            sa.PrimaryKeyConstraint("ID", name="pk_BIC_CCD_SCORECARD_APPROVER"),
        )

    if not _table_exists("BIC_CCD_SCORECARD_ACTIVITY_LOG"):
        op.create_table(
            "BIC_CCD_SCORECARD_ACTIVITY_LOG",
            sa.Column("ID", sa.Integer(), sa.Identity(start=1), nullable=False),
            sa.Column("CASE_ID", sa.Integer(), nullable=False),
            sa.Column("CASE_STATUS", sa.String(20), nullable=False),
            sa.Column("FILE_ID", sa.Integer(), nullable=True),
            sa.Column("FILE_PATH", sa.String(500), nullable=True),
            sa.Column("REVIEW_COMMENTS", sa.Text(), nullable=True),
            sa.Column("CREATED_BY", sa.String(50), nullable=False),
            sa.Column("CREATED_DT", sa.DateTime(), nullable=False),
            sa.Column("ACTION", sa.String(30), nullable=True),
            sa.Column("PERFORMED_BY", sa.Integer(), nullable=True),
            sa.Column("PREVIOUS_STATUS", sa.String(20), nullable=True),
            sa.ForeignKeyConstraint(
                ["CASE_ID"], ["BIC_CCD_SCORECARD.TRANSACTION_ID"],
                name="fk_BIC_CCD_SCORECARD_ACTIVITY_LOG_CASE_ID_BIC_CCD_SCORECARD",
            ),
            sa.ForeignKeyConstraint(
                ["FILE_ID"], ["BIC_CCD_CASE_FILE.FILE_ID"],
                name="fk_BIC_CCD_SCORECARD_ACTIVITY_LOG_FILE_ID_BIC_CCD_CASE_FILE",
            ),
            sa.ForeignKeyConstraint(
                ["PERFORMED_BY"], ["BIC_CCD_APP_USER.USER_ID"],
                name="fk_BIC_CCD_SCORECARD_ACTIVITY_LOG_PERFORMED_BY_BIC_CCD_APP_USER",
            ),
            sa.PrimaryKeyConstraint("ID", name="pk_BIC_CCD_SCORECARD_ACTIVITY_LOG"),
        )

    # ── Tier 4: depend on STATUS_TRACKER / KRI_EVIDENCE ─────────────────────

    if not _table_exists("BIC_CCD_KRI_EVIDENCE"):
        op.create_table(
            "BIC_CCD_KRI_EVIDENCE",
            sa.Column("ID", sa.Integer(), sa.Identity(start=1), nullable=False),
            sa.Column("KRI_ID", sa.Integer(), nullable=False),
            sa.Column("CONTROL_ID", sa.Integer(), nullable=False),
            sa.Column("YEAR", sa.Integer(), nullable=False),
            sa.Column("MONTH", sa.Integer(), nullable=False),
            sa.Column("FILE_NAME", sa.String(500), nullable=False),
            sa.Column("FILE_PATH", sa.String(500), nullable=True),
            sa.Column("FILE_STATUS", sa.String(20), nullable=False, server_default="ACTIVE"),
            sa.Column("FILE_ID", sa.String(100), nullable=True),
            sa.Column("FILE_UPLOAD_ID", sa.String(100), nullable=True),
            sa.Column("KRI_UPLOAD_VERSION", sa.Integer(), nullable=True),
            sa.Column("FILE_TYPE", sa.String(10), nullable=True),
            sa.Column("FILE_SIZE_BYTES", sa.Integer(), nullable=True),
            sa.Column("S3_BUCKET", sa.String(200), nullable=True),
            sa.Column("VERSION_NUMBER", sa.Integer(), nullable=False),
            sa.Column("IS_LOCKED", sa.Boolean(), nullable=False),
            sa.Column("LOCKED_DT", sa.DateTime(), nullable=True),
            sa.Column("LOCKED_BY", sa.String(50), nullable=True),
            sa.Column("UPLOADED_BY", sa.Integer(), nullable=False),
            sa.Column("UPLOADED_DT", sa.DateTime(), nullable=False),
            sa.Column("METADATA_JSON", sa.Text(), nullable=True),
            sa.Column("REGION_ID", sa.Integer(), nullable=True),
            sa.Column("TRACKER_ID", sa.Integer(), nullable=True),
            sa.Column("CREATED_DT", sa.DateTime(), nullable=False),
            sa.Column("UPDATED_DT", sa.DateTime(), nullable=False),
            sa.Column("CREATED_BY", sa.String(50), nullable=False),
            sa.Column("UPDATED_BY", sa.String(50), nullable=False),
            sa.ForeignKeyConstraint(
                ["KRI_ID"], ["BIC_CCD_KRI_CONFIG.KRI_ID"],
                name="fk_BIC_CCD_KRI_EVIDENCE_KRI_ID_BIC_CCD_KRI_CONFIG",
            ),
            sa.ForeignKeyConstraint(
                ["CONTROL_ID"], ["BIC_CCD_KRI_CONTROL.CONTROL_ID"],
                name="fk_BIC_CCD_KRI_EVIDENCE_CONTROL_ID_BIC_CCD_KRI_CONTROL",
            ),
            sa.ForeignKeyConstraint(
                ["UPLOADED_BY"], ["BIC_CCD_APP_USER.USER_ID"],
                name="fk_BIC_CCD_KRI_EVIDENCE_UPLOADED_BY_BIC_CCD_APP_USER",
            ),
            sa.ForeignKeyConstraint(
                ["REGION_ID"], ["BIC_CCD_REGION.REGION_ID"],
                name="fk_BIC_CCD_KRI_EVIDENCE_REGION_ID_BIC_CCD_REGION",
            ),
            sa.ForeignKeyConstraint(
                ["TRACKER_ID"], ["BIC_CCD_KRI_CONTROL_STATUS_TRACKER.ID"],
                name="fk_BIC_CCD_KRI_EVIDENCE_TRACKER_ID_BIC_CCD_KRI_CTRL_STAT_TRK",
            ),
            sa.PrimaryKeyConstraint("ID", name="pk_BIC_CCD_KRI_EVIDENCE"),
        )

    if not _table_exists("BIC_CCD_KRI_COMMENT"):
        op.create_table(
            "BIC_CCD_KRI_COMMENT",
            sa.Column("ID", sa.Integer(), sa.Identity(start=1), nullable=False),
            sa.Column("KRI_ID", sa.Integer(), nullable=False),
            sa.Column("MONTH", sa.Integer(), nullable=True),
            sa.Column("YEAR", sa.Integer(), nullable=True),
            sa.Column("COMMENTS", sa.Text(), nullable=False),
            sa.Column("CONTROL_ID", sa.Integer(), nullable=True),
            sa.Column("STATUS_ID", sa.Integer(), nullable=True),
            sa.Column("COMMENT_TYPE", sa.String(20), nullable=False),
            sa.Column("PARENT_COMMENT_ID", sa.Integer(), nullable=True),
            sa.Column("POSTED_BY", sa.Integer(), nullable=False),
            sa.Column("POSTED_DT", sa.DateTime(), nullable=False),
            sa.Column("IS_RESOLVED", sa.Boolean(), nullable=False),
            sa.Column("CREATED_DT", sa.DateTime(), nullable=False),
            sa.Column("UPDATED_DT", sa.DateTime(), nullable=False),
            sa.Column("CREATED_BY", sa.String(50), nullable=False),
            sa.Column("UPDATED_BY", sa.String(50), nullable=False),
            sa.ForeignKeyConstraint(
                ["KRI_ID"], ["BIC_CCD_KRI_CONFIG.KRI_ID"],
                name="fk_BIC_CCD_KRI_COMMENT_KRI_ID_BIC_CCD_KRI_CONFIG",
            ),
            sa.ForeignKeyConstraint(
                ["CONTROL_ID"], ["BIC_CCD_KRI_CONTROL.CONTROL_ID"],
                name="fk_BIC_CCD_KRI_COMMENT_CONTROL_ID_BIC_CCD_KRI_CONTROL",
            ),
            sa.ForeignKeyConstraint(
                ["STATUS_ID"], ["BIC_CCD_KRI_CONTROL_STATUS_TRACKER.ID"],
                name="fk_BIC_CCD_KRI_COMMENT_STATUS_ID_BIC_CCD_KRI_CTRL_STAT_TRK",
            ),
            sa.ForeignKeyConstraint(
                ["POSTED_BY"], ["BIC_CCD_APP_USER.USER_ID"],
                name="fk_BIC_CCD_KRI_COMMENT_POSTED_BY_BIC_CCD_APP_USER",
            ),
            sa.ForeignKeyConstraint(
                ["PARENT_COMMENT_ID"], ["BIC_CCD_KRI_COMMENT.ID"],
                name="fk_BIC_CCD_KRI_COMMENT_PARENT_COMMENT_ID_BIC_CCD_KRI_COMMENT",
            ),
            sa.PrimaryKeyConstraint("ID", name="pk_BIC_CCD_KRI_COMMENT"),
        )

    if not _table_exists("BIC_CCD_KRI_ASSIGNMENT_AUDIT"):
        op.create_table(
            "BIC_CCD_KRI_ASSIGNMENT_AUDIT",
            sa.Column("ID", sa.Integer(), sa.Identity(start=1), nullable=False),
            sa.Column("KRI_ID", sa.Integer(), nullable=False),
            sa.Column("CONTROL_ID", sa.Integer(), nullable=False),
            sa.Column("MONTH", sa.Integer(), nullable=True),
            sa.Column("YEAR", sa.Integer(), nullable=True),
            sa.Column("ASSIGNED_TO", sa.Integer(), nullable=False),
            sa.Column("STATUS_ID", sa.Integer(), nullable=True),
            sa.Column("APPROVER_TYPE", sa.String(30), nullable=True),
            sa.Column("COMMENTS", sa.Text(), nullable=True),
            sa.Column("CREATED_BY_USER", sa.Integer(), nullable=False),
            sa.Column("CREATED_DT", sa.DateTime(), nullable=False),
            sa.Column("ACTION", sa.String(20), nullable=True),
            sa.Column("ASSIGNMENT_ID", sa.Integer(), nullable=True),
            sa.ForeignKeyConstraint(
                ["KRI_ID"], ["BIC_CCD_KRI_CONFIG.KRI_ID"],
                name="fk_BIC_CCD_KRI_ASSIGNMENT_AUDIT_KRI_ID_BIC_CCD_KRI_CONFIG",
            ),
            sa.ForeignKeyConstraint(
                ["CONTROL_ID"], ["BIC_CCD_KRI_CONTROL.CONTROL_ID"],
                name="fk_BIC_CCD_KRI_ASSIGNMENT_AUDIT_CONTROL_ID_BIC_CCD_KRI_CONTROL",
            ),
            sa.ForeignKeyConstraint(
                ["ASSIGNED_TO"], ["BIC_CCD_APP_USER.USER_ID"],
                name="fk_BIC_CCD_KRI_ASSIGNMENT_AUDIT_ASSIGNED_TO_BIC_CCD_APP_USER",
            ),
            sa.ForeignKeyConstraint(
                ["CREATED_BY_USER"], ["BIC_CCD_APP_USER.USER_ID"],
                name="fk_BIC_CCD_KRI_ASSIGNMENT_AUDIT_CREATED_BY_USER_BIC_CCD_APP_USER",
            ),
            sa.ForeignKeyConstraint(
                ["ASSIGNMENT_ID"], ["BIC_CCD_KRI_ASSIGNMENT_TRACKER.ID"],
                name="fk_BIC_CCD_KRI_ASSIGNMENT_AUDIT_ASSIGNMENT_ID",
            ),
            sa.PrimaryKeyConstraint("ID", name="pk_BIC_CCD_KRI_ASSIGNMENT_AUDIT"),
        )

    if not _table_exists("BIC_CCD_MAKER_CHECKER_SUBMISSION"):
        op.create_table(
            "BIC_CCD_MAKER_CHECKER_SUBMISSION",
            sa.Column("SUBMISSION_ID", sa.Integer(), sa.Identity(start=1), nullable=False),
            sa.Column("STATUS_ID", sa.Integer(), nullable=False),
            sa.Column("EVIDENCE_ID", sa.Integer(), nullable=True),
            sa.Column("SUBMITTED_BY", sa.Integer(), nullable=False),
            sa.Column("SUBMITTED_DT", sa.DateTime(), nullable=False),
            sa.Column("SUBMISSION_NOTES", sa.Text(), nullable=True),
            sa.Column("L1_APPROVER_ID", sa.Integer(), nullable=True),
            sa.Column("L1_ACTION", sa.String(20), nullable=True),
            sa.Column("L1_ACTION_DT", sa.DateTime(), nullable=True),
            sa.Column("L1_COMMENTS", sa.String(2000), nullable=True),
            sa.Column("L2_APPROVER_ID", sa.Integer(), nullable=True),
            sa.Column("L2_ACTION", sa.String(20), nullable=True),
            sa.Column("L2_ACTION_DT", sa.DateTime(), nullable=True),
            sa.Column("L2_COMMENTS", sa.String(2000), nullable=True),
            sa.Column("L3_APPROVER_ID", sa.Integer(), nullable=True),
            sa.Column("L3_ACTION", sa.String(20), nullable=True),
            sa.Column("L3_ACTION_DT", sa.DateTime(), nullable=True),
            sa.Column("L3_COMMENTS", sa.String(2000), nullable=True),
            sa.Column("FINAL_STATUS", sa.String(20), nullable=False),
            sa.Column("CREATED_DT", sa.DateTime(), nullable=False),
            sa.Column("UPDATED_DT", sa.DateTime(), nullable=False),
            sa.Column("CREATED_BY", sa.String(50), nullable=False),
            sa.Column("UPDATED_BY", sa.String(50), nullable=False),
            sa.ForeignKeyConstraint(
                ["STATUS_ID"], ["BIC_CCD_KRI_CONTROL_STATUS_TRACKER.ID"],
                name="fk_BIC_CCD_MAKER_CHECKER_SUBMISSION_STATUS_ID",
            ),
            sa.ForeignKeyConstraint(
                ["EVIDENCE_ID"], ["BIC_CCD_KRI_EVIDENCE.ID"],
                name="fk_BIC_CCD_MAKER_CHECKER_SUBMISSION_EVIDENCE_ID",
            ),
            sa.ForeignKeyConstraint(
                ["SUBMITTED_BY"], ["BIC_CCD_APP_USER.USER_ID"],
                name="fk_BIC_CCD_MAKER_CHECKER_SUBMISSION_SUBMITTED_BY",
            ),
            sa.PrimaryKeyConstraint("SUBMISSION_ID", name="pk_BIC_CCD_MAKER_CHECKER_SUBMISSION"),
        )

    if not _table_exists("BIC_CCD_APPROVAL_AUDIT_TRAIL"):
        op.create_table(
            "BIC_CCD_APPROVAL_AUDIT_TRAIL",
            sa.Column("AUDIT_ID", sa.Integer(), sa.Identity(start=1), nullable=False),
            sa.Column("STATUS_ID", sa.Integer(), nullable=False),
            sa.Column("ACTION", sa.String(30), nullable=False),
            sa.Column("PERFORMED_BY", sa.Integer(), nullable=False),
            sa.Column("PERFORMED_DT", sa.DateTime(), nullable=False),
            sa.Column("COMMENTS", sa.String(2000), nullable=True),
            sa.Column("PREVIOUS_STATUS", sa.String(20), nullable=True),
            sa.Column("NEW_STATUS", sa.String(20), nullable=True),
            sa.Column("IP_ADDRESS", sa.String(50), nullable=True),
            sa.Column("CREATED_DT", sa.DateTime(), nullable=False),
            sa.Column("UPDATED_DT", sa.DateTime(), nullable=False),
            sa.Column("CREATED_BY", sa.String(50), nullable=False),
            sa.Column("UPDATED_BY", sa.String(50), nullable=False),
            sa.ForeignKeyConstraint(
                ["STATUS_ID"], ["BIC_CCD_KRI_CONTROL_STATUS_TRACKER.ID"],
                name="fk_BIC_CCD_APPROVAL_AUDIT_TRAIL_STATUS_ID",
            ),
            sa.ForeignKeyConstraint(
                ["PERFORMED_BY"], ["BIC_CCD_APP_USER.USER_ID"],
                name="fk_BIC_CCD_APPROVAL_AUDIT_TRAIL_PERFORMED_BY",
            ),
            sa.PrimaryKeyConstraint("AUDIT_ID", name="pk_BIC_CCD_APPROVAL_AUDIT_TRAIL"),
        )

    if not _table_exists("BIC_CCD_VARIANCE_SUBMISSION"):
        op.create_table(
            "BIC_CCD_VARIANCE_SUBMISSION",
            sa.Column("VARIANCE_ID", sa.Integer(), sa.Identity(start=1), nullable=False),
            sa.Column("METRIC_ID", sa.Integer(), nullable=False),
            sa.Column("STATUS_ID", sa.Integer(), nullable=True),
            sa.Column("VARIANCE_PCT", sa.Float(), nullable=False),
            sa.Column("COMMENTARY", sa.Text(), nullable=False),
            sa.Column("SUBMITTED_BY", sa.Integer(), nullable=False),
            sa.Column("SUBMITTED_DT", sa.DateTime(), nullable=False),
            sa.Column("REVIEW_STATUS", sa.String(20), nullable=False),
            sa.Column("REVIEWED_BY", sa.Integer(), nullable=True),
            sa.Column("REVIEWED_DT", sa.DateTime(), nullable=True),
            sa.Column("REVIEW_COMMENTS", sa.String(2000), nullable=True),
            sa.Column("CREATED_DT", sa.DateTime(), nullable=False),
            sa.Column("UPDATED_DT", sa.DateTime(), nullable=False),
            sa.Column("CREATED_BY", sa.String(50), nullable=False),
            sa.Column("UPDATED_BY", sa.String(50), nullable=False),
            sa.ForeignKeyConstraint(
                ["METRIC_ID"], ["BIC_CCD_KRI_METRIC.METRIC_ID"],
                name="fk_BIC_CCD_VARIANCE_SUBMISSION_METRIC_ID",
            ),
            sa.ForeignKeyConstraint(
                ["STATUS_ID"], ["BIC_CCD_KRI_CONTROL_STATUS_TRACKER.ID"],
                name="fk_BIC_CCD_VARIANCE_SUBMISSION_STATUS_ID",
            ),
            sa.ForeignKeyConstraint(
                ["SUBMITTED_BY"], ["BIC_CCD_APP_USER.USER_ID"],
                name="fk_BIC_CCD_VARIANCE_SUBMISSION_SUBMITTED_BY",
            ),
            sa.ForeignKeyConstraint(
                ["REVIEWED_BY"], ["BIC_CCD_APP_USER.USER_ID"],
                name="fk_BIC_CCD_VARIANCE_SUBMISSION_REVIEWED_BY",
            ),
            sa.PrimaryKeyConstraint("VARIANCE_ID", name="pk_BIC_CCD_VARIANCE_SUBMISSION"),
        )

    if not _table_exists("BIC_CCD_KRI_EMAIL_ITERATION"):
        op.create_table(
            "BIC_CCD_KRI_EMAIL_ITERATION",
            sa.Column("ITER_ID", sa.Integer(), sa.Identity(start=1), nullable=False),
            sa.Column("KRI_ID", sa.Integer(), nullable=False),
            sa.Column("PERIOD_YEAR", sa.Integer(), nullable=False),
            sa.Column("PERIOD_MONTH", sa.Integer(), nullable=False),
            sa.Column("CURRENT_ITER", sa.Integer(), nullable=False),
            sa.Column("LAST_UPDATED", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(
                ["KRI_ID"], ["BIC_CCD_KRI_CONFIG.KRI_ID"],
                name="fk_BIC_CCD_KRI_EMAIL_ITERATION_KRI_ID_BIC_CCD_KRI_CONFIG",
            ),
            sa.PrimaryKeyConstraint("ITER_ID", name="pk_BIC_CCD_KRI_EMAIL_ITERATION"),
            sa.UniqueConstraint(
                "KRI_ID", "PERIOD_YEAR", "PERIOD_MONTH",
                name="uq_bic_ccd_kri_iter_period",
            ),
        )

    if not _table_exists("BIC_CCD_KRI_AUDIT_SUMMARY"):
        op.create_table(
            "BIC_CCD_KRI_AUDIT_SUMMARY",
            sa.Column("SUMMARY_ID", sa.Integer(), sa.Identity(start=1), nullable=False),
            sa.Column("KRI_ID", sa.Integer(), nullable=False),
            sa.Column("PERIOD_YEAR", sa.Integer(), nullable=False),
            sa.Column("PERIOD_MONTH", sa.Integer(), nullable=False),
            sa.Column("S3_PATH", sa.String(1000), nullable=False),
            sa.Column("GENERATED_DT", sa.DateTime(), nullable=False),
            sa.Column("GENERATED_BY", sa.Integer(), nullable=True),
            sa.Column("L3_APPROVER_NAME", sa.String(200), nullable=True),
            sa.Column("FINAL_STATUS", sa.String(30), nullable=False),
            sa.Column("TOTAL_ITERATIONS", sa.Integer(), nullable=False),
            sa.Column("TOTAL_EVIDENCES", sa.Integer(), nullable=False),
            sa.Column("TOTAL_EMAILS", sa.Integer(), nullable=False),
            sa.ForeignKeyConstraint(
                ["KRI_ID"], ["BIC_CCD_KRI_CONFIG.KRI_ID"],
                name="fk_BIC_CCD_KRI_AUDIT_SUMMARY_KRI_ID_BIC_CCD_KRI_CONFIG",
            ),
            sa.ForeignKeyConstraint(
                ["GENERATED_BY"], ["BIC_CCD_APP_USER.USER_ID"],
                name="fk_BIC_CCD_KRI_AUDIT_SUMMARY_GENERATED_BY_BIC_CCD_APP_USER",
            ),
            sa.PrimaryKeyConstraint("SUMMARY_ID", name="pk_BIC_CCD_KRI_AUDIT_SUMMARY"),
        )

    # ── Tier 5: depend on KRI_EVIDENCE ───────────────────────────────────────

    if not _table_exists("BIC_CCD_KRI_CONTROL_EVIDENCE_AUDIT"):
        op.create_table(
            "BIC_CCD_KRI_CONTROL_EVIDENCE_AUDIT",
            sa.Column("ID", sa.Integer(), sa.Identity(start=1), nullable=False),
            sa.Column("TRACKER_ID", sa.Integer(), nullable=False),
            sa.Column("METRIC_VALUE", sa.Float(), nullable=True),
            sa.Column("RAG_STATUS", sa.String(10), nullable=True),
            sa.Column("ASSIGNED_TO", sa.Integer(), nullable=True),
            sa.Column("STATUS_ID", sa.Integer(), nullable=True),
            sa.Column("FILE_IDS", sa.Text(), nullable=True),
            sa.Column("SHORT_COMMENT", sa.String(200), nullable=True),
            sa.Column("LONG_COMMENT", sa.Text(), nullable=True),
            sa.Column("VERSION_COMMENT", sa.String(500), nullable=True),
            sa.Column("CREATED_BY", sa.String(50), nullable=False),
            sa.Column("CREATED_DT", sa.DateTime(), nullable=False),
            sa.Column("VERSION_NUMBER", sa.Integer(), nullable=True),
            sa.Column("S3_KEY", sa.String(500), nullable=True),
            sa.Column("FILE_SIZE_BYTES", sa.Integer(), nullable=True),
            sa.Column("ACTION", sa.String(20), nullable=True),
            sa.Column("PERFORMED_BY", sa.Integer(), nullable=True),
            sa.Column("PERFORMED_DT", sa.DateTime(), nullable=True),
            sa.Column("COMMENTS", sa.String(500), nullable=True),
            sa.ForeignKeyConstraint(
                ["TRACKER_ID"], ["BIC_CCD_KRI_EVIDENCE.ID"],
                name="fk_BIC_CCD_KRI_CTRL_EVID_AUDIT_TRACKER_ID_BIC_CCD_KRI_EVIDENCE",
            ),
            sa.ForeignKeyConstraint(
                ["STATUS_ID"], ["BIC_CCD_KRI_STATUS.STATUS_ID"],
                name="fk_BIC_CCD_KRI_CTRL_EVID_AUDIT_STATUS_ID_BIC_CCD_KRI_STATUS",
            ),
            sa.ForeignKeyConstraint(
                ["ASSIGNED_TO"], ["BIC_CCD_APP_USER.USER_ID"],
                name="fk_BIC_CCD_KRI_CTRL_EVID_AUDIT_ASSIGNED_TO_BIC_CCD_APP_USER",
            ),
            sa.ForeignKeyConstraint(
                ["PERFORMED_BY"], ["BIC_CCD_APP_USER.USER_ID"],
                name="fk_BIC_CCD_KRI_CTRL_EVID_AUDIT_PERFORMED_BY_BIC_CCD_APP_USER",
            ),
            sa.PrimaryKeyConstraint("ID", name="pk_BIC_CCD_KRI_CONTROL_EVIDENCE_AUDIT"),
        )

    if not _table_exists("BIC_CCD_KRI_EVIDENCE_METADATA"):
        op.create_table(
            "BIC_CCD_KRI_EVIDENCE_METADATA",
            sa.Column("EVIDENCE_ID", sa.Integer(), sa.Identity(start=1), nullable=False),
            sa.Column("KRI_ID", sa.Integer(), nullable=False),
            sa.Column("CONTROL_ID_STR", sa.String(100), nullable=True),
            sa.Column("REGION_CODE", sa.String(20), nullable=True),
            sa.Column("PERIOD_YEAR", sa.Integer(), nullable=False),
            sa.Column("PERIOD_MONTH", sa.Integer(), nullable=False),
            sa.Column("ITERATION", sa.Integer(), nullable=True),
            sa.Column("EVIDENCE_TYPE", sa.String(20), nullable=False),
            sa.Column("ACTION", sa.String(50), nullable=True),
            sa.Column("SENDER", sa.String(500), nullable=True),
            sa.Column("RECEIVER", sa.String(500), nullable=True),
            sa.Column("FILE_NAME", sa.String(500), nullable=False),
            sa.Column("S3_OBJECT_PATH", sa.String(1000), nullable=False),
            sa.Column("UPLOADED_BY", sa.Integer(), nullable=True),
            sa.Column("NOTES", sa.Text(), nullable=True),
            sa.Column("IS_UNMAPPED", sa.Boolean(), nullable=False),
            sa.Column("EMAIL_UUID", sa.String(100), nullable=True),
            sa.Column("CREATED_DT", sa.DateTime(), nullable=False),
            sa.Column("UPDATED_DT", sa.DateTime(), nullable=False),
            sa.Column("CREATED_BY", sa.String(50), nullable=False),
            sa.Column("UPDATED_BY", sa.String(50), nullable=False),
            sa.ForeignKeyConstraint(
                ["KRI_ID"], ["BIC_CCD_KRI_CONFIG.KRI_ID"],
                name="fk_BIC_CCD_KRI_EVIDENCE_METADATA_KRI_ID_BIC_CCD_KRI_CONFIG",
            ),
            sa.ForeignKeyConstraint(
                ["UPLOADED_BY"], ["BIC_CCD_APP_USER.USER_ID"],
                name="fk_BIC_CCD_KRI_EVIDENCE_METADATA_UPLOADED_BY_BIC_CCD_APP_USER",
            ),
            sa.PrimaryKeyConstraint("EVIDENCE_ID", name="pk_BIC_CCD_KRI_EVIDENCE_METADATA"),
        )
        op.create_index(
            "idx_bic_ccd_evmeta_kri_period",
            "BIC_CCD_KRI_EVIDENCE_METADATA", ["KRI_ID", "PERIOD_YEAR", "PERIOD_MONTH"],
        )

    # ── Deferred FKs on EMAIL_AUDIT (targets must exist first) ───────────────

    if not _constraint_exists(
        "fk_BIC_CCD_EMAIL_AUDIT_RELATED_KRI_ID_BIC_CCD_KRI_CONFIG",
        "BIC_CCD_EMAIL_AUDIT",
    ):
        op.create_foreign_key(
            "fk_BIC_CCD_EMAIL_AUDIT_RELATED_KRI_ID_BIC_CCD_KRI_CONFIG",
            "BIC_CCD_EMAIL_AUDIT", "BIC_CCD_KRI_CONFIG",
            ["RELATED_KRI_ID"], ["KRI_ID"],
        )

    if not _constraint_exists(
        "fk_BIC_CCD_EMAIL_AUDIT_RELATED_STATUS_ID_BIC_CCD_KRI_CTRL_STAT_TRK",
        "BIC_CCD_EMAIL_AUDIT",
    ):
        op.create_foreign_key(
            "fk_BIC_CCD_EMAIL_AUDIT_RELATED_STATUS_ID_BIC_CCD_KRI_CTRL_STAT_TRK",
            "BIC_CCD_EMAIL_AUDIT", "BIC_CCD_KRI_CONTROL_STATUS_TRACKER",
            ["RELATED_STATUS_ID"], ["ID"],
        )


def downgrade() -> None:
    # Drop deferred FKs first
    if _constraint_exists(
        "fk_BIC_CCD_EMAIL_AUDIT_RELATED_STATUS_ID_BIC_CCD_KRI_CTRL_STAT_TRK",
        "BIC_CCD_EMAIL_AUDIT",
    ):
        op.drop_constraint(
            "fk_BIC_CCD_EMAIL_AUDIT_RELATED_STATUS_ID_BIC_CCD_KRI_CTRL_STAT_TRK",
            "BIC_CCD_EMAIL_AUDIT", type_="foreignkey",
        )
    if _constraint_exists(
        "fk_BIC_CCD_EMAIL_AUDIT_RELATED_KRI_ID_BIC_CCD_KRI_CONFIG",
        "BIC_CCD_EMAIL_AUDIT",
    ):
        op.drop_constraint(
            "fk_BIC_CCD_EMAIL_AUDIT_RELATED_KRI_ID_BIC_CCD_KRI_CONFIG",
            "BIC_CCD_EMAIL_AUDIT", type_="foreignkey",
        )

    # Drop in reverse FK order
    for table in [
        "BIC_CCD_KRI_EVIDENCE_METADATA",
        "BIC_CCD_KRI_CONTROL_EVIDENCE_AUDIT",
        "BIC_CCD_KRI_AUDIT_SUMMARY",
        "BIC_CCD_KRI_EMAIL_ITERATION",
        "BIC_CCD_VARIANCE_SUBMISSION",
        "BIC_CCD_APPROVAL_AUDIT_TRAIL",
        "BIC_CCD_MAKER_CHECKER_SUBMISSION",
        "BIC_CCD_KRI_ASSIGNMENT_AUDIT",
        "BIC_CCD_KRI_COMMENT",
        "BIC_CCD_KRI_EVIDENCE",
        "BIC_CCD_SCORECARD_ACTIVITY_LOG",
        "BIC_CCD_SCORECARD_APPROVER",
        "BIC_CCD_KRI_METRIC",
        "BIC_CCD_KRI_ASSIGNMENT_TRACKER",
        "BIC_CCD_KRI_DATA_SOURCE_STATUS_TRACKER",
        "BIC_CCD_KRI_CONTROL_STATUS_TRACKER",
        "BIC_CCD_SCORECARD",
        "BIC_CCD_KRI_APPROVAL_LOG",
        "BIC_CCD_KRI_BLUESHEET",
        "BIC_CCD_APPROVAL_ASSIGNMENT_RULE",
        "BIC_CCD_KRI_USER_ROLE",
        "BIC_CCD_KRI_DATA_SOURCE_MAPPING",
        "BIC_CCD_KRI_CONFIGURATION",
        "BIC_CCD_SAVED_VIEW",
        "BIC_CCD_NOTIFICATION",
        "BIC_CCD_ESCALATION_CONFIG",
        "BIC_CCD_USER_ROLE_MAPPING",
        "BIC_CCD_CASE_FILE",
        "BIC_CCD_KRI_CONFIG",
        "BIC_CCD_EMAIL_AUDIT",
        "BIC_CCD_APP_USER",
        "BIC_CCD_CASE",
        "BIC_CCD_SHED_LOCK",
        "BIC_CCD_ROLE_REGION_MAPPING",
        "BIC_CCD_KRI_STATUS",
        "BIC_CCD_KRI_CONTROL",
        "BIC_CCD_KRI_CATEGORY",
        "BIC_CCD_REGION",
    ]:
        if _table_exists(table):
            op.drop_table(table)
