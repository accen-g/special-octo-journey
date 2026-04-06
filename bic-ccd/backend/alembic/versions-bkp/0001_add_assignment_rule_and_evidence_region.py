"""Add approval_assignment_rule table and evidence_metadata.region_id column.

Revision ID: 0001
Revises:
Create Date: 2026-04-04

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers used by Alembic
revision = '0001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── 1. Add region_id to evidence_metadata ───────────────
    # Uses batch mode for SQLite compatibility (SQLite cannot ALTER columns in-place).
    with op.batch_alter_table("evidence_metadata") as batch_op:
        batch_op.add_column(
            sa.Column("region_id", sa.Integer(), sa.ForeignKey("region_master.region_id"), nullable=True)
        )

    # ── 2. Create approval_assignment_rule table ─────────────
    op.create_table(
        "approval_assignment_rule",
        sa.Column("rule_id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("role_code", sa.String(20), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("app_user.user_id"), nullable=True),
        sa.Column("region_id", sa.Integer(), sa.ForeignKey("region_master.region_id"), nullable=True),
        sa.Column("kri_id", sa.Integer(), sa.ForeignKey("kri_master.kri_id"), nullable=True),
        sa.Column("category_id", sa.Integer(), sa.ForeignKey("kri_category_master.category_id"), nullable=True),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="100"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="1"),
        # AuditMixin columns
        sa.Column("created_dt", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_dt", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("created_by", sa.String(50), nullable=False, server_default="SYSTEM"),
        sa.Column("updated_by", sa.String(50), nullable=False, server_default="SYSTEM"),
    )
    op.create_index("idx_aar_role_region", "approval_assignment_rule", ["role_code", "region_id"])


def downgrade() -> None:
    # Drop assignment rule table + index
    op.drop_index("idx_aar_role_region", table_name="approval_assignment_rule")
    op.drop_table("approval_assignment_rule")

    # Remove region_id from evidence_metadata
    with op.batch_alter_table("evidence_metadata") as batch_op:
        batch_op.drop_column("region_id")
