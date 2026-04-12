"""Phase 1 + BIC alignment — extra tables and app-specific columns

Revision ID: b1c2d3e4f5a6
Revises: a9dbeb296e9b
Create Date: 2026-04-07

What this migration does
------------------------
The 23 BIC_ tables already exist in the Oracle target database.
This migration creates ONLY the extra tables our application needs
that are NOT in the BIC 23, and adds app-specific extra columns
to existing BIC tables.

Extra tables created:
  APP_USER, USER_ROLE_MAPPING, KRI_CONFIGURATION,
  MAKER_CHECKER_SUBMISSION, APPROVAL_AUDIT_TRAIL,
  VARIANCE_SUBMISSION, ESCALATION_CONFIG,
  NOTIFICATION, APPROVAL_ASSIGNMENT_RULE, SAVED_VIEW

App-specific columns added to BIC tables:
  BIC_REGION          : REGION_CODE, IS_ACTIVE
  BIC_KRI_CATEGORY    : CATEGORY_CODE, DESCRIPTION, IS_ACTIVE
  BIC_KRI_CONTROL     : DIMENSION_CODE, DISPLAY_ORDER, DESCRIPTION, IS_ACTIVE
  BIC_KRI_CONFIG      : KRI_CODE, DESCRIPTION, RISK_LEVEL, FRAMEWORK,
                        IS_DCRM, ONBOARDED_DT
  BIC_KRI_CONTROL_STATUS_TRACKER : STATUS, RAG_STATUS, SLA_DUE_DT, SLA_MET,
                        COMPLETED_DT, CURRENT_APPROVER, APPROVAL_LEVEL, RETRY_COUNT
  BIC_KRI_EVIDENCE    : FILE_TYPE, FILE_SIZE_BYTES, S3_BUCKET, VERSION_NUMBER,
                        IS_LOCKED, LOCKED_DT, LOCKED_BY, UPLOADED_BY,
                        UPLOADED_DT, METADATA_JSON, REGION_ID
  BIC_KRI_CONTROL_EVIDENCE_AUDIT : VERSION_NUMBER, S3_KEY, FILE_SIZE_BYTES,
                        ACTION, PERFORMED_BY, PERFORMED_DT, COMMENTS
  BIC_KRI_DATA_SOURCE_MAPPING : MAPPING_TYPE, SOURCE_TYPE, CONNECTION_INFO,
                        QUERY_TEMPLATE, SCHEDULE_CRON, IS_ACTIVE
  BIC_KRI_ASSIGNMENT_TRACKER  : IS_ACTIVE
  BIC_SCORECARD       : SUBMITTED_DT, KRI_ID, CREATED_BY_USER_ID
  BIC_EMAIL_AUDIT     : RECIPIENT_NAME, SENT_DT, RELATED_KRI_ID,
                        RELATED_STATUS_ID
  BIC_SHED_LOCK       : IS_LOCKED

Safe to run on a clean dev DB (SQLite) where create_all has not yet run.
All add_column calls are nullable / have server defaults to avoid
breaking existing Oracle rows.
"""
from typing import Sequence, Union
import sqlalchemy as sa
from alembic import op

revision: str = 'b1c2d3e4f5a6'
down_revision: Union[str, None] = 'a9dbeb296e9b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _add_col(table, col):
    """add_column wrapper — silently skips if column already exists (idempotent)."""
    try:
        op.add_column(table, col)
    except Exception:
        pass


def upgrade() -> None:
    # ── Extra tables ─────────────────────────────────────────

    op.create_table(
        'APP_USER',
        sa.Column('USER_ID', sa.Integer(), sa.Identity(start=1), nullable=False),
        sa.Column('SOE_ID', sa.String(20), nullable=False, unique=True),
        sa.Column('FULL_NAME', sa.String(200), nullable=False),
        sa.Column('EMAIL', sa.String(200), nullable=False),
        sa.Column('DEPARTMENT', sa.String(100), nullable=True),
        sa.Column('IS_ACTIVE', sa.Boolean(), nullable=False, server_default='1'),
        sa.Column('LAST_LOGIN_DT', sa.DateTime(), nullable=True),
        sa.Column('CREATED_DT', sa.DateTime(), nullable=False),
        sa.Column('UPDATED_DT', sa.DateTime(), nullable=False),
        sa.Column('CREATED_BY', sa.String(50), nullable=False, server_default='SYSTEM'),
        sa.Column('UPDATED_BY', sa.String(50), nullable=False, server_default='SYSTEM'),
        sa.PrimaryKeyConstraint('USER_ID'),
    )

    op.create_table(
        'USER_ROLE_MAPPING',
        sa.Column('MAPPING_ID', sa.Integer(), sa.Identity(start=1), nullable=False),
        sa.Column('USER_ID', sa.Integer(), nullable=False),
        sa.Column('ROLE_CODE', sa.String(30), nullable=False),
        sa.Column('REGION_ID', sa.Integer(), nullable=True),
        sa.Column('IS_ACTIVE', sa.Boolean(), nullable=False, server_default='1'),
        sa.Column('EFFECTIVE_FROM', sa.Date(), nullable=False),
        sa.Column('EFFECTIVE_TO', sa.Date(), nullable=True),
        sa.Column('CREATED_DT', sa.DateTime(), nullable=False),
        sa.Column('UPDATED_DT', sa.DateTime(), nullable=False),
        sa.Column('CREATED_BY', sa.String(50), nullable=False, server_default='SYSTEM'),
        sa.Column('UPDATED_BY', sa.String(50), nullable=False, server_default='SYSTEM'),
        sa.PrimaryKeyConstraint('MAPPING_ID'),
        sa.ForeignKeyConstraint(['USER_ID'], ['APP_USER.USER_ID']),
        sa.ForeignKeyConstraint(['REGION_ID'], ['BIC_REGION.REGION_ID']),
        sa.UniqueConstraint('USER_ID', 'ROLE_CODE', 'REGION_ID', name='uq_user_role_region'),
    )

    op.create_table(
        'KRI_CONFIGURATION',
        sa.Column('CONFIG_ID', sa.Integer(), sa.Identity(start=1), nullable=False),
        sa.Column('KRI_ID', sa.Integer(), nullable=False),
        sa.Column('CONTROL_ID', sa.Integer(), nullable=False),
        sa.Column('SLA_DAYS', sa.Integer(), nullable=False, server_default='3'),
        sa.Column('VARIANCE_THRESHOLD', sa.Float(), nullable=False, server_default='10.0'),
        sa.Column('RAG_GREEN_MAX', sa.Float(), nullable=True),
        sa.Column('RAG_AMBER_MAX', sa.Float(), nullable=True),
        sa.Column('REQUIRES_EVIDENCE', sa.Boolean(), nullable=False, server_default='1'),
        sa.Column('REQUIRES_APPROVAL', sa.Boolean(), nullable=False, server_default='1'),
        sa.Column('FREEZE_DAY', sa.Integer(), nullable=False, server_default='15'),
        sa.Column('SLA_START_DAY', sa.Integer(), nullable=True),
        sa.Column('SLA_END_DAY', sa.Integer(), nullable=True),
        sa.Column('RAG_THRESHOLDS', sa.Text(), nullable=True),
        sa.Column('IS_ACTIVE', sa.Boolean(), nullable=False, server_default='1'),
        sa.Column('CREATED_DT', sa.DateTime(), nullable=False),
        sa.Column('UPDATED_DT', sa.DateTime(), nullable=False),
        sa.Column('CREATED_BY', sa.String(50), nullable=False, server_default='SYSTEM'),
        sa.Column('UPDATED_BY', sa.String(50), nullable=False, server_default='SYSTEM'),
        sa.PrimaryKeyConstraint('CONFIG_ID'),
        sa.ForeignKeyConstraint(['KRI_ID'], ['BIC_KRI_CONFIG.KRI_ID']),
        sa.ForeignKeyConstraint(['CONTROL_ID'], ['BIC_KRI_CONTROL.CONTROL_ID']),
        sa.UniqueConstraint('KRI_ID', 'CONTROL_ID', name='uq_kri_dim_cfg'),
    )

    op.create_table(
        'MAKER_CHECKER_SUBMISSION',
        sa.Column('SUBMISSION_ID', sa.Integer(), sa.Identity(start=1), nullable=False),
        sa.Column('STATUS_ID', sa.Integer(), nullable=False),
        sa.Column('EVIDENCE_ID', sa.Integer(), nullable=True),
        sa.Column('SUBMITTED_BY', sa.Integer(), nullable=False),
        sa.Column('SUBMITTED_DT', sa.DateTime(), nullable=False),
        sa.Column('SUBMISSION_NOTES', sa.Text(), nullable=True),
        sa.Column('L1_APPROVER_ID', sa.Integer(), nullable=True),
        sa.Column('L1_ACTION', sa.String(20), nullable=True),
        sa.Column('L1_ACTION_DT', sa.DateTime(), nullable=True),
        sa.Column('L1_COMMENTS', sa.String(2000), nullable=True),
        sa.Column('L2_APPROVER_ID', sa.Integer(), nullable=True),
        sa.Column('L2_ACTION', sa.String(20), nullable=True),
        sa.Column('L2_ACTION_DT', sa.DateTime(), nullable=True),
        sa.Column('L2_COMMENTS', sa.String(2000), nullable=True),
        sa.Column('L3_APPROVER_ID', sa.Integer(), nullable=True),
        sa.Column('L3_ACTION', sa.String(20), nullable=True),
        sa.Column('L3_ACTION_DT', sa.DateTime(), nullable=True),
        sa.Column('L3_COMMENTS', sa.String(2000), nullable=True),
        sa.Column('FINAL_STATUS', sa.String(20), nullable=False, server_default='PENDING'),
        sa.Column('CREATED_DT', sa.DateTime(), nullable=False),
        sa.Column('UPDATED_DT', sa.DateTime(), nullable=False),
        sa.Column('CREATED_BY', sa.String(50), nullable=False, server_default='SYSTEM'),
        sa.Column('UPDATED_BY', sa.String(50), nullable=False, server_default='SYSTEM'),
        sa.PrimaryKeyConstraint('SUBMISSION_ID'),
        sa.ForeignKeyConstraint(['STATUS_ID'], ['BIC_KRI_CONTROL_STATUS_TRACKER.ID']),
        sa.ForeignKeyConstraint(['EVIDENCE_ID'], ['BIC_KRI_EVIDENCE.ID']),
        sa.ForeignKeyConstraint(['SUBMITTED_BY'], ['APP_USER.USER_ID']),
    )

    op.create_table(
        'APPROVAL_AUDIT_TRAIL',
        sa.Column('AUDIT_ID', sa.Integer(), sa.Identity(start=1), nullable=False),
        sa.Column('STATUS_ID', sa.Integer(), nullable=False),
        sa.Column('ACTION', sa.String(30), nullable=False),
        sa.Column('PERFORMED_BY', sa.Integer(), nullable=False),
        sa.Column('PERFORMED_DT', sa.DateTime(), nullable=False),
        sa.Column('COMMENTS', sa.String(2000), nullable=True),
        sa.Column('PREVIOUS_STATUS', sa.String(20), nullable=True),
        sa.Column('NEW_STATUS', sa.String(20), nullable=True),
        sa.Column('IP_ADDRESS', sa.String(50), nullable=True),
        sa.Column('CREATED_DT', sa.DateTime(), nullable=False),
        sa.Column('UPDATED_DT', sa.DateTime(), nullable=False),
        sa.Column('CREATED_BY', sa.String(50), nullable=False, server_default='SYSTEM'),
        sa.Column('UPDATED_BY', sa.String(50), nullable=False, server_default='SYSTEM'),
        sa.PrimaryKeyConstraint('AUDIT_ID'),
        sa.ForeignKeyConstraint(['STATUS_ID'], ['BIC_KRI_CONTROL_STATUS_TRACKER.ID']),
        sa.ForeignKeyConstraint(['PERFORMED_BY'], ['APP_USER.USER_ID']),
    )

    op.create_table(
        'VARIANCE_SUBMISSION',
        sa.Column('VARIANCE_ID', sa.Integer(), sa.Identity(start=1), nullable=False),
        sa.Column('METRIC_ID', sa.Integer(), nullable=False),
        sa.Column('STATUS_ID', sa.Integer(), nullable=True),
        sa.Column('VARIANCE_PCT', sa.Float(), nullable=False),
        sa.Column('COMMENTARY', sa.Text(), nullable=False),
        sa.Column('SUBMITTED_BY', sa.Integer(), nullable=False),
        sa.Column('SUBMITTED_DT', sa.DateTime(), nullable=False),
        sa.Column('REVIEW_STATUS', sa.String(20), nullable=False, server_default='PENDING'),
        sa.Column('REVIEWED_BY', sa.Integer(), nullable=True),
        sa.Column('REVIEWED_DT', sa.DateTime(), nullable=True),
        sa.Column('REVIEW_COMMENTS', sa.String(2000), nullable=True),
        sa.Column('CREATED_DT', sa.DateTime(), nullable=False),
        sa.Column('UPDATED_DT', sa.DateTime(), nullable=False),
        sa.Column('CREATED_BY', sa.String(50), nullable=False, server_default='SYSTEM'),
        sa.Column('UPDATED_BY', sa.String(50), nullable=False, server_default='SYSTEM'),
        sa.PrimaryKeyConstraint('VARIANCE_ID'),
        sa.ForeignKeyConstraint(['METRIC_ID'], ['BIC_KRI_METRIC.METRIC_ID']),
    )

    op.create_table(
        'ESCALATION_CONFIG',
        sa.Column('CONFIG_ID', sa.Integer(), sa.Identity(start=1), nullable=False),
        sa.Column('REGION_ID', sa.Integer(), nullable=True),
        sa.Column('ESCALATION_TYPE', sa.String(30), nullable=False),
        sa.Column('THRESHOLD_HOURS', sa.Integer(), nullable=False, server_default='72'),
        sa.Column('REMINDER_HOURS', sa.Integer(), nullable=False, server_default='24'),
        sa.Column('MAX_REMINDERS', sa.Integer(), nullable=False, server_default='3'),
        sa.Column('ESCALATE_TO_ROLE', sa.String(30), nullable=False),
        sa.Column('EMAIL_TEMPLATE', sa.Text(), nullable=True),
        sa.Column('IS_ACTIVE', sa.Boolean(), nullable=False, server_default='1'),
        sa.Column('CREATED_DT', sa.DateTime(), nullable=False),
        sa.Column('UPDATED_DT', sa.DateTime(), nullable=False),
        sa.Column('CREATED_BY', sa.String(50), nullable=False, server_default='SYSTEM'),
        sa.Column('UPDATED_BY', sa.String(50), nullable=False, server_default='SYSTEM'),
        sa.PrimaryKeyConstraint('CONFIG_ID'),
        sa.ForeignKeyConstraint(['REGION_ID'], ['BIC_REGION.REGION_ID']),
    )

    op.create_table(
        'NOTIFICATION',
        sa.Column('NOTIFICATION_ID', sa.Integer(), sa.Identity(start=1), nullable=False),
        sa.Column('USER_ID', sa.Integer(), nullable=False),
        sa.Column('TITLE', sa.String(300), nullable=False),
        sa.Column('MESSAGE', sa.String(2000), nullable=False),
        sa.Column('NOTIFICATION_TYPE', sa.String(30), nullable=True),
        sa.Column('IS_READ', sa.Boolean(), nullable=False, server_default='0'),
        sa.Column('LINK_URL', sa.String(500), nullable=True),
        sa.Column('CREATED_DT', sa.DateTime(), nullable=False),
        sa.Column('UPDATED_DT', sa.DateTime(), nullable=False),
        sa.Column('CREATED_BY', sa.String(50), nullable=False, server_default='SYSTEM'),
        sa.Column('UPDATED_BY', sa.String(50), nullable=False, server_default='SYSTEM'),
        sa.PrimaryKeyConstraint('NOTIFICATION_ID'),
        sa.ForeignKeyConstraint(['USER_ID'], ['APP_USER.USER_ID']),
    )

    op.create_table(
        'APPROVAL_ASSIGNMENT_RULE',
        sa.Column('RULE_ID', sa.Integer(), sa.Identity(start=1), nullable=False),
        sa.Column('ROLE_CODE', sa.String(20), nullable=False),
        sa.Column('USER_ID', sa.Integer(), nullable=True),
        sa.Column('REGION_ID', sa.Integer(), nullable=True),
        sa.Column('KRI_ID', sa.Integer(), nullable=True),
        sa.Column('CATEGORY_ID', sa.Integer(), nullable=True),
        sa.Column('PRIORITY', sa.Integer(), nullable=False, server_default='100'),
        sa.Column('IS_ACTIVE', sa.Boolean(), nullable=False, server_default='1'),
        sa.Column('CREATED_DT', sa.DateTime(), nullable=False),
        sa.Column('UPDATED_DT', sa.DateTime(), nullable=False),
        sa.Column('CREATED_BY', sa.String(50), nullable=False, server_default='SYSTEM'),
        sa.Column('UPDATED_BY', sa.String(50), nullable=False, server_default='SYSTEM'),
        sa.PrimaryKeyConstraint('RULE_ID'),
    )

    op.create_table(
        'SAVED_VIEW',
        sa.Column('VIEW_ID', sa.Integer(), sa.Identity(start=1), nullable=False),
        sa.Column('USER_ID', sa.Integer(), nullable=False),
        sa.Column('VIEW_NAME', sa.String(200), nullable=False),
        sa.Column('VIEW_TYPE', sa.String(30), nullable=False),
        sa.Column('FILTERS_JSON', sa.Text(), nullable=True),
        sa.Column('IS_DEFAULT', sa.Boolean(), nullable=False, server_default='0'),
        sa.Column('CREATED_DT', sa.DateTime(), nullable=False),
        sa.Column('UPDATED_DT', sa.DateTime(), nullable=False),
        sa.Column('CREATED_BY', sa.String(50), nullable=False, server_default='SYSTEM'),
        sa.Column('UPDATED_BY', sa.String(50), nullable=False, server_default='SYSTEM'),
        sa.PrimaryKeyConstraint('VIEW_ID'),
        sa.ForeignKeyConstraint(['USER_ID'], ['APP_USER.USER_ID']),
    )

    # ── App-specific extra columns on BIC tables ─────────────
    # BIC_REGION
    _add_col('BIC_REGION', sa.Column('REGION_CODE', sa.String(10), nullable=True))
    _add_col('BIC_REGION', sa.Column('IS_ACTIVE', sa.Boolean(), nullable=True, server_default='1'))

    # BIC_KRI_CATEGORY
    _add_col('BIC_KRI_CATEGORY', sa.Column('CATEGORY_CODE', sa.String(30), nullable=True))
    _add_col('BIC_KRI_CATEGORY', sa.Column('DESCRIPTION', sa.String(500), nullable=True))
    _add_col('BIC_KRI_CATEGORY', sa.Column('IS_ACTIVE', sa.Boolean(), nullable=True, server_default='1'))

    # BIC_KRI_CONTROL
    _add_col('BIC_KRI_CONTROL', sa.Column('DIMENSION_CODE', sa.String(30), nullable=True))
    _add_col('BIC_KRI_CONTROL', sa.Column('DISPLAY_ORDER', sa.Integer(), nullable=True, server_default='0'))
    _add_col('BIC_KRI_CONTROL', sa.Column('DESCRIPTION', sa.String(500), nullable=True))
    _add_col('BIC_KRI_CONTROL', sa.Column('IS_ACTIVE', sa.Boolean(), nullable=True, server_default='1'))

    # BIC_KRI_CONFIG
    _add_col('BIC_KRI_CONFIG', sa.Column('KRI_CODE', sa.String(30), nullable=True))
    _add_col('BIC_KRI_CONFIG', sa.Column('DESCRIPTION', sa.Text(), nullable=True))
    _add_col('BIC_KRI_CONFIG', sa.Column('RISK_LEVEL', sa.String(20), nullable=True, server_default='MEDIUM'))
    _add_col('BIC_KRI_CONFIG', sa.Column('FRAMEWORK', sa.String(100), nullable=True))
    _add_col('BIC_KRI_CONFIG', sa.Column('IS_DCRM', sa.Boolean(), nullable=False, server_default='0'))
    _add_col('BIC_KRI_CONFIG', sa.Column('ONBOARDED_DT', sa.DateTime(), nullable=True))

    # BIC_KRI_CONTROL_STATUS_TRACKER
    _add_col('BIC_KRI_CONTROL_STATUS_TRACKER', sa.Column('STATUS', sa.String(30), nullable=True, server_default='NOT_STARTED'))
    _add_col('BIC_KRI_CONTROL_STATUS_TRACKER', sa.Column('RAG_STATUS', sa.String(10), nullable=True))
    _add_col('BIC_KRI_CONTROL_STATUS_TRACKER', sa.Column('SLA_DUE_DT', sa.DateTime(), nullable=True))
    _add_col('BIC_KRI_CONTROL_STATUS_TRACKER', sa.Column('SLA_MET', sa.Boolean(), nullable=True))
    _add_col('BIC_KRI_CONTROL_STATUS_TRACKER', sa.Column('COMPLETED_DT', sa.DateTime(), nullable=True))
    _add_col('BIC_KRI_CONTROL_STATUS_TRACKER', sa.Column('CURRENT_APPROVER', sa.Integer(), nullable=True))
    _add_col('BIC_KRI_CONTROL_STATUS_TRACKER', sa.Column('APPROVAL_LEVEL', sa.String(10), nullable=True))
    _add_col('BIC_KRI_CONTROL_STATUS_TRACKER', sa.Column('RETRY_COUNT', sa.Integer(), nullable=True, server_default='0'))

    # BIC_KRI_EVIDENCE
    _add_col('BIC_KRI_EVIDENCE', sa.Column('FILE_TYPE', sa.String(10), nullable=True))
    _add_col('BIC_KRI_EVIDENCE', sa.Column('FILE_SIZE_BYTES', sa.Integer(), nullable=True))
    _add_col('BIC_KRI_EVIDENCE', sa.Column('S3_BUCKET', sa.String(200), nullable=True))
    _add_col('BIC_KRI_EVIDENCE', sa.Column('VERSION_NUMBER', sa.Integer(), nullable=True, server_default='1'))
    _add_col('BIC_KRI_EVIDENCE', sa.Column('IS_LOCKED', sa.Boolean(), nullable=True, server_default='0'))
    _add_col('BIC_KRI_EVIDENCE', sa.Column('LOCKED_DT', sa.DateTime(), nullable=True))
    _add_col('BIC_KRI_EVIDENCE', sa.Column('LOCKED_BY', sa.String(50), nullable=True))
    _add_col('BIC_KRI_EVIDENCE', sa.Column('UPLOADED_BY', sa.Integer(), nullable=True))
    _add_col('BIC_KRI_EVIDENCE', sa.Column('UPLOADED_DT', sa.DateTime(), nullable=True))
    _add_col('BIC_KRI_EVIDENCE', sa.Column('METADATA_JSON', sa.Text(), nullable=True))
    _add_col('BIC_KRI_EVIDENCE', sa.Column('REGION_ID', sa.Integer(), nullable=True))

    # BIC_KRI_CONTROL_EVIDENCE_AUDIT
    _add_col('BIC_KRI_CONTROL_EVIDENCE_AUDIT', sa.Column('VERSION_NUMBER', sa.Integer(), nullable=True))
    _add_col('BIC_KRI_CONTROL_EVIDENCE_AUDIT', sa.Column('S3_KEY', sa.String(500), nullable=True))
    _add_col('BIC_KRI_CONTROL_EVIDENCE_AUDIT', sa.Column('FILE_SIZE_BYTES', sa.Integer(), nullable=True))
    _add_col('BIC_KRI_CONTROL_EVIDENCE_AUDIT', sa.Column('ACTION', sa.String(20), nullable=True))
    _add_col('BIC_KRI_CONTROL_EVIDENCE_AUDIT', sa.Column('PERFORMED_BY', sa.Integer(), nullable=True))
    _add_col('BIC_KRI_CONTROL_EVIDENCE_AUDIT', sa.Column('PERFORMED_DT', sa.DateTime(), nullable=True))
    _add_col('BIC_KRI_CONTROL_EVIDENCE_AUDIT', sa.Column('COMMENTS', sa.String(500), nullable=True))

    # BIC_KRI_DATA_SOURCE_MAPPING
    _add_col('BIC_KRI_DATA_SOURCE_MAPPING', sa.Column('MAPPING_TYPE', sa.String(20), nullable=True))
    _add_col('BIC_KRI_DATA_SOURCE_MAPPING', sa.Column('SOURCE_TYPE', sa.String(50), nullable=True))
    _add_col('BIC_KRI_DATA_SOURCE_MAPPING', sa.Column('CONNECTION_INFO', sa.String(500), nullable=True))
    _add_col('BIC_KRI_DATA_SOURCE_MAPPING', sa.Column('QUERY_TEMPLATE', sa.Text(), nullable=True))
    _add_col('BIC_KRI_DATA_SOURCE_MAPPING', sa.Column('SCHEDULE_CRON', sa.String(50), nullable=True))
    _add_col('BIC_KRI_DATA_SOURCE_MAPPING', sa.Column('IS_ACTIVE', sa.Boolean(), nullable=True, server_default='1'))

    # BIC_KRI_ASSIGNMENT_TRACKER
    _add_col('BIC_KRI_ASSIGNMENT_TRACKER', sa.Column('IS_ACTIVE', sa.Boolean(), nullable=True, server_default='1'))

    # BIC_SCORECARD
    _add_col('BIC_SCORECARD', sa.Column('SUBMITTED_DT', sa.DateTime(), nullable=True))
    _add_col('BIC_SCORECARD', sa.Column('KRI_ID', sa.Integer(), nullable=True))
    _add_col('BIC_SCORECARD', sa.Column('CREATED_BY_USER_ID', sa.Integer(), nullable=True))

    # BIC_EMAIL_AUDIT
    _add_col('BIC_EMAIL_AUDIT', sa.Column('RECIPIENT_NAME', sa.String(200), nullable=True))
    _add_col('BIC_EMAIL_AUDIT', sa.Column('SENT_DT', sa.DateTime(), nullable=True))
    _add_col('BIC_EMAIL_AUDIT', sa.Column('RELATED_KRI_ID', sa.Integer(), nullable=True))
    _add_col('BIC_EMAIL_AUDIT', sa.Column('RELATED_STATUS_ID', sa.Integer(), nullable=True))

    # BIC_SHED_LOCK
    _add_col('BIC_SHED_LOCK', sa.Column('IS_LOCKED', sa.Boolean(), nullable=True, server_default='1'))

    # BIC_KRI_METRIC — extra columns
    _add_col('BIC_KRI_METRIC', sa.Column('METRIC_ID', sa.Integer(), sa.Identity(start=1), nullable=True))
    _add_col('BIC_KRI_METRIC', sa.Column('PREVIOUS_VALUE', sa.Float(), nullable=True))
    _add_col('BIC_KRI_METRIC', sa.Column('VARIANCE_PCT', sa.Float(), nullable=True))
    _add_col('BIC_KRI_METRIC', sa.Column('VARIANCE_STATUS', sa.String(10), nullable=True))
    _add_col('BIC_KRI_METRIC', sa.Column('SOURCE_ID', sa.Integer(), nullable=True))
    _add_col('BIC_KRI_METRIC', sa.Column('CAPTURED_DT', sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_table('SAVED_VIEW')
    op.drop_table('APPROVAL_ASSIGNMENT_RULE')
    op.drop_table('NOTIFICATION')
    op.drop_table('ESCALATION_CONFIG')
    op.drop_table('VARIANCE_SUBMISSION')
    op.drop_table('APPROVAL_AUDIT_TRAIL')
    op.drop_table('MAKER_CHECKER_SUBMISSION')
    op.drop_table('KRI_CONFIGURATION')
    op.drop_table('USER_ROLE_MAPPING')
    op.drop_table('APP_USER')
