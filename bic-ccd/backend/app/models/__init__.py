"""SQLAlchemy ORM models for BIC-CCD."""
from datetime import datetime, date
from typing import Optional, List
from sqlalchemy import (
    Column, Integer, String, DateTime, Float, Text, Boolean,
    ForeignKey, UniqueConstraint, Index, CheckConstraint, Date, Identity
)
from sqlalchemy.orm import relationship, Mapped, mapped_column
from app.database import Base


# ─── Mixin ──────────────────────────────────────────────────
class AuditMixin:
    created_dt: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_dt: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    created_by: Mapped[str] = mapped_column(String(50), nullable=False, default="SYSTEM")
    updated_by: Mapped[str] = mapped_column(String(50), nullable=False, default="SYSTEM")


# ─── Region ─────────────────────────────────────────────────
class RegionMaster(AuditMixin, Base):
    __tablename__ = "region_master"
    region_id: Mapped[int] = mapped_column(Integer, Identity(start=1), primary_key=True)
    region_code: Mapped[str] = mapped_column(String(10), unique=True, nullable=False)
    region_name: Mapped[str] = mapped_column(String(100), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    kris: Mapped[List["KriMaster"]] = relationship(back_populates="region")


# ─── KRI Category ───────────────────────────────────────────
class KriCategoryMaster(AuditMixin, Base):
    __tablename__ = "kri_category_master"
    category_id: Mapped[int] = mapped_column(Integer, Identity(start=1), primary_key=True)
    category_code: Mapped[str] = mapped_column(String(30), unique=True, nullable=False)
    category_name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String(500))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    kris: Mapped[List["KriMaster"]] = relationship(back_populates="category")


# ─── Control Dimension ──────────────────────────────────────
class ControlDimensionMaster(AuditMixin, Base):
    __tablename__ = "control_dimension_master"
    dimension_id: Mapped[int] = mapped_column(Integer, Identity(start=1), primary_key=True)
    dimension_code: Mapped[str] = mapped_column(String(30), unique=True, nullable=False)
    dimension_name: Mapped[str] = mapped_column(String(200), nullable=False)
    display_order: Mapped[int] = mapped_column(Integer, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String(500))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


# ─── KRI Master ─────────────────────────────────────────────
class KriMaster(AuditMixin, Base):
    __tablename__ = "kri_master"
    kri_id: Mapped[int] = mapped_column(Integer, Identity(start=1), primary_key=True)
    kri_code: Mapped[str] = mapped_column(String(30), unique=True, nullable=False)
    kri_name: Mapped[str] = mapped_column(String(300), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    category_id: Mapped[int] = mapped_column(Integer, ForeignKey("kri_category_master.category_id"), nullable=False)
    region_id: Mapped[int] = mapped_column(Integer, ForeignKey("region_master.region_id"), nullable=False)
    risk_level: Mapped[str] = mapped_column(String(20), default="MEDIUM")
    framework: Mapped[Optional[str]] = mapped_column(String(100))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    onboarded_dt: Mapped[Optional[datetime]] = mapped_column(DateTime)

    category: Mapped["KriCategoryMaster"] = relationship(back_populates="kris")
    region: Mapped["RegionMaster"] = relationship(back_populates="kris")
    configurations: Mapped[List["KriConfiguration"]] = relationship(back_populates="kri")
    assignments: Mapped[List["KriAssignment"]] = relationship(back_populates="kri")
    monthly_statuses: Mapped[List["MonthlyControlStatus"]] = relationship(back_populates="kri")
    evidence: Mapped[List["EvidenceMetadata"]] = relationship(back_populates="kri")


# ─── App User ───────────────────────────────────────────────
class AppUser(AuditMixin, Base):
    __tablename__ = "app_user"
    user_id: Mapped[int] = mapped_column(Integer, Identity(start=1), primary_key=True)
    soe_id: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    full_name: Mapped[str] = mapped_column(String(200), nullable=False)
    email: Mapped[str] = mapped_column(String(200), nullable=False)
    department: Mapped[Optional[str]] = mapped_column(String(100))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_login_dt: Mapped[Optional[datetime]] = mapped_column(DateTime)

    roles: Mapped[List["UserRoleMapping"]] = relationship(back_populates="user")


# ─── User Role Mapping ──────────────────────────────────────
class UserRoleMapping(AuditMixin, Base):
    __tablename__ = "user_role_mapping"
    mapping_id: Mapped[int] = mapped_column(Integer, Identity(start=1), primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("app_user.user_id"), nullable=False)
    role_code: Mapped[str] = mapped_column(String(30), nullable=False)
    region_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("region_master.region_id"))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    effective_to: Mapped[Optional[date]] = mapped_column(Date)

    user: Mapped["AppUser"] = relationship(back_populates="roles")
    region: Mapped[Optional["RegionMaster"]] = relationship()

    __table_args__ = (
        UniqueConstraint("user_id", "role_code", "region_id", name="uq_user_role_region"),
    )


# ─── KRI Configuration ─────────────────────────────────────
class KriConfiguration(AuditMixin, Base):
    __tablename__ = "kri_configuration"
    config_id: Mapped[int] = mapped_column(Integer, Identity(start=1), primary_key=True)
    kri_id: Mapped[int] = mapped_column(Integer, ForeignKey("kri_master.kri_id"), nullable=False)
    dimension_id: Mapped[int] = mapped_column(Integer, ForeignKey("control_dimension_master.dimension_id"), nullable=False)
    sla_days: Mapped[int] = mapped_column(Integer, default=3)
    variance_threshold: Mapped[float] = mapped_column(Float, default=10.0)
    rag_green_max: Mapped[Optional[float]] = mapped_column(Float)
    rag_amber_max: Mapped[Optional[float]] = mapped_column(Float)
    requires_evidence: Mapped[bool] = mapped_column(Boolean, default=True)
    requires_approval: Mapped[bool] = mapped_column(Boolean, default=True)
    freeze_day: Mapped[int] = mapped_column(Integer, default=15)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    kri: Mapped["KriMaster"] = relationship(back_populates="configurations")
    dimension: Mapped["ControlDimensionMaster"] = relationship()

    __table_args__ = (
        UniqueConstraint("kri_id", "dimension_id", name="uq_kri_dim"),
    )


# ─── KRI Assignment ─────────────────────────────────────────
class KriAssignment(AuditMixin, Base):
    __tablename__ = "kri_assignment"
    assignment_id: Mapped[int] = mapped_column(Integer, Identity(start=1), primary_key=True)
    kri_id: Mapped[int] = mapped_column(Integer, ForeignKey("kri_master.kri_id"), nullable=False)
    dimension_id: Mapped[int] = mapped_column(Integer, ForeignKey("control_dimension_master.dimension_id"), nullable=False)
    role_code: Mapped[str] = mapped_column(String(30), nullable=False)
    assigned_user_id: Mapped[int] = mapped_column(Integer, ForeignKey("app_user.user_id"), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    kri: Mapped["KriMaster"] = relationship(back_populates="assignments")
    dimension: Mapped["ControlDimensionMaster"] = relationship()
    assigned_user: Mapped["AppUser"] = relationship()


# ─── Data Source Mapping ────────────────────────────────────
class DataSourceMapping(AuditMixin, Base):
    __tablename__ = "data_source_mapping"
    source_id: Mapped[int] = mapped_column(Integer, Identity(start=1), primary_key=True)
    kri_id: Mapped[int] = mapped_column(Integer, ForeignKey("kri_master.kri_id"), nullable=False)
    source_name: Mapped[str] = mapped_column(String(200), nullable=False)
    source_type: Mapped[Optional[str]] = mapped_column(String(50))
    connection_info: Mapped[Optional[str]] = mapped_column(String(500))
    query_template: Mapped[Optional[str]] = mapped_column(Text)
    schedule_cron: Mapped[Optional[str]] = mapped_column(String(50))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


# ─── Monthly Control Status ─────────────────────────────────
class MonthlyControlStatus(AuditMixin, Base):
    __tablename__ = "monthly_control_status"
    status_id: Mapped[int] = mapped_column(Integer, Identity(start=1), primary_key=True)
    kri_id: Mapped[int] = mapped_column(Integer, ForeignKey("kri_master.kri_id"), nullable=False)
    dimension_id: Mapped[int] = mapped_column(Integer, ForeignKey("control_dimension_master.dimension_id"), nullable=False)
    period_year: Mapped[int] = mapped_column(Integer, nullable=False)
    period_month: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="NOT_STARTED")
    rag_status: Mapped[Optional[str]] = mapped_column(String(10))
    sla_due_dt: Mapped[Optional[datetime]] = mapped_column(DateTime)
    sla_met: Mapped[Optional[bool]] = mapped_column(Boolean)
    completed_dt: Mapped[Optional[datetime]] = mapped_column(DateTime)
    assigned_to: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("app_user.user_id"))
    current_approver: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("app_user.user_id"))
    approval_level: Mapped[Optional[str]] = mapped_column(String(10))

    kri: Mapped["KriMaster"] = relationship(back_populates="monthly_statuses")
    dimension: Mapped["ControlDimensionMaster"] = relationship()

    __table_args__ = (
        UniqueConstraint("kri_id", "dimension_id", "period_year", "period_month", name="uq_monthly_kri_dim"),
        Index("idx_mcs_period", "period_year", "period_month"),
    )


# ─── Metric Values ──────────────────────────────────────────
class MetricValues(AuditMixin, Base):
    __tablename__ = "metric_values"
    metric_id: Mapped[int] = mapped_column(Integer, Identity(start=1), primary_key=True)
    kri_id: Mapped[int] = mapped_column(Integer, ForeignKey("kri_master.kri_id"), nullable=False)
    dimension_id: Mapped[int] = mapped_column(Integer, ForeignKey("control_dimension_master.dimension_id"), nullable=False)
    period_year: Mapped[int] = mapped_column(Integer, nullable=False)
    period_month: Mapped[int] = mapped_column(Integer, nullable=False)
    current_value: Mapped[Optional[float]] = mapped_column(Float)
    previous_value: Mapped[Optional[float]] = mapped_column(Float)
    variance_pct: Mapped[Optional[float]] = mapped_column(Float)
    variance_status: Mapped[Optional[str]] = mapped_column(String(10))
    source_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("data_source_mapping.source_id"))
    captured_dt: Mapped[Optional[datetime]] = mapped_column(DateTime, default=datetime.utcnow)


# ─── Approval Audit Trail ───────────────────────────────────
class ApprovalAuditTrail(AuditMixin, Base):
    __tablename__ = "approval_audit_trail"
    audit_id: Mapped[int] = mapped_column(Integer, Identity(start=1), primary_key=True)
    status_id: Mapped[int] = mapped_column(Integer, ForeignKey("monthly_control_status.status_id"), nullable=False)
    action: Mapped[str] = mapped_column(String(30), nullable=False)
    performed_by: Mapped[int] = mapped_column(Integer, ForeignKey("app_user.user_id"), nullable=False)
    performed_dt: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    comments: Mapped[Optional[str]] = mapped_column(String(2000))
    previous_status: Mapped[Optional[str]] = mapped_column(String(20))
    new_status: Mapped[Optional[str]] = mapped_column(String(20))
    ip_address: Mapped[Optional[str]] = mapped_column(String(50))

    performer: Mapped["AppUser"] = relationship()
    control_status: Mapped["MonthlyControlStatus"] = relationship()


# ─── Evidence Metadata ──────────────────────────────────────
class EvidenceMetadata(AuditMixin, Base):
    __tablename__ = "evidence_metadata"
    evidence_id: Mapped[int] = mapped_column(Integer, Identity(start=1), primary_key=True)
    kri_id: Mapped[int] = mapped_column(Integer, ForeignKey("kri_master.kri_id"), nullable=False)
    dimension_id: Mapped[int] = mapped_column(Integer, ForeignKey("control_dimension_master.dimension_id"), nullable=False)
    period_year: Mapped[int] = mapped_column(Integer, nullable=False)
    period_month: Mapped[int] = mapped_column(Integer, nullable=False)
    file_name: Mapped[str] = mapped_column(String(500), nullable=False)
    file_type: Mapped[Optional[str]] = mapped_column(String(10))
    file_size_bytes: Mapped[Optional[int]] = mapped_column(Integer)
    s3_bucket: Mapped[Optional[str]] = mapped_column(String(200))
    s3_key: Mapped[Optional[str]] = mapped_column(String(500))
    version_number: Mapped[int] = mapped_column(Integer, default=1)
    is_locked: Mapped[bool] = mapped_column(Boolean, default=False)
    locked_dt: Mapped[Optional[datetime]] = mapped_column(DateTime)
    locked_by: Mapped[Optional[str]] = mapped_column(String(50))
    uploaded_by: Mapped[int] = mapped_column(Integer, ForeignKey("app_user.user_id"), nullable=False)
    uploaded_dt: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    metadata_json: Mapped[Optional[str]] = mapped_column(Text)

    region_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("region_master.region_id"))

    kri: Mapped["KriMaster"] = relationship(back_populates="evidence")
    uploader: Mapped["AppUser"] = relationship()
    region: Mapped[Optional["RegionMaster"]] = relationship()


# ─── Evidence Version Audit ─────────────────────────────────
class EvidenceVersionAudit(AuditMixin, Base):
    __tablename__ = "evidence_version_audit"
    version_id: Mapped[int] = mapped_column(Integer, Identity(start=1), primary_key=True)
    evidence_id: Mapped[int] = mapped_column(Integer, ForeignKey("evidence_metadata.evidence_id"), nullable=False)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    s3_key: Mapped[str] = mapped_column(String(500), nullable=False)
    file_size_bytes: Mapped[Optional[int]] = mapped_column(Integer)
    action: Mapped[Optional[str]] = mapped_column(String(20))
    performed_by: Mapped[int] = mapped_column(Integer, ForeignKey("app_user.user_id"), nullable=False)
    performed_dt: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    comments: Mapped[Optional[str]] = mapped_column(String(500))


# ─── Maker Checker Submission ───────────────────────────────
class MakerCheckerSubmission(AuditMixin, Base):
    __tablename__ = "maker_checker_submission"
    submission_id: Mapped[int] = mapped_column(Integer, Identity(start=1), primary_key=True)
    status_id: Mapped[int] = mapped_column(Integer, ForeignKey("monthly_control_status.status_id"), nullable=False)
    evidence_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("evidence_metadata.evidence_id"))
    submitted_by: Mapped[int] = mapped_column(Integer, ForeignKey("app_user.user_id"), nullable=False)
    submitted_dt: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    submission_notes: Mapped[Optional[str]] = mapped_column(Text)
    l1_approver_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("app_user.user_id"))
    l1_action: Mapped[Optional[str]] = mapped_column(String(20))
    l1_action_dt: Mapped[Optional[datetime]] = mapped_column(DateTime)
    l1_comments: Mapped[Optional[str]] = mapped_column(String(2000))
    l2_approver_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("app_user.user_id"))
    l2_action: Mapped[Optional[str]] = mapped_column(String(20))
    l2_action_dt: Mapped[Optional[datetime]] = mapped_column(DateTime)
    l2_comments: Mapped[Optional[str]] = mapped_column(String(2000))
    l3_approver_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("app_user.user_id"))
    l3_action: Mapped[Optional[str]] = mapped_column(String(20))
    l3_action_dt: Mapped[Optional[datetime]] = mapped_column(DateTime)
    l3_comments: Mapped[Optional[str]] = mapped_column(String(2000))
    final_status: Mapped[str] = mapped_column(String(20), default="PENDING")

    control_status: Mapped["MonthlyControlStatus"] = relationship()
    evidence: Mapped[Optional["EvidenceMetadata"]] = relationship()
    submitter: Mapped["AppUser"] = relationship(foreign_keys=[submitted_by])


# ─── Variance Submission ────────────────────────────────────
class VarianceSubmission(AuditMixin, Base):
    __tablename__ = "variance_submission"
    variance_id: Mapped[int] = mapped_column(Integer, Identity(start=1), primary_key=True)
    metric_id: Mapped[int] = mapped_column(Integer, ForeignKey("metric_values.metric_id"), nullable=False)
    status_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("monthly_control_status.status_id"))
    variance_pct: Mapped[float] = mapped_column(Float, nullable=False)
    commentary: Mapped[str] = mapped_column(Text, nullable=False)
    submitted_by: Mapped[int] = mapped_column(Integer, ForeignKey("app_user.user_id"), nullable=False)
    submitted_dt: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    review_status: Mapped[str] = mapped_column(String(20), default="PENDING")
    reviewed_by: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("app_user.user_id"))
    reviewed_dt: Mapped[Optional[datetime]] = mapped_column(DateTime)
    review_comments: Mapped[Optional[str]] = mapped_column(String(2000))

    metric: Mapped["MetricValues"] = relationship()


# ─── KRI Comments ───────────────────────────────────────────
class KriComment(AuditMixin, Base):
    __tablename__ = "kri_comments"
    comment_id: Mapped[int] = mapped_column(Integer, Identity(start=1), primary_key=True)
    kri_id: Mapped[int] = mapped_column(Integer, ForeignKey("kri_master.kri_id"), nullable=False)
    dimension_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("control_dimension_master.dimension_id"))
    status_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("monthly_control_status.status_id"))
    comment_text: Mapped[str] = mapped_column(Text, nullable=False)
    comment_type: Mapped[str] = mapped_column(String(20), default="GENERAL")
    parent_comment_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("kri_comments.comment_id"))
    posted_by: Mapped[int] = mapped_column(Integer, ForeignKey("app_user.user_id"), nullable=False)
    posted_dt: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    is_resolved: Mapped[bool] = mapped_column(Boolean, default=False)

    poster: Mapped["AppUser"] = relationship()


# ─── Escalation Config ──────────────────────────────────────
class EscalationConfig(AuditMixin, Base):
    __tablename__ = "escalation_config"
    config_id: Mapped[int] = mapped_column(Integer, Identity(start=1), primary_key=True)
    region_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("region_master.region_id"))
    escalation_type: Mapped[str] = mapped_column(String(30), nullable=False)
    threshold_hours: Mapped[int] = mapped_column(Integer, default=72)
    reminder_hours: Mapped[int] = mapped_column(Integer, default=24)
    max_reminders: Mapped[int] = mapped_column(Integer, default=3)
    escalate_to_role: Mapped[str] = mapped_column(String(30), nullable=False)
    email_template: Mapped[Optional[str]] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


# ─── Email Audit ────────────────────────────────────────────
class EmailAudit(AuditMixin, Base):
    __tablename__ = "email_audit"
    email_id: Mapped[int] = mapped_column(Integer, Identity(start=1), primary_key=True)
    recipient_email: Mapped[str] = mapped_column(String(200), nullable=False)
    recipient_name: Mapped[Optional[str]] = mapped_column(String(200))
    email_type: Mapped[str] = mapped_column(String(50), nullable=False)
    subject: Mapped[str] = mapped_column(String(500), nullable=False)
    body: Mapped[Optional[str]] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="QUEUED")
    sent_dt: Mapped[Optional[datetime]] = mapped_column(DateTime)
    error_message: Mapped[Optional[str]] = mapped_column(String(1000))
    related_kri_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("kri_master.kri_id"))
    related_status_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("monthly_control_status.status_id"))


# ─── Scheduler Lock ─────────────────────────────────────────
class SchedulerLock(Base):
    __tablename__ = "scheduler_lock"
    lock_id: Mapped[int] = mapped_column(Integer, Identity(start=1), primary_key=True)
    job_name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    locked_by: Mapped[str] = mapped_column(String(100), nullable=False)
    locked_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    is_locked: Mapped[bool] = mapped_column(Boolean, default=True)


# ─── Notification ───────────────────────────────────────────
class Notification(AuditMixin, Base):
    __tablename__ = "notification"
    notification_id: Mapped[int] = mapped_column(Integer, Identity(start=1), primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("app_user.user_id"), nullable=False)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    message: Mapped[str] = mapped_column(String(2000), nullable=False)
    notification_type: Mapped[Optional[str]] = mapped_column(String(30))
    is_read: Mapped[bool] = mapped_column(Boolean, default=False)
    link_url: Mapped[Optional[str]] = mapped_column(String(500))

    user: Mapped["AppUser"] = relationship()


# ─── Approval Assignment Rule ───────────────────────────────
class ApprovalAssignmentRule(AuditMixin, Base):
    """Priority-based rule engine for auto-assigning approvers to submissions.

    Resolution order (most-specific wins):
      kri_id match > category_id match > region_id match > global (all None)
    Lower priority number = higher precedence.
    """
    __tablename__ = "approval_assignment_rule"
    rule_id: Mapped[int] = mapped_column(Integer, Identity(start=1), primary_key=True)
    role_code: Mapped[str] = mapped_column(String(20), nullable=False)
    user_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("app_user.user_id"))
    region_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("region_master.region_id"))
    kri_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("kri_master.kri_id"))
    category_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("kri_category_master.category_id"))
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=100)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    user: Mapped[Optional["AppUser"]] = relationship()
    region: Mapped[Optional["RegionMaster"]] = relationship()
    kri: Mapped[Optional["KriMaster"]] = relationship()
    category: Mapped[Optional["KriCategoryMaster"]] = relationship()

    __table_args__ = (
        Index("idx_aar_role_region", "role_code", "region_id"),
    )


# ─── Saved View ─────────────────────────────────────────────
class SavedView(AuditMixin, Base):
    __tablename__ = "saved_view"
    view_id: Mapped[int] = mapped_column(Integer, Identity(start=1), primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("app_user.user_id"), nullable=False)
    view_name: Mapped[str] = mapped_column(String(200), nullable=False)
    view_type: Mapped[str] = mapped_column(String(30), nullable=False)
    filters_json: Mapped[Optional[str]] = mapped_column(Text)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
