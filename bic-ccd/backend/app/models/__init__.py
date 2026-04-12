"""SQLAlchemy ORM models for BIC-CCD.

Table names align with the 23-table CCB Oracle schema (CCB_ prefix).
Python attribute names are kept unchanged from prior code so services/routers
need no edits.  Where the BIC Oracle column name differs from our Python
attribute name the Oracle name is supplied as the first positional argument
to mapped_column(), e.g.:

    dimension_id = mapped_column("CONTROL_ID", Integer, ...)

Oracle is case-insensitive for unquoted identifiers, so SQLAlchemy will
normalise 'kri_id' → KRI_ID automatically when no explicit name is given.
Explicit names are only needed where the BIC name differs structurally
(e.g. CONTROL_ID vs dimension_id, MONTH vs period_month).

Extra tables (not in BIC 23) are placed at the bottom and keep their
original names — they are created by our Alembic migration.
"""
from datetime import datetime, date
from typing import Optional, List
from sqlalchemy import (
    Integer, String, DateTime, Float, Text, Boolean,
    ForeignKey, UniqueConstraint, Index, Date, Identity,
)
from sqlalchemy.orm import relationship, Mapped, mapped_column
from app.database import Base


# ─── Audit Mixin ────────────────────────────────────────────
class AuditMixin:
    created_dt: Mapped[datetime] = mapped_column("CREATED_DT", DateTime, default=datetime.utcnow, nullable=False)
    updated_dt: Mapped[datetime] = mapped_column("UPDATED_DT", DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    created_by: Mapped[str] = mapped_column("CREATED_BY", String(50), nullable=False, default="SYSTEM")
    updated_by: Mapped[str] = mapped_column("UPDATED_BY", String(50), nullable=False, default="SYSTEM")


# ════════════════════════════════════════════════════════════
# BIC 23 TABLES
# ════════════════════════════════════════════════════════════

# ─── CCB_REGION ─────────────────────────────────────────────
class RegionMaster(AuditMixin, Base):
    __tablename__ = "CCB_REGION"

    region_id: Mapped[int] = mapped_column("REGION_ID", Integer, Identity(start=1), primary_key=True)
    region_name: Mapped[str] = mapped_column("REGION_NAME", String(200), nullable=False)
    # BIC names differ from our Phase-1 names — map explicitly
    control_lead: Mapped[Optional[str]] = mapped_column("CTRL_LEAD", String(200))
    governance_team: Mapped[Optional[str]] = mapped_column("GOV_TEAM", String(200))
    # Extra (not in BIC) — kept for app logic
    region_code: Mapped[Optional[str]] = mapped_column("REGION_CODE", String(10), unique=True)
    is_active: Mapped[bool] = mapped_column("IS_ACTIVE", Boolean, default=True)

    kris: Mapped[List["KriMaster"]] = relationship(back_populates="region")


# ─── CCB_KRI_CATEGORY ───────────────────────────────────────
class KriCategoryMaster(AuditMixin, Base):
    __tablename__ = "CCB_KRI_CATEGORY"

    category_id: Mapped[int] = mapped_column("CATEGORY_ID", Integer, Identity(start=1), primary_key=True)
    category_name: Mapped[str] = mapped_column("CATEGORY_NAME", String(200), nullable=False)
    # Extra
    category_code: Mapped[Optional[str]] = mapped_column("CATEGORY_CODE", String(30), unique=True)
    description: Mapped[Optional[str]] = mapped_column("DESCRIPTION", String(500))
    is_active: Mapped[bool] = mapped_column("IS_ACTIVE", Boolean, default=True)

    kris: Mapped[List["KriMaster"]] = relationship(back_populates="category")


# ─── CCB_KRI_CONTROL ────────────────────────────────────────
class ControlDimensionMaster(AuditMixin, Base):
    """BIC control type lookup.  Python attr 'dimension_id' → Oracle CONTROL_ID."""
    __tablename__ = "CCB_KRI_CONTROL"

    dimension_id: Mapped[int] = mapped_column("CONTROL_ID", Integer, Identity(start=1), primary_key=True)
    dimension_name: Mapped[str] = mapped_column("CONTROL_NAME", String(200), nullable=False)
    freeze_business_days: Mapped[Optional[int]] = mapped_column("FREEZE_BUSINESS_DAYS", Integer)
    # Extra
    dimension_code: Mapped[Optional[str]] = mapped_column("DIMENSION_CODE", String(30), unique=True)
    display_order: Mapped[int] = mapped_column("DISPLAY_ORDER", Integer, nullable=False, default=0)
    description: Mapped[Optional[str]] = mapped_column("DESCRIPTION", String(500))
    is_active: Mapped[bool] = mapped_column("IS_ACTIVE", Boolean, default=True)


# ─── CCB_KRI_STATUS ─────────────────────────────────────────
class KriStatusLookup(Base):
    """Lookup table for all possible KRI/control statuses."""
    __tablename__ = "CCB_KRI_STATUS"

    status_id: Mapped[int] = mapped_column("STATUS_ID", Integer, Identity(start=1), primary_key=True)
    status_name: Mapped[str] = mapped_column("STATUS_NAME", String(50), unique=True, nullable=False)
    created_dt: Mapped[datetime] = mapped_column("CREATED_DT", DateTime, default=datetime.utcnow, nullable=False)


# ─── CCB_KRI_CONFIG ─────────────────────────────────────────
class KriMaster(AuditMixin, Base):
    """Master KRI configuration — one row per KRI.
    Absorbs Phase-1 sla_start_day/sla_end_day/rag_thresholds → BIC names.
    """
    __tablename__ = "CCB_KRI_CONFIG"

    kri_id: Mapped[int] = mapped_column("KRI_ID", Integer, Identity(start=1), primary_key=True)
    kri_name: Mapped[str] = mapped_column("KRI_NAME", String(300), nullable=False)
    kri_title: Mapped[Optional[str]] = mapped_column("KRI_TITLE", String(300))
    scorecard_name: Mapped[Optional[str]] = mapped_column("SCORECARD_NAME", String(200))
    region_id: Mapped[int] = mapped_column("REGION_ID", Integer, ForeignKey("CCB_REGION.REGION_ID"), nullable=False)
    category_id: Mapped[int] = mapped_column("CATEGORY_ID", Integer, ForeignKey("CCB_KRI_CATEGORY.CATEGORY_ID"), nullable=False)
    legal_entities: Mapped[Optional[str]] = mapped_column("LEGAL_ENTITIES", Text)
    frequency: Mapped[Optional[str]] = mapped_column("FREQUENCY", String(50))
    data_sources: Mapped[Optional[str]] = mapped_column("DATA_SOURCES", Text)
    sla_check: Mapped[Optional[bool]] = mapped_column("SLA_CHECK", Boolean)
    # Phase-1 sla_start_day / sla_end_day → BIC SLA_START / SLA_END
    sla_start_day: Mapped[Optional[int]] = mapped_column("SLA_START", Integer)
    sla_end_day: Mapped[Optional[int]] = mapped_column("SLA_END", Integer)
    reminder_date: Mapped[Optional[int]] = mapped_column("REMINDER_DATE", Integer)
    escalation_date: Mapped[Optional[int]] = mapped_column("ESCALATION_DATE", Integer)
    accuracy_check: Mapped[Optional[bool]] = mapped_column("ACCURACY_CHECK", Boolean)
    completeness_check: Mapped[Optional[bool]] = mapped_column("COMPLETENESS_CHECK", Boolean)
    evidence_folder: Mapped[Optional[str]] = mapped_column("EVIDENCE_FOLDER", String(500))
    # Phase-1 rag_thresholds → BIC RAG_THRESHOLD
    rag_thresholds: Mapped[Optional[str]] = mapped_column("RAG_THRESHOLD", Text)
    metric_value_type: Mapped[Optional[str]] = mapped_column("METRIC_VALUE_TYPE", String(50))
    decimal_place: Mapped[Optional[int]] = mapped_column("DECIMAL_PLACE", Integer)
    is_active: Mapped[bool] = mapped_column("IS_ACTIVE", Boolean, default=True)
    # Extra (not in BIC)
    kri_code: Mapped[Optional[str]] = mapped_column("KRI_CODE", String(30), unique=True)
    description: Mapped[Optional[str]] = mapped_column("DESCRIPTION", Text)
    risk_level: Mapped[str] = mapped_column("RISK_LEVEL", String(20), default="MEDIUM")
    framework: Mapped[Optional[str]] = mapped_column("FRAMEWORK", String(100))
    is_dcrm: Mapped[bool] = mapped_column("IS_DCRM", Boolean, default=False, nullable=False, server_default="0")
    onboarded_dt: Mapped[Optional[datetime]] = mapped_column("ONBOARDED_DT", DateTime)

    category: Mapped["KriCategoryMaster"] = relationship(back_populates="kris")
    region: Mapped["RegionMaster"] = relationship(back_populates="kris")
    configurations: Mapped[List["KriConfiguration"]] = relationship(back_populates="kri")
    assignments: Mapped[List["KriAssignment"]] = relationship(back_populates="kri")
    monthly_statuses: Mapped[List["MonthlyControlStatus"]] = relationship(back_populates="kri")
    evidence: Mapped[List["EvidenceMetadata"]] = relationship(back_populates="kri")


# ─── CCB_KRI_METRIC ─────────────────────────────────────────
class MetricValues(AuditMixin, Base):
    __tablename__ = "CCB_KRI_METRIC"

    metric_id: Mapped[int] = mapped_column("METRIC_ID", Integer, Identity(start=1), primary_key=True)
    kri_id: Mapped[int] = mapped_column("KRI_ID", Integer, ForeignKey("CCB_KRI_CONFIG.KRI_ID"), nullable=False)
    dimension_id: Mapped[int] = mapped_column("CONTROL_ID", Integer, ForeignKey("CCB_KRI_CONTROL.CONTROL_ID"), nullable=False)
    # period_year / period_month → BIC YEAR / MONTH
    period_year: Mapped[int] = mapped_column("YEAR", Integer, nullable=False)
    period_month: Mapped[int] = mapped_column("MONTH", Integer, nullable=False)
    current_value: Mapped[Optional[float]] = mapped_column("METRIC_VALUE", Float)
    rag_status: Mapped[Optional[str]] = mapped_column("RAG_STATUS", String(10))
    run_date: Mapped[Optional[datetime]] = mapped_column("RUN_DATE", DateTime)
    # Extra
    previous_value: Mapped[Optional[float]] = mapped_column("PREVIOUS_VALUE", Float)
    variance_pct: Mapped[Optional[float]] = mapped_column("VARIANCE_PCT", Float)
    variance_status: Mapped[Optional[str]] = mapped_column("VARIANCE_STATUS", String(10))
    source_id: Mapped[Optional[int]] = mapped_column("SOURCE_ID", Integer, ForeignKey("CCB_KRI_DATA_SOURCE_MAPPING.ID"))
    captured_dt: Mapped[Optional[datetime]] = mapped_column("CAPTURED_DT", DateTime, default=datetime.utcnow)


# ─── CCB_KRI_COMMENT ────────────────────────────────────────
class KriComment(AuditMixin, Base):
    __tablename__ = "CCB_KRI_COMMENT"

    comment_id: Mapped[int] = mapped_column("ID", Integer, Identity(start=1), primary_key=True)
    kri_id: Mapped[int] = mapped_column("KRI_ID", Integer, ForeignKey("CCB_KRI_CONFIG.KRI_ID"), nullable=False)
    period_month: Mapped[Optional[int]] = mapped_column("MONTH", Integer)
    period_year: Mapped[Optional[int]] = mapped_column("YEAR", Integer)
    comment_text: Mapped[str] = mapped_column("COMMENTS", Text, nullable=False)
    # Extra
    dimension_id: Mapped[Optional[int]] = mapped_column("CONTROL_ID", Integer, ForeignKey("CCB_KRI_CONTROL.CONTROL_ID"))
    status_id: Mapped[Optional[int]] = mapped_column("STATUS_ID", Integer, ForeignKey("CCB_KRI_CONTROL_STATUS_TRACKER.ID"))
    comment_type: Mapped[str] = mapped_column("COMMENT_TYPE", String(20), default="GENERAL")
    parent_comment_id: Mapped[Optional[int]] = mapped_column("PARENT_COMMENT_ID", Integer, ForeignKey("CCB_KRI_COMMENT.ID"))
    posted_by: Mapped[int] = mapped_column("POSTED_BY", Integer, ForeignKey("APP_USER.USER_ID"), nullable=False)
    posted_dt: Mapped[datetime] = mapped_column("POSTED_DT", DateTime, default=datetime.utcnow)
    is_resolved: Mapped[bool] = mapped_column("IS_RESOLVED", Boolean, default=False)

    poster: Mapped["AppUser"] = relationship()


# ─── CCB_KRI_CONTROL_STATUS_TRACKER ─────────────────────────
class MonthlyControlStatus(AuditMixin, Base):
    """Core operational table — one row per KRI × control × month × year."""
    __tablename__ = "CCB_KRI_CONTROL_STATUS_TRACKER"

    status_id: Mapped[int] = mapped_column("ID", Integer, Identity(start=1), primary_key=True)
    kri_id: Mapped[int] = mapped_column("KRI_ID", Integer, ForeignKey("CCB_KRI_CONFIG.KRI_ID"), nullable=False)
    dimension_id: Mapped[int] = mapped_column("CONTROL_ID", Integer, ForeignKey("CCB_KRI_CONTROL.CONTROL_ID"), nullable=False)
    period_year: Mapped[int] = mapped_column("YEAR", Integer, nullable=False)
    period_month: Mapped[int] = mapped_column("MONTH", Integer, nullable=False)
    # status stored as string in our app; status_fk is the BIC FK to CCB_KRI_STATUS
    status: Mapped[str] = mapped_column("STATUS", String(30), default="NOT_STARTED")
    status_fk: Mapped[Optional[int]] = mapped_column("STATUS_ID", Integer, ForeignKey("CCB_KRI_STATUS.STATUS_ID"))
    sla_start: Mapped[Optional[datetime]] = mapped_column("SLA_START", DateTime)
    sla_end: Mapped[Optional[datetime]] = mapped_column("SLA_END", DateTime)
    sla_check: Mapped[Optional[bool]] = mapped_column("SLA_CHECK", Boolean)
    accuracy_check: Mapped[Optional[bool]] = mapped_column("ACCURACY_CHECK", Boolean)
    completeness_check: Mapped[Optional[bool]] = mapped_column("COMPLETENESS_CHECK", Boolean)
    kri_version: Mapped[Optional[str]] = mapped_column("KRI_VERSION", String(20))
    short_comment: Mapped[Optional[str]] = mapped_column("SHORT_COMMENT", String(200))
    long_comment: Mapped[Optional[str]] = mapped_column("LONG_COMMENT", Text)
    version_comment: Mapped[Optional[str]] = mapped_column("VERSION_COMMENT", String(500))
    retry_count: Mapped[int] = mapped_column("RETRY_COUNT", Integer, default=0)
    assigned_to: Mapped[Optional[int]] = mapped_column("ASSIGNED_TO", Integer, ForeignKey("APP_USER.USER_ID"))
    admin_update: Mapped[Optional[str]] = mapped_column("ADMIN_UPDATE", String(200))
    admin_update_dt: Mapped[Optional[datetime]] = mapped_column("ADMIN_UPDATE_DT", DateTime)
    # Extra
    rag_status: Mapped[Optional[str]] = mapped_column("RAG_STATUS", String(10))
    sla_due_dt: Mapped[Optional[datetime]] = mapped_column("SLA_DUE_DT", DateTime)
    sla_met: Mapped[Optional[bool]] = mapped_column("SLA_MET", Boolean)
    completed_dt: Mapped[Optional[datetime]] = mapped_column("COMPLETED_DT", DateTime)
    current_approver: Mapped[Optional[int]] = mapped_column("CURRENT_APPROVER", Integer, ForeignKey("APP_USER.USER_ID"))
    approval_level: Mapped[Optional[str]] = mapped_column("APPROVAL_LEVEL", String(10))

    kri: Mapped["KriMaster"] = relationship(back_populates="monthly_statuses")
    dimension: Mapped["ControlDimensionMaster"] = relationship()

    __table_args__ = (
        UniqueConstraint("KRI_ID", "CONTROL_ID", "YEAR", "MONTH", name="uq_ccb_status_tracker_period"),
        Index("idx_ccb_status_tracker_period", "YEAR", "MONTH"),
    )


# ─── CCB_KRI_CONTROL_EVIDENCE_AUDIT ─────────────────────────
class EvidenceVersionAudit(Base):
    """Audit trail of every evidence submission version."""
    __tablename__ = "CCB_KRI_CONTROL_EVIDENCE_AUDIT"

    version_id: Mapped[int] = mapped_column("ID", Integer, Identity(start=1), primary_key=True)
    evidence_id: Mapped[int] = mapped_column("TRACKER_ID", Integer, ForeignKey("CCB_KRI_EVIDENCE.ID"), nullable=False)
    metric_value: Mapped[Optional[float]] = mapped_column("METRIC_VALUE", Float)
    rag_status: Mapped[Optional[str]] = mapped_column("RAG_STATUS", String(10))
    assigned_to: Mapped[Optional[int]] = mapped_column("ASSIGNED_TO", Integer, ForeignKey("APP_USER.USER_ID"))
    status_fk: Mapped[Optional[int]] = mapped_column("STATUS_ID", Integer, ForeignKey("CCB_KRI_STATUS.STATUS_ID"))
    file_ids: Mapped[Optional[str]] = mapped_column("FILE_IDS", Text)
    short_comment: Mapped[Optional[str]] = mapped_column("SHORT_COMMENT", String(200))
    long_comment: Mapped[Optional[str]] = mapped_column("LONG_COMMENT", Text)
    version_comment: Mapped[Optional[str]] = mapped_column("VERSION_COMMENT", String(500))
    created_by: Mapped[str] = mapped_column("CREATED_BY", String(50), nullable=False, default="SYSTEM")
    created_dt: Mapped[datetime] = mapped_column("CREATED_DT", DateTime, default=datetime.utcnow, nullable=False)
    # Extra
    version_number: Mapped[Optional[int]] = mapped_column("VERSION_NUMBER", Integer)
    s3_key: Mapped[Optional[str]] = mapped_column("S3_KEY", String(500))
    file_size_bytes: Mapped[Optional[int]] = mapped_column("FILE_SIZE_BYTES", Integer)
    action: Mapped[Optional[str]] = mapped_column("ACTION", String(20))
    performed_by: Mapped[Optional[int]] = mapped_column("PERFORMED_BY", Integer, ForeignKey("APP_USER.USER_ID"))
    performed_dt: Mapped[Optional[datetime]] = mapped_column("PERFORMED_DT", DateTime, default=datetime.utcnow)
    comments: Mapped[Optional[str]] = mapped_column("COMMENTS", String(500))


# ─── CCB_KRI_EVIDENCE ───────────────────────────────────────
class EvidenceMetadata(AuditMixin, Base):
    __tablename__ = "CCB_KRI_EVIDENCE"

    evidence_id: Mapped[int] = mapped_column("ID", Integer, Identity(start=1), primary_key=True)
    kri_id: Mapped[int] = mapped_column("KRI_ID", Integer, ForeignKey("CCB_KRI_CONFIG.KRI_ID"), nullable=False)
    dimension_id: Mapped[int] = mapped_column("CONTROL_ID", Integer, ForeignKey("CCB_KRI_CONTROL.CONTROL_ID"), nullable=False)
    period_year: Mapped[int] = mapped_column("YEAR", Integer, nullable=False)
    period_month: Mapped[int] = mapped_column("MONTH", Integer, nullable=False)
    file_name: Mapped[str] = mapped_column("FILE_NAME", String(500), nullable=False)
    # s3_key → BIC FILE_PATH
    s3_key: Mapped[Optional[str]] = mapped_column("FILE_PATH", String(500))
    # evidence_status → BIC FILE_STATUS
    evidence_status: Mapped[str] = mapped_column("FILE_STATUS", String(20), default="ACTIVE", nullable=False, server_default="ACTIVE")
    file_id: Mapped[Optional[str]] = mapped_column("FILE_ID", String(100))
    file_upload_id: Mapped[Optional[str]] = mapped_column("FILE_UPLOAD_ID", String(100))
    kri_upload_version: Mapped[Optional[int]] = mapped_column("KRI_UPLOAD_VERSION", Integer)
    # Extra
    file_type: Mapped[Optional[str]] = mapped_column("FILE_TYPE", String(10))
    file_size_bytes: Mapped[Optional[int]] = mapped_column("FILE_SIZE_BYTES", Integer)
    s3_bucket: Mapped[Optional[str]] = mapped_column("S3_BUCKET", String(200))
    version_number: Mapped[int] = mapped_column("VERSION_NUMBER", Integer, default=1)
    is_locked: Mapped[bool] = mapped_column("IS_LOCKED", Boolean, default=False)
    locked_dt: Mapped[Optional[datetime]] = mapped_column("LOCKED_DT", DateTime)
    locked_by: Mapped[Optional[str]] = mapped_column("LOCKED_BY", String(50))
    uploaded_by: Mapped[int] = mapped_column("UPLOADED_BY", Integer, ForeignKey("APP_USER.USER_ID"), nullable=False)
    uploaded_dt: Mapped[datetime] = mapped_column("UPLOADED_DT", DateTime, default=datetime.utcnow)
    metadata_json: Mapped[Optional[str]] = mapped_column("METADATA_JSON", Text)
    region_id: Mapped[Optional[int]] = mapped_column("REGION_ID", Integer, ForeignKey("CCB_REGION.REGION_ID"))
    # BIC-aligned: optional FK to the tracker row this evidence file supports.
    # nullable=True so all existing rows remain valid (backfilled by Alembic migration).
    # Existing queries using (KRI_ID, CONTROL_ID, YEAR, MONTH) are unaffected.
    tracker_id: Mapped[Optional[int]] = mapped_column(
        "TRACKER_ID", Integer, ForeignKey("CCB_KRI_CONTROL_STATUS_TRACKER.ID"), nullable=True
    )

    kri: Mapped["KriMaster"] = relationship(back_populates="evidence")
    uploader: Mapped["AppUser"] = relationship(foreign_keys=[uploaded_by])
    region: Mapped[Optional["RegionMaster"]] = relationship(foreign_keys=[region_id])
    tracker: Mapped[Optional["MonthlyControlStatus"]] = relationship(
        foreign_keys=[tracker_id]
    )


# ─── CCB_KRI_USER_ROLE ──────────────────────────────────────
class KriUserRole(Base):
    """KRI-level role assignments per user — BIC boolean-flag model."""
    __tablename__ = "CCB_KRI_USER_ROLE"

    id: Mapped[int] = mapped_column("ID", Integer, Identity(start=1), primary_key=True)
    kri_id: Mapped[int] = mapped_column("KRI_ID", Integer, ForeignKey("CCB_KRI_CONFIG.KRI_ID"), nullable=False)
    user_id: Mapped[int] = mapped_column("USER_ID", Integer, ForeignKey("APP_USER.USER_ID"), nullable=False)
    data_provider: Mapped[bool] = mapped_column("DATA_PROVIDER", Boolean, default=False)
    metric_owner: Mapped[bool] = mapped_column("METRIC_OWNER", Boolean, default=False)
    remediation_owner: Mapped[bool] = mapped_column("REMEDIATION_OWNER", Boolean, default=False)
    maker: Mapped[bool] = mapped_column("MAKER", Boolean, default=False)
    checker: Mapped[bool] = mapped_column("CHECKER", Boolean, default=False)
    bi_metric_lead: Mapped[bool] = mapped_column("BI_METRIC_LEAD", Boolean, default=False)
    created_dt: Mapped[datetime] = mapped_column("CREATED_DT", DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("KRI_ID", "USER_ID", name="uq_ccb_kri_user_role"),
    )


# ─── CCB_ROLE_REGION_MAPPING ────────────────────────────────
class RoleRegionMapping(Base):
    """Maps AD group roles to regions."""
    __tablename__ = "CCB_ROLE_REGION_MAPPING"

    id: Mapped[int] = mapped_column("ID", Integer, Identity(start=1), primary_key=True)
    role: Mapped[str] = mapped_column("ROLE", String(100), nullable=False)
    region: Mapped[str] = mapped_column("REGION", String(50), nullable=False)
    created_dt: Mapped[datetime] = mapped_column("CREATED_DT", DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("ROLE", "REGION", name="uq_ccb_role_region"),
    )


# ─── CCB_KRI_DATA_SOURCE_MAPPING ────────────────────────────
class DataSourceMapping(AuditMixin, Base):
    __tablename__ = "CCB_KRI_DATA_SOURCE_MAPPING"

    source_id: Mapped[int] = mapped_column("ID", Integer, Identity(start=1), primary_key=True)
    kri_id: Mapped[int] = mapped_column("KRI_ID", Integer, ForeignKey("CCB_KRI_CONFIG.KRI_ID"), nullable=False)
    source_name: Mapped[str] = mapped_column("DATA_SOURCE", String(200), nullable=False)
    payload_name: Mapped[Optional[str]] = mapped_column("DATA_PAYLOAD", String(200))
    table_name: Mapped[Optional[str]] = mapped_column("DATA_TABLE", String(200))
    column_name: Mapped[Optional[str]] = mapped_column("DATA_COLUMN", String(200))
    schema_name: Mapped[Optional[str]] = mapped_column("TABLE_SCHEMA", String(200))
    # Extra
    mapping_type: Mapped[Optional[str]] = mapped_column("MAPPING_TYPE", String(20))
    source_type: Mapped[Optional[str]] = mapped_column("SOURCE_TYPE", String(50))
    connection_info: Mapped[Optional[str]] = mapped_column("CONNECTION_INFO", String(500))
    query_template: Mapped[Optional[str]] = mapped_column("QUERY_TEMPLATE", Text)
    schedule_cron: Mapped[Optional[str]] = mapped_column("SCHEDULE_CRON", String(50))
    is_active: Mapped[bool] = mapped_column("IS_ACTIVE", Boolean, default=True)


# ─── CCB_KRI_DATA_SOURCE_STATUS_TRACKER ─────────────────────
class DataSourceStatusTracker(Base):
    """Tracks data receipt status per mapping per month."""
    __tablename__ = "CCB_KRI_DATA_SOURCE_STATUS_TRACKER"

    id: Mapped[int] = mapped_column("ID", Integer, Identity(start=1), primary_key=True)
    mapping_id: Mapped[int] = mapped_column("MAPPING_ID", Integer, ForeignKey("CCB_KRI_DATA_SOURCE_MAPPING.ID"), nullable=False)
    period_month: Mapped[int] = mapped_column("MONTH", Integer, nullable=False)
    period_year: Mapped[int] = mapped_column("YEAR", Integer, nullable=False)
    status_id: Mapped[Optional[int]] = mapped_column("STATUS_ID", Integer, ForeignKey("CCB_KRI_STATUS.STATUS_ID"))
    status: Mapped[str] = mapped_column("STATUS", String(30), default="NOT_RECEIVED")
    received_dt: Mapped[Optional[datetime]] = mapped_column("RECEIVED_DT", DateTime)
    updated_dt: Mapped[datetime] = mapped_column("UPDATED_DT", DateTime, default=datetime.utcnow)
    created_dt: Mapped[datetime] = mapped_column("CREATED_DT", DateTime, default=datetime.utcnow)

    mapping: Mapped["DataSourceMapping"] = relationship(foreign_keys=[mapping_id])

    __table_args__ = (
        UniqueConstraint("MAPPING_ID", "MONTH", "YEAR", name="uq_ccb_ds_tracker"),
    )


# ─── CCB_KRI_ASSIGNMENT_TRACKER ─────────────────────────────
class KriAssignment(AuditMixin, Base):
    __tablename__ = "CCB_KRI_ASSIGNMENT_TRACKER"

    assignment_id: Mapped[int] = mapped_column("ID", Integer, Identity(start=1), primary_key=True)
    kri_id: Mapped[int] = mapped_column("KRI_ID", Integer, ForeignKey("CCB_KRI_CONFIG.KRI_ID"), nullable=False)
    dimension_id: Mapped[int] = mapped_column("CONTROL_ID", Integer, ForeignKey("CCB_KRI_CONTROL.CONTROL_ID"), nullable=False)
    period_month: Mapped[Optional[int]] = mapped_column("MONTH", Integer)
    period_year: Mapped[Optional[int]] = mapped_column("YEAR", Integer)
    assigned_user_id: Mapped[int] = mapped_column("ASSIGNED_TO", Integer, ForeignKey("APP_USER.USER_ID"), nullable=False)
    status_fk: Mapped[Optional[int]] = mapped_column("STATUS_ID", Integer, ForeignKey("CCB_KRI_STATUS.STATUS_ID"))
    role_code: Mapped[str] = mapped_column("APPROVER_TYPE", String(30), nullable=False)
    comments: Mapped[Optional[str]] = mapped_column("COMMENTS", Text)
    is_active: Mapped[bool] = mapped_column("IS_ACTIVE", Boolean, default=True)

    kri: Mapped["KriMaster"] = relationship(back_populates="assignments")
    dimension: Mapped["ControlDimensionMaster"] = relationship()
    assigned_user: Mapped["AppUser"] = relationship()


# ─── CCB_KRI_ASSIGNMENT_AUDIT ───────────────────────────────
class AssignmentAudit(Base):
    """Immutable audit log of every DCRM assignment change."""
    __tablename__ = "CCB_KRI_ASSIGNMENT_AUDIT"

    audit_id: Mapped[int] = mapped_column("ID", Integer, Identity(start=1), primary_key=True)
    kri_id: Mapped[int] = mapped_column("KRI_ID", Integer, ForeignKey("CCB_KRI_CONFIG.KRI_ID"), nullable=False)
    dimension_id: Mapped[int] = mapped_column("CONTROL_ID", Integer, ForeignKey("CCB_KRI_CONTROL.CONTROL_ID"), nullable=False)
    period_month: Mapped[Optional[int]] = mapped_column("MONTH", Integer)
    period_year: Mapped[Optional[int]] = mapped_column("YEAR", Integer)
    assigned_user_id: Mapped[int] = mapped_column("ASSIGNED_TO", Integer, ForeignKey("APP_USER.USER_ID"), nullable=False)
    status_fk: Mapped[Optional[int]] = mapped_column("STATUS_ID", Integer, ForeignKey("CCB_KRI_STATUS.STATUS_ID"))
    approver_level: Mapped[Optional[str]] = mapped_column("APPROVER_TYPE", String(30))
    comments: Mapped[Optional[str]] = mapped_column("COMMENTS", Text)
    assigned_by: Mapped[int] = mapped_column("CREATED_BY_USER", Integer, ForeignKey("APP_USER.USER_ID"), nullable=False)
    assigned_at: Mapped[datetime] = mapped_column("CREATED_DT", DateTime, default=datetime.utcnow, nullable=False)
    action: Mapped[Optional[str]] = mapped_column("ACTION", String(20))
    # kept for backward compat with Phase 1
    assignment_id: Mapped[Optional[int]] = mapped_column("ASSIGNMENT_ID", Integer, ForeignKey("CCB_KRI_ASSIGNMENT_TRACKER.ID"))

    kri: Mapped["KriMaster"] = relationship(foreign_keys=[kri_id])
    dimension: Mapped["ControlDimensionMaster"] = relationship(foreign_keys=[dimension_id])
    assigned_user: Mapped["AppUser"] = relationship(foreign_keys=[assigned_user_id])
    assigned_by_user: Mapped["AppUser"] = relationship(foreign_keys=[assigned_by])


# ─── CCB_SCORECARD ──────────────────────────────────────────
class ScorecardCase(AuditMixin, Base):
    __tablename__ = "CCB_SCORECARD"

    transaction_id: Mapped[int] = mapped_column("TRANSACTION_ID", Integer, Identity(start=1), primary_key=True)
    case_id: Mapped[Optional[str]] = mapped_column("CASE_ID", String(50))
    case_status: Mapped[str] = mapped_column("CASE_STATUS", String(20), default="SUBMITTED", nullable=False)
    request_title: Mapped[str] = mapped_column("REQUEST_TITLE", String(500), nullable=False)
    product_level_value: Mapped[Optional[str]] = mapped_column("PRODUCT_LEVEL_VALUE", String(200))
    file_id: Mapped[Optional[int]] = mapped_column("FILE_ID", Integer, ForeignKey("CCB_CASE_FILE.FILE_ID"))
    region_id: Mapped[int] = mapped_column("REGION_ID", Integer, ForeignKey("CCB_REGION.REGION_ID"), nullable=False)
    notes: Mapped[Optional[str]] = mapped_column("NOTES", Text)
    period_month: Mapped[Optional[int]] = mapped_column("MONTH", Integer)
    period_year: Mapped[Optional[int]] = mapped_column("YEAR", Integer)
    due_date: Mapped[Optional[date]] = mapped_column("DUE_DATE", Date)
    submitted_dt: Mapped[Optional[datetime]] = mapped_column("SUBMITTED_DT", DateTime)
    # Extra
    kri_id: Mapped[Optional[int]] = mapped_column("KRI_ID", Integer, ForeignKey("CCB_KRI_CONFIG.KRI_ID"))
    created_by_user: Mapped[int] = mapped_column("CREATED_BY_USER_ID", Integer, ForeignKey("APP_USER.USER_ID"), nullable=False)

    region: Mapped["RegionMaster"] = relationship(foreign_keys=[region_id])
    kri: Mapped[Optional["KriMaster"]] = relationship(foreign_keys=[kri_id])
    creator: Mapped["AppUser"] = relationship(foreign_keys=[created_by_user])
    approvers: Mapped[List["ScorecardApprover"]] = relationship(back_populates="case")
    activity_log: Mapped[List["ScorecardActivityLog"]] = relationship(back_populates="case")


# ─── CCB_SCORECARD_APPROVER ─────────────────────────────────
class ScorecardApprover(Base):
    __tablename__ = "CCB_SCORECARD_APPROVER"

    approver_id: Mapped[int] = mapped_column("ID", Integer, Identity(start=1), primary_key=True)
    case_id: Mapped[int] = mapped_column("CASE_ID", Integer, ForeignKey("CCB_SCORECARD.TRANSACTION_ID"), nullable=False)
    user_id: Mapped[int] = mapped_column("USER_ID", Integer, ForeignKey("APP_USER.USER_ID"), nullable=False)
    approved_at: Mapped[Optional[datetime]] = mapped_column("APPROVED_AT", DateTime)
    action: Mapped[Optional[str]] = mapped_column("ACTION", String(20))
    comments: Mapped[Optional[str]] = mapped_column("COMMENTS", Text)

    case: Mapped["ScorecardCase"] = relationship(back_populates="approvers")
    user: Mapped["AppUser"] = relationship(foreign_keys=[user_id])


# ─── CCB_SCORECARD_ACTIVITY_LOG ─────────────────────────────
class ScorecardActivityLog(Base):
    __tablename__ = "CCB_SCORECARD_ACTIVITY_LOG"

    log_id: Mapped[int] = mapped_column("ID", Integer, Identity(start=1), primary_key=True)
    case_id: Mapped[int] = mapped_column("CASE_ID", Integer, ForeignKey("CCB_SCORECARD.TRANSACTION_ID"), nullable=False)
    case_status: Mapped[str] = mapped_column("CASE_STATUS", String(20), nullable=False)
    file_id: Mapped[Optional[int]] = mapped_column("FILE_ID", Integer, ForeignKey("CCB_CASE_FILE.FILE_ID"))
    file_path: Mapped[Optional[str]] = mapped_column("FILE_PATH", String(500))
    review_comments: Mapped[Optional[str]] = mapped_column("REVIEW_COMMENTS", Text)
    created_by: Mapped[str] = mapped_column("CREATED_BY", String(50), nullable=False, default="SYSTEM")
    created_dt: Mapped[datetime] = mapped_column("CREATED_DT", DateTime, default=datetime.utcnow, nullable=False)
    # Extra
    action: Mapped[Optional[str]] = mapped_column("ACTION", String(30))
    performed_by: Mapped[Optional[int]] = mapped_column("PERFORMED_BY", Integer, ForeignKey("APP_USER.USER_ID"))
    previous_status: Mapped[Optional[str]] = mapped_column("PREVIOUS_STATUS", String(20))

    case: Mapped["ScorecardCase"] = relationship(back_populates="activity_log")
    performer: Mapped[Optional["AppUser"]] = relationship(foreign_keys=[performed_by])


# ─── CCB_CASE ───────────────────────────────────────────────
class BicCase(AuditMixin, Base):
    """Generic case records — linked to scorecard uploads."""
    __tablename__ = "CCB_CASE"

    transaction_id: Mapped[int] = mapped_column("TRANSACTION_ID", Integer, Identity(start=1), primary_key=True)
    case_id: Mapped[Optional[str]] = mapped_column("CASE_ID", String(50))
    case_status: Mapped[str] = mapped_column("CASE_STATUS", String(20), default="OPEN", nullable=False)
    is_active: Mapped[bool] = mapped_column("IS_ACTIVE", Boolean, default=True)

    files: Mapped[List["CaseFile"]] = relationship(back_populates="case")


# ─── CCB_CASE_FILE ──────────────────────────────────────────
class CaseFile(Base):
    """Files uploaded against cases."""
    __tablename__ = "CCB_CASE_FILE"

    file_id: Mapped[int] = mapped_column("FILE_ID", Integer, Identity(start=1), primary_key=True)
    case_id: Mapped[Optional[int]] = mapped_column("CASE_ID", Integer, ForeignKey("CCB_CASE.TRANSACTION_ID"))
    review_status: Mapped[Optional[str]] = mapped_column("REVIEW_STATUS", String(20))
    file_upload_id: Mapped[Optional[str]] = mapped_column("FILE_UPLOAD_ID", String(100))
    file_path: Mapped[str] = mapped_column("FILE_PATH", String(500), nullable=False)
    file_size: Mapped[Optional[int]] = mapped_column("FILE_SIZE", Integer)
    file_name: Mapped[Optional[str]] = mapped_column("FILE_NAME", String(500))
    created_by: Mapped[str] = mapped_column("CREATED_BY", String(50), nullable=False, default="SYSTEM")
    created_dt: Mapped[datetime] = mapped_column("CREATED_DT", DateTime, default=datetime.utcnow, nullable=False)

    case: Mapped[Optional["BicCase"]] = relationship(back_populates="files")


# ─── CCB_EMAIL_AUDIT ────────────────────────────────────────
class EmailAudit(Base):
    __tablename__ = "CCB_EMAIL_AUDIT"

    email_id: Mapped[int] = mapped_column("ID", Integer, Identity(start=1), primary_key=True)
    email_to: Mapped[str] = mapped_column("EMAIL_TO", String(500), nullable=False)
    email_cc: Mapped[Optional[str]] = mapped_column("EMAIL_CC", String(500))
    subject: Mapped[str] = mapped_column("SUBJECT", String(500), nullable=False)
    template_name: Mapped[Optional[str]] = mapped_column("TEMPLATE_NAME", String(100))
    status: Mapped[str] = mapped_column("STATUS", String(20), default="QUEUED")
    email_body: Mapped[Optional[str]] = mapped_column("EMAIL_BODY", Text)
    error_message: Mapped[Optional[str]] = mapped_column("ERROR_MESSAGE", String(1000))
    uuid: Mapped[Optional[str]] = mapped_column("UUID", String(100))
    created_dt: Mapped[datetime] = mapped_column("CREATED_DT", DateTime, default=datetime.utcnow, nullable=False)
    # Extra
    recipient_name: Mapped[Optional[str]] = mapped_column("RECIPIENT_NAME", String(200))
    sent_dt: Mapped[Optional[datetime]] = mapped_column("SENT_DT", DateTime)
    related_kri_id: Mapped[Optional[int]] = mapped_column("RELATED_KRI_ID", Integer, ForeignKey("CCB_KRI_CONFIG.KRI_ID"))
    related_status_id: Mapped[Optional[int]] = mapped_column("RELATED_STATUS_ID", Integer, ForeignKey("CCB_KRI_CONTROL_STATUS_TRACKER.ID"))


# ─── CCB_SHED_LOCK ──────────────────────────────────────────
class SchedulerLock(Base):
    """ShedLock-compatible distributed scheduler lock."""
    __tablename__ = "CCB_SHED_LOCK"

    job_name: Mapped[str] = mapped_column("NAME", String(100), primary_key=True)
    lock_until: Mapped[datetime] = mapped_column("LOCK_UNTIL", DateTime, nullable=False)
    locked_at: Mapped[datetime] = mapped_column("LOCKED_AT", DateTime, default=datetime.utcnow)
    locked_by: Mapped[str] = mapped_column("LOCKED_BY", String(100), nullable=False)
    # Extra (our app uses these)
    is_locked: Mapped[bool] = mapped_column("IS_LOCKED", Boolean, default=True)


# ════════════════════════════════════════════════════════════
# EXTRA TABLES (not in BIC 23 — created by our Alembic migration)
# ════════════════════════════════════════════════════════════

# ─── APP_USER ───────────────────────────────────────────────
class AppUser(AuditMixin, Base):
    """Application users — not in BIC 23 (BIC uses AD/LDAP).
    Kept for dev/demo auth and as FK target for BIC tables.
    """
    __tablename__ = "APP_USER"

    user_id: Mapped[int] = mapped_column("USER_ID", Integer, Identity(start=1), primary_key=True)
    soe_id: Mapped[str] = mapped_column("SOE_ID", String(20), unique=True, nullable=False)
    full_name: Mapped[str] = mapped_column("FULL_NAME", String(200), nullable=False)
    email: Mapped[str] = mapped_column("EMAIL", String(200), nullable=False)
    department: Mapped[Optional[str]] = mapped_column("DEPARTMENT", String(100))
    is_active: Mapped[bool] = mapped_column("IS_ACTIVE", Boolean, default=True)
    last_login_dt: Mapped[Optional[datetime]] = mapped_column("LAST_LOGIN_DT", DateTime)

    roles: Mapped[List["UserRoleMapping"]] = relationship(back_populates="user")


# ─── USER_ROLE_MAPPING ──────────────────────────────────────
class UserRoleMapping(AuditMixin, Base):
    """Our role-based access control — role_code strings per user per region.
    Complements CCB_KRI_USER_ROLE (KRI-level boolean flags).
    """
    __tablename__ = "USER_ROLE_MAPPING"

    mapping_id: Mapped[int] = mapped_column("MAPPING_ID", Integer, Identity(start=1), primary_key=True)
    user_id: Mapped[int] = mapped_column("USER_ID", Integer, ForeignKey("APP_USER.USER_ID"), nullable=False)
    role_code: Mapped[str] = mapped_column("ROLE_CODE", String(30), nullable=False)
    region_id: Mapped[Optional[int]] = mapped_column("REGION_ID", Integer, ForeignKey("CCB_REGION.REGION_ID"))
    is_active: Mapped[bool] = mapped_column("IS_ACTIVE", Boolean, default=True)
    effective_from: Mapped[date] = mapped_column("EFFECTIVE_FROM", Date, nullable=False)
    effective_to: Mapped[Optional[date]] = mapped_column("EFFECTIVE_TO", Date)

    user: Mapped["AppUser"] = relationship(back_populates="roles")
    region: Mapped[Optional["RegionMaster"]] = relationship()

    __table_args__ = (
        UniqueConstraint("USER_ID", "ROLE_CODE", "REGION_ID", name="uq_ccb_user_role_region"),
    )


# ─── KRI_CONFIGURATION ──────────────────────────────────────
class KriConfiguration(AuditMixin, Base):
    """Per-KRI × control dimension settings (SLA days, RAG scalars, etc.).
    Not in BIC 23 — BIC stores KRI-level config in CCB_KRI_CONFIG.
    Kept for per-dimension overrides our app needs.
    """
    __tablename__ = "KRI_CONFIGURATION"

    config_id: Mapped[int] = mapped_column("CONFIG_ID", Integer, Identity(start=1), primary_key=True)
    kri_id: Mapped[int] = mapped_column("KRI_ID", Integer, ForeignKey("CCB_KRI_CONFIG.KRI_ID"), nullable=False)
    dimension_id: Mapped[int] = mapped_column("CONTROL_ID", Integer, ForeignKey("CCB_KRI_CONTROL.CONTROL_ID"), nullable=False)
    sla_days: Mapped[int] = mapped_column("SLA_DAYS", Integer, default=3)
    variance_threshold: Mapped[float] = mapped_column("VARIANCE_THRESHOLD", Float, default=10.0)
    rag_green_max: Mapped[Optional[float]] = mapped_column("RAG_GREEN_MAX", Float)
    rag_amber_max: Mapped[Optional[float]] = mapped_column("RAG_AMBER_MAX", Float)
    requires_evidence: Mapped[bool] = mapped_column("REQUIRES_EVIDENCE", Boolean, default=True)
    requires_approval: Mapped[bool] = mapped_column("REQUIRES_APPROVAL", Boolean, default=True)
    freeze_day: Mapped[int] = mapped_column("FREEZE_DAY", Integer, default=15)
    sla_start_day: Mapped[Optional[int]] = mapped_column("SLA_START_DAY", Integer)
    sla_end_day: Mapped[Optional[int]] = mapped_column("SLA_END_DAY", Integer)
    rag_thresholds: Mapped[Optional[str]] = mapped_column("RAG_THRESHOLDS", Text)
    is_active: Mapped[bool] = mapped_column("IS_ACTIVE", Boolean, default=True)

    kri: Mapped["KriMaster"] = relationship(back_populates="configurations")
    dimension: Mapped["ControlDimensionMaster"] = relationship()

    __table_args__ = (
        UniqueConstraint("KRI_ID", "CONTROL_ID", name="uq_ccb_kri_config_dim"),
    )


# ─── MAKER_CHECKER_SUBMISSION ───────────────────────────────
class MakerCheckerSubmission(AuditMixin, Base):
    __tablename__ = "MAKER_CHECKER_SUBMISSION"

    submission_id: Mapped[int] = mapped_column("SUBMISSION_ID", Integer, Identity(start=1), primary_key=True)
    status_id: Mapped[int] = mapped_column("STATUS_ID", Integer, ForeignKey("CCB_KRI_CONTROL_STATUS_TRACKER.ID"), nullable=False)
    evidence_id: Mapped[Optional[int]] = mapped_column("EVIDENCE_ID", Integer, ForeignKey("CCB_KRI_EVIDENCE.ID"))
    submitted_by: Mapped[int] = mapped_column("SUBMITTED_BY", Integer, ForeignKey("APP_USER.USER_ID"), nullable=False)
    submitted_dt: Mapped[datetime] = mapped_column("SUBMITTED_DT", DateTime, default=datetime.utcnow)
    submission_notes: Mapped[Optional[str]] = mapped_column("SUBMISSION_NOTES", Text)
    l1_approver_id: Mapped[Optional[int]] = mapped_column("L1_APPROVER_ID", Integer, ForeignKey("APP_USER.USER_ID"))
    l1_action: Mapped[Optional[str]] = mapped_column("L1_ACTION", String(20))
    l1_action_dt: Mapped[Optional[datetime]] = mapped_column("L1_ACTION_DT", DateTime)
    l1_comments: Mapped[Optional[str]] = mapped_column("L1_COMMENTS", String(2000))
    l2_approver_id: Mapped[Optional[int]] = mapped_column("L2_APPROVER_ID", Integer, ForeignKey("APP_USER.USER_ID"))
    l2_action: Mapped[Optional[str]] = mapped_column("L2_ACTION", String(20))
    l2_action_dt: Mapped[Optional[datetime]] = mapped_column("L2_ACTION_DT", DateTime)
    l2_comments: Mapped[Optional[str]] = mapped_column("L2_COMMENTS", String(2000))
    l3_approver_id: Mapped[Optional[int]] = mapped_column("L3_APPROVER_ID", Integer, ForeignKey("APP_USER.USER_ID"))
    l3_action: Mapped[Optional[str]] = mapped_column("L3_ACTION", String(20))
    l3_action_dt: Mapped[Optional[datetime]] = mapped_column("L3_ACTION_DT", DateTime)
    l3_comments: Mapped[Optional[str]] = mapped_column("L3_COMMENTS", String(2000))
    final_status: Mapped[str] = mapped_column("FINAL_STATUS", String(20), default="PENDING")

    control_status: Mapped["MonthlyControlStatus"] = relationship()
    evidence: Mapped[Optional["EvidenceMetadata"]] = relationship()
    submitter: Mapped["AppUser"] = relationship(foreign_keys=[submitted_by])


# ─── APPROVAL_AUDIT_TRAIL ───────────────────────────────────
class ApprovalAuditTrail(AuditMixin, Base):
    __tablename__ = "APPROVAL_AUDIT_TRAIL"

    audit_id: Mapped[int] = mapped_column("AUDIT_ID", Integer, Identity(start=1), primary_key=True)
    status_id: Mapped[int] = mapped_column("STATUS_ID", Integer, ForeignKey("CCB_KRI_CONTROL_STATUS_TRACKER.ID"), nullable=False)
    action: Mapped[str] = mapped_column("ACTION", String(30), nullable=False)
    performed_by: Mapped[int] = mapped_column("PERFORMED_BY", Integer, ForeignKey("APP_USER.USER_ID"), nullable=False)
    performed_dt: Mapped[datetime] = mapped_column("PERFORMED_DT", DateTime, default=datetime.utcnow)
    comments: Mapped[Optional[str]] = mapped_column("COMMENTS", String(2000))
    previous_status: Mapped[Optional[str]] = mapped_column("PREVIOUS_STATUS", String(20))
    new_status: Mapped[Optional[str]] = mapped_column("NEW_STATUS", String(20))
    ip_address: Mapped[Optional[str]] = mapped_column("IP_ADDRESS", String(50))

    performer: Mapped["AppUser"] = relationship()
    control_status: Mapped["MonthlyControlStatus"] = relationship()


# ─── VARIANCE_SUBMISSION ────────────────────────────────────
class VarianceSubmission(AuditMixin, Base):
    __tablename__ = "VARIANCE_SUBMISSION"

    variance_id: Mapped[int] = mapped_column("VARIANCE_ID", Integer, Identity(start=1), primary_key=True)
    metric_id: Mapped[int] = mapped_column("METRIC_ID", Integer, ForeignKey("CCB_KRI_METRIC.METRIC_ID"), nullable=False)
    status_id: Mapped[Optional[int]] = mapped_column("STATUS_ID", Integer, ForeignKey("CCB_KRI_CONTROL_STATUS_TRACKER.ID"))
    variance_pct: Mapped[float] = mapped_column("VARIANCE_PCT", Float, nullable=False)
    commentary: Mapped[str] = mapped_column("COMMENTARY", Text, nullable=False)
    submitted_by: Mapped[int] = mapped_column("SUBMITTED_BY", Integer, ForeignKey("APP_USER.USER_ID"), nullable=False)
    submitted_dt: Mapped[datetime] = mapped_column("SUBMITTED_DT", DateTime, default=datetime.utcnow)
    review_status: Mapped[str] = mapped_column("REVIEW_STATUS", String(20), default="PENDING")
    reviewed_by: Mapped[Optional[int]] = mapped_column("REVIEWED_BY", Integer, ForeignKey("APP_USER.USER_ID"))
    reviewed_dt: Mapped[Optional[datetime]] = mapped_column("REVIEWED_DT", DateTime)
    review_comments: Mapped[Optional[str]] = mapped_column("REVIEW_COMMENTS", String(2000))

    metric: Mapped["MetricValues"] = relationship()


# ─── ESCALATION_CONFIG ──────────────────────────────────────
class EscalationConfig(AuditMixin, Base):
    __tablename__ = "ESCALATION_CONFIG"

    config_id: Mapped[int] = mapped_column("CONFIG_ID", Integer, Identity(start=1), primary_key=True)
    region_id: Mapped[Optional[int]] = mapped_column("REGION_ID", Integer, ForeignKey("CCB_REGION.REGION_ID"))
    escalation_type: Mapped[str] = mapped_column("ESCALATION_TYPE", String(30), nullable=False)
    threshold_hours: Mapped[int] = mapped_column("THRESHOLD_HOURS", Integer, default=72)
    reminder_hours: Mapped[int] = mapped_column("REMINDER_HOURS", Integer, default=24)
    max_reminders: Mapped[int] = mapped_column("MAX_REMINDERS", Integer, default=3)
    escalate_to_role: Mapped[str] = mapped_column("ESCALATE_TO_ROLE", String(30), nullable=False)
    email_template: Mapped[Optional[str]] = mapped_column("EMAIL_TEMPLATE", Text)
    is_active: Mapped[bool] = mapped_column("IS_ACTIVE", Boolean, default=True)


# ─── NOTIFICATION ───────────────────────────────────────────
class Notification(AuditMixin, Base):
    __tablename__ = "NOTIFICATION"

    notification_id: Mapped[int] = mapped_column("NOTIFICATION_ID", Integer, Identity(start=1), primary_key=True)
    user_id: Mapped[int] = mapped_column("USER_ID", Integer, ForeignKey("APP_USER.USER_ID"), nullable=False)
    title: Mapped[str] = mapped_column("TITLE", String(300), nullable=False)
    message: Mapped[str] = mapped_column("MESSAGE", String(2000), nullable=False)
    notification_type: Mapped[Optional[str]] = mapped_column("NOTIFICATION_TYPE", String(30))
    is_read: Mapped[bool] = mapped_column("IS_READ", Boolean, default=False)
    link_url: Mapped[Optional[str]] = mapped_column("LINK_URL", String(500))

    user: Mapped["AppUser"] = relationship()


# ─── APPROVAL_ASSIGNMENT_RULE ────────────────────────────────
class ApprovalAssignmentRule(AuditMixin, Base):
    __tablename__ = "APPROVAL_ASSIGNMENT_RULE"

    rule_id: Mapped[int] = mapped_column("RULE_ID", Integer, Identity(start=1), primary_key=True)
    role_code: Mapped[str] = mapped_column("ROLE_CODE", String(20), nullable=False)
    user_id: Mapped[Optional[int]] = mapped_column("USER_ID", Integer, ForeignKey("APP_USER.USER_ID"))
    region_id: Mapped[Optional[int]] = mapped_column("REGION_ID", Integer, ForeignKey("CCB_REGION.REGION_ID"))
    kri_id: Mapped[Optional[int]] = mapped_column("KRI_ID", Integer, ForeignKey("CCB_KRI_CONFIG.KRI_ID"))
    category_id: Mapped[Optional[int]] = mapped_column("CATEGORY_ID", Integer, ForeignKey("CCB_KRI_CATEGORY.CATEGORY_ID"))
    priority: Mapped[int] = mapped_column("PRIORITY", Integer, nullable=False, default=100)
    is_active: Mapped[bool] = mapped_column("IS_ACTIVE", Boolean, default=True)

    user: Mapped[Optional["AppUser"]] = relationship()
    region: Mapped[Optional["RegionMaster"]] = relationship()
    kri: Mapped[Optional["KriMaster"]] = relationship()
    category: Mapped[Optional["KriCategoryMaster"]] = relationship()

    __table_args__ = (
        Index("idx_aar_role_region", "ROLE_CODE", "REGION_ID"),
    )


# ─── SAVED_VIEW ─────────────────────────────────────────────
class SavedView(AuditMixin, Base):
    __tablename__ = "SAVED_VIEW"

    view_id: Mapped[int] = mapped_column("VIEW_ID", Integer, Identity(start=1), primary_key=True)
    user_id: Mapped[int] = mapped_column("USER_ID", Integer, ForeignKey("APP_USER.USER_ID"), nullable=False)
    view_name: Mapped[str] = mapped_column("VIEW_NAME", String(200), nullable=False)
    view_type: Mapped[str] = mapped_column("VIEW_TYPE", String(30), nullable=False)
    filters_json: Mapped[Optional[str]] = mapped_column("FILTERS_JSON", Text)
    is_default: Mapped[bool] = mapped_column("IS_DEFAULT", Boolean, default=False)


# ════════════════════════════════════════════════════════════
# KRI ONBOARDING TABLES (Bluesheet workflow)
# ════════════════════════════════════════════════════════════

# ─── BIC_KRI_BLUESHEET ──────────────────────────────────────
class KriBluesheet(AuditMixin, Base):
    """Extended KRI metadata matching the Bluesheet form.
    One row per KRI — stores roles, scorecard coverage, rationale, and runbook.
    """
    __tablename__ = "BIC_KRI_BLUESHEET"

    bluesheet_id: Mapped[int] = mapped_column("BLUESHEET_ID", Integer, Identity(start=1), primary_key=True)
    kri_id: Mapped[int] = mapped_column("KRI_ID", Integer, ForeignKey("CCB_KRI_CONFIG.KRI_ID"), nullable=False, unique=True)

    # ── Classification extras ──────────────────────────────
    legacy_kri_id: Mapped[Optional[str]] = mapped_column("LEGACY_KRI_ID", String(50))
    threshold: Mapped[Optional[str]] = mapped_column("THRESHOLD", String(100))
    circuit_breaker: Mapped[Optional[str]] = mapped_column("CIRCUIT_BREAKER", String(100))
    control_ids: Mapped[Optional[str]] = mapped_column("CONTROL_IDS", String(500))
    dq_objectives: Mapped[Optional[str]] = mapped_column("DQ_OBJECTIVES", Text)

    # ── Roles & Responsibilities ───────────────────────────
    primary_senior_manager: Mapped[Optional[str]] = mapped_column("PRIMARY_SENIOR_MANAGER", String(200))
    metric_owner_name: Mapped[Optional[str]] = mapped_column("METRIC_OWNER_NAME", String(200))
    remediation_owner_name: Mapped[Optional[str]] = mapped_column("REMEDIATION_OWNER_NAME", String(200))
    bi_metrics_lead: Mapped[Optional[str]] = mapped_column("BI_METRICS_LEAD", String(200))
    data_provider_name: Mapped[Optional[str]] = mapped_column("DATA_PROVIDER_NAME", String(200))

    # ── Scorecard Coverage ─────────────────────────────────
    sc_uk: Mapped[bool] = mapped_column("SC_UK", Boolean, default=False)
    sc_finance: Mapped[bool] = mapped_column("SC_FINANCE", Boolean, default=False)
    sc_risk: Mapped[bool] = mapped_column("SC_RISK", Boolean, default=False)
    sc_liquidity: Mapped[bool] = mapped_column("SC_LIQUIDITY", Boolean, default=False)
    sc_capital: Mapped[bool] = mapped_column("SC_CAPITAL", Boolean, default=False)
    sc_risk_reports: Mapped[bool] = mapped_column("SC_RISK_REPORTS", Boolean, default=False)
    sc_markets: Mapped[bool] = mapped_column("SC_MARKETS", Boolean, default=False)

    # ── Rationale & Scope ──────────────────────────────────
    why_selected: Mapped[Optional[str]] = mapped_column("WHY_SELECTED", Text)
    threshold_rationale: Mapped[Optional[str]] = mapped_column("THRESHOLD_RATIONALE", Text)
    limitations: Mapped[Optional[str]] = mapped_column("LIMITATIONS", Text)
    kri_calculation: Mapped[Optional[str]] = mapped_column("KRI_CALCULATION", Text)

    # ── Runbook ────────────────────────────────────────────
    runbook_s3_path: Mapped[Optional[str]] = mapped_column("RUNBOOK_S3_PATH", String(500))
    runbook_filename: Mapped[Optional[str]] = mapped_column("RUNBOOK_FILENAME", String(300))
    runbook_version: Mapped[Optional[str]] = mapped_column("RUNBOOK_VERSION", String(20))
    runbook_review_date: Mapped[Optional[date]] = mapped_column("RUNBOOK_REVIEW_DATE", Date)
    runbook_notes: Mapped[Optional[str]] = mapped_column("RUNBOOK_NOTES", Text)

    # ── Approval ───────────────────────────────────────────
    approval_status: Mapped[str] = mapped_column("APPROVAL_STATUS", String(20), default="PENDING_APPROVAL", nullable=False)
    submitted_by: Mapped[Optional[int]] = mapped_column("SUBMITTED_BY", Integer, ForeignKey("APP_USER.USER_ID"))
    submitted_dt: Mapped[Optional[datetime]] = mapped_column("SUBMITTED_DT", DateTime)

    kri: Mapped["KriMaster"] = relationship(foreign_keys=[kri_id])
    submitter: Mapped[Optional["AppUser"]] = relationship(foreign_keys=[submitted_by])


# ─── BIC_KRI_APPROVAL_LOG ───────────────────────────────────
class KriApprovalLog(Base):
    """Immutable audit log for KRI-level onboarding approval actions."""
    __tablename__ = "BIC_KRI_APPROVAL_LOG"

    log_id: Mapped[int] = mapped_column("LOG_ID", Integer, Identity(start=1), primary_key=True)
    kri_id: Mapped[int] = mapped_column("KRI_ID", Integer, ForeignKey("CCB_KRI_CONFIG.KRI_ID"), nullable=False)
    action: Mapped[str] = mapped_column("ACTION", String(20), nullable=False)   # SUBMITTED | APPROVED | REJECTED | REWORK
    performed_by: Mapped[int] = mapped_column("PERFORMED_BY", Integer, ForeignKey("APP_USER.USER_ID"), nullable=False)
    performed_dt: Mapped[datetime] = mapped_column("PERFORMED_DT", DateTime, default=datetime.utcnow, nullable=False)
    comments: Mapped[Optional[str]] = mapped_column("COMMENTS", Text)
    previous_status: Mapped[Optional[str]] = mapped_column("PREVIOUS_STATUS", String(20))
    new_status: Mapped[Optional[str]] = mapped_column("NEW_STATUS", String(20))

    kri: Mapped["KriMaster"] = relationship(foreign_keys=[kri_id])
    performer: Mapped["AppUser"] = relationship(foreign_keys=[performed_by])


# ════════════════════════════════════════════════════════════
# AUDIT EVIDENCE TABLES (Unified Audit Evidence System)
# ════════════════════════════════════════════════════════════

# ─── BIC_KRI_EVIDENCE_METADATA ──────────────────────────────
class KriEvidenceMetadata(AuditMixin, Base):
    """Stores ONLY metadata — no file/email content. S3 is source of truth."""
    __tablename__ = "BIC_KRI_EVIDENCE_METADATA"

    evidence_id: Mapped[int] = mapped_column("EVIDENCE_ID", Integer, Identity(start=1), primary_key=True)
    kri_id: Mapped[int] = mapped_column("KRI_ID", Integer, ForeignKey("CCB_KRI_CONFIG.KRI_ID"), nullable=False)
    control_id: Mapped[Optional[str]] = mapped_column("CONTROL_ID_STR", String(100))   # e.g. "CCB-DC-0041"
    region_code: Mapped[Optional[str]] = mapped_column("REGION_CODE", String(20))       # e.g. "UK"
    period_year: Mapped[int] = mapped_column("PERIOD_YEAR", Integer, nullable=False)
    period_month: Mapped[int] = mapped_column("PERIOD_MONTH", Integer, nullable=False)
    iteration: Mapped[Optional[int]] = mapped_column("ITERATION", Integer)               # for email evidence
    evidence_type: Mapped[str] = mapped_column("EVIDENCE_TYPE", String(20), nullable=False)  # manual | auto | email
    action: Mapped[Optional[str]] = mapped_column("ACTION", String(50))                  # SUBMISSION | REWORK | ...
    sender: Mapped[Optional[str]] = mapped_column("SENDER", String(500))
    receiver: Mapped[Optional[str]] = mapped_column("RECEIVER", String(500))
    file_name: Mapped[str] = mapped_column("FILE_NAME", String(500), nullable=False)
    s3_object_path: Mapped[str] = mapped_column("S3_OBJECT_PATH", String(1000), nullable=False)
    uploaded_by: Mapped[Optional[int]] = mapped_column("UPLOADED_BY", Integer, ForeignKey("APP_USER.USER_ID"))
    notes: Mapped[Optional[str]] = mapped_column("NOTES", Text)
    is_unmapped: Mapped[bool] = mapped_column("IS_UNMAPPED", Boolean, default=False)
    email_uuid: Mapped[Optional[str]] = mapped_column("EMAIL_UUID", String(100))

    kri: Mapped["KriMaster"] = relationship(foreign_keys=[kri_id])
    uploader: Mapped[Optional["AppUser"]] = relationship(foreign_keys=[uploaded_by])

    __table_args__ = (
        Index("idx_bic_evmeta_kri_period", "KRI_ID", "PERIOD_YEAR", "PERIOD_MONTH"),
    )


# ─── BIC_KRI_EMAIL_ITERATION ────────────────────────────────
class KriEmailIteration(Base):
    """Tracks current iteration count per KRI per reporting period."""
    __tablename__ = "BIC_KRI_EMAIL_ITERATION"

    iter_id: Mapped[int] = mapped_column("ITER_ID", Integer, Identity(start=1), primary_key=True)
    kri_id: Mapped[int] = mapped_column("KRI_ID", Integer, ForeignKey("CCB_KRI_CONFIG.KRI_ID"), nullable=False)
    period_year: Mapped[int] = mapped_column("PERIOD_YEAR", Integer, nullable=False)
    period_month: Mapped[int] = mapped_column("PERIOD_MONTH", Integer, nullable=False)
    current_iter: Mapped[int] = mapped_column("CURRENT_ITER", Integer, default=1)
    last_updated: Mapped[datetime] = mapped_column("LAST_UPDATED", DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    kri: Mapped["KriMaster"] = relationship(foreign_keys=[kri_id])

    __table_args__ = (
        UniqueConstraint("KRI_ID", "PERIOD_YEAR", "PERIOD_MONTH", name="uq_bic_kri_iter_period"),
    )


# ─── BIC_KRI_AUDIT_SUMMARY ──────────────────────────────────
class KriAuditSummary(Base):
    """Tracks generated audit summaries."""
    __tablename__ = "BIC_KRI_AUDIT_SUMMARY"

    summary_id: Mapped[int] = mapped_column("SUMMARY_ID", Integer, Identity(start=1), primary_key=True)
    kri_id: Mapped[int] = mapped_column("KRI_ID", Integer, ForeignKey("CCB_KRI_CONFIG.KRI_ID"), nullable=False)
    period_year: Mapped[int] = mapped_column("PERIOD_YEAR", Integer, nullable=False)
    period_month: Mapped[int] = mapped_column("PERIOD_MONTH", Integer, nullable=False)
    s3_path: Mapped[str] = mapped_column("S3_PATH", String(1000), nullable=False)
    generated_dt: Mapped[datetime] = mapped_column("GENERATED_DT", DateTime, default=datetime.utcnow, nullable=False)
    generated_by: Mapped[Optional[int]] = mapped_column("GENERATED_BY", Integer, ForeignKey("APP_USER.USER_ID"))
    l3_approver_name: Mapped[Optional[str]] = mapped_column("L3_APPROVER_NAME", String(200))
    final_status: Mapped[str] = mapped_column("FINAL_STATUS", String(30), default="APPROVED")
    total_iterations: Mapped[int] = mapped_column("TOTAL_ITERATIONS", Integer, default=0)
    total_evidences: Mapped[int] = mapped_column("TOTAL_EVIDENCES", Integer, default=0)
    total_emails: Mapped[int] = mapped_column("TOTAL_EMAILS", Integer, default=0)

    kri: Mapped["KriMaster"] = relationship(foreign_keys=[kri_id])
    generator: Mapped[Optional["AppUser"]] = relationship(foreign_keys=[generated_by])
