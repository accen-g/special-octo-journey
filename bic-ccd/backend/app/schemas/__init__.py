"""Pydantic V2 schemas for BIC-CCD API."""
from datetime import datetime, date
from typing import Optional, List, Any
from pydantic import BaseModel, Field, ConfigDict
from enum import Enum


# ─── Enums ──────────────────────────────────────────────────
class RoleCode(str, Enum):
    MANAGEMENT = "MANAGEMENT"
    L1_APPROVER = "L1_APPROVER"
    L2_APPROVER = "L2_APPROVER"
    L3_ADMIN = "L3_ADMIN"
    DATA_PROVIDER = "DATA_PROVIDER"
    METRIC_OWNER = "METRIC_OWNER"
    SYSTEM_ADMIN = "SYSTEM_ADMIN"


class RiskLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class ControlStatus(str, Enum):
    NOT_STARTED = "NOT_STARTED"
    IN_PROGRESS = "IN_PROGRESS"
    PENDING_APPROVAL = "PENDING_APPROVAL"
    APPROVED = "APPROVED"
    REWORK = "REWORK"
    SLA_BREACHED = "SLA_BREACHED"
    COMPLETED = "COMPLETED"


class RAGStatus(str, Enum):
    GREEN = "GREEN"
    AMBER = "AMBER"
    RED = "RED"


class ApprovalAction(str, Enum):
    SUBMITTED = "SUBMITTED"
    L1_APPROVED = "L1_APPROVED"
    L1_REJECTED = "L1_REJECTED"
    L1_REWORK = "L1_REWORK"
    L2_APPROVED = "L2_APPROVED"
    L2_REJECTED = "L2_REJECTED"
    L2_REWORK = "L2_REWORK"
    L3_APPROVED = "L3_APPROVED"
    L3_REJECTED = "L3_REJECTED"
    L3_REWORK = "L3_REWORK"
    ESCALATED = "ESCALATED"
    RECALLED = "RECALLED"
    OVERRIDDEN = "OVERRIDDEN"


class SubmissionStatus(str, Enum):
    PENDING = "PENDING"
    L1_PENDING = "L1_PENDING"
    L2_PENDING = "L2_PENDING"
    L3_PENDING = "L3_PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    REWORK = "REWORK"


class VarianceReviewStatus(str, Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    REWORK = "REWORK"


# ─── Auth ───────────────────────────────────────────────────
class LoginRequest(BaseModel):
    soe_id: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: "UserResponse"


class CurrentUser(BaseModel):
    user_id: int
    soe_id: str
    full_name: str
    email: str
    roles: List[dict]


# ─── Region ─────────────────────────────────────────────────
class RegionBase(BaseModel):
    region_code: str = Field(max_length=10)
    region_name: str = Field(max_length=100)
    is_active: bool = True

class RegionCreate(RegionBase):
    pass

class RegionResponse(RegionBase):
    model_config = ConfigDict(from_attributes=True)
    region_id: int
    created_dt: datetime


# ─── KRI Category ───────────────────────────────────────────
class CategoryBase(BaseModel):
    category_code: str = Field(max_length=30)
    category_name: str = Field(max_length=200)
    description: Optional[str] = None
    is_active: bool = True

class CategoryCreate(CategoryBase):
    pass

class CategoryResponse(CategoryBase):
    model_config = ConfigDict(from_attributes=True)
    category_id: int


# ─── Control Dimension ──────────────────────────────────────
class DimensionBase(BaseModel):
    dimension_code: str
    dimension_name: str
    display_order: int
    description: Optional[str] = None
    is_active: bool = True

class DimensionResponse(DimensionBase):
    model_config = ConfigDict(from_attributes=True)
    dimension_id: int


# ─── User ───────────────────────────────────────────────────
class UserBase(BaseModel):
    soe_id: str = Field(max_length=20)
    full_name: str = Field(max_length=200)
    email: str = Field(max_length=200)
    department: Optional[str] = None

class UserCreate(UserBase):
    password: Optional[str] = None
    roles: Optional[List[dict]] = None

class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    email: Optional[str] = None
    department: Optional[str] = None
    is_active: Optional[bool] = None

class UserResponse(UserBase):
    model_config = ConfigDict(from_attributes=True)
    user_id: int
    is_active: bool
    last_login_dt: Optional[datetime] = None
    roles: Optional[List[dict]] = None


# ─── Role Mapping ───────────────────────────────────────────
class RoleAssignment(BaseModel):
    user_id: int
    role_code: RoleCode
    region_id: Optional[int] = None
    effective_from: date
    effective_to: Optional[date] = None

class RoleAssignmentResponse(RoleAssignment):
    model_config = ConfigDict(from_attributes=True)
    mapping_id: int
    is_active: bool


# ─── KRI ────────────────────────────────────────────────────
class KriBase(BaseModel):
    kri_code: str = Field(max_length=30)
    kri_name: str = Field(max_length=300)
    description: Optional[str] = None
    category_id: int
    region_id: int
    risk_level: RiskLevel = RiskLevel.MEDIUM
    framework: Optional[str] = None

class KriCreate(KriBase):
    pass

class KriUpdate(BaseModel):
    kri_name: Optional[str] = None
    description: Optional[str] = None
    category_id: Optional[int] = None
    risk_level: Optional[RiskLevel] = None
    framework: Optional[str] = None
    is_active: Optional[bool] = None

class KriResponse(KriBase):
    model_config = ConfigDict(from_attributes=True)
    kri_id: int
    is_active: bool
    onboarded_dt: Optional[datetime] = None
    created_dt: datetime
    category_name: Optional[str] = None
    region_name: Optional[str] = None


# ─── KRI Configuration ─────────────────────────────────────
class KriConfigBase(BaseModel):
    kri_id: int
    dimension_id: int
    sla_days: int = 3
    variance_threshold: float = 10.0
    rag_green_max: Optional[float] = None
    rag_amber_max: Optional[float] = None
    requires_evidence: bool = True
    requires_approval: bool = True
    freeze_day: int = 15

class KriConfigCreate(KriConfigBase):
    pass

class KriConfigResponse(KriConfigBase):
    model_config = ConfigDict(from_attributes=True)
    config_id: int
    is_active: bool
    dimension_name: Optional[str] = None


# ─── Monthly Control Status ─────────────────────────────────
class MonthlyStatusBase(BaseModel):
    kri_id: int
    dimension_id: int
    period_year: int
    period_month: int

class MonthlyStatusResponse(MonthlyStatusBase):
    model_config = ConfigDict(from_attributes=True)
    status_id: int
    status: ControlStatus
    rag_status: Optional[RAGStatus] = None
    sla_due_dt: Optional[datetime] = None
    sla_met: Optional[bool] = None
    completed_dt: Optional[datetime] = None
    approval_level: Optional[str] = None
    kri_name: Optional[str] = None
    kri_code: Optional[str] = None
    dimension_name: Optional[str] = None
    region_name: Optional[str] = None
    category_name: Optional[str] = None
    assigned_to_name: Optional[str] = None


# ─── Approval ───────────────────────────────────────────────
class ApprovalActionRequest(BaseModel):
    action: ApprovalAction
    comments: Optional[str] = None

class ApprovalAuditResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    audit_id: int
    status_id: int
    action: str
    performed_by: int
    performed_dt: datetime
    comments: Optional[str] = None
    previous_status: Optional[str] = None
    new_status: Optional[str] = None
    performer_name: Optional[str] = None


# ─── Evidence ───────────────────────────────────────────────
class EvidenceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    evidence_id: int
    kri_id: int
    dimension_id: int
    period_year: int
    period_month: int
    file_name: str
    file_type: Optional[str] = None
    file_size_bytes: Optional[int] = None
    version_number: int
    is_locked: bool
    uploaded_by: int
    uploaded_dt: datetime
    uploader_name: Optional[str] = None
    kri_name: Optional[str] = None


# ─── Maker Checker ──────────────────────────────────────────
class MakerCheckerSubmitRequest(BaseModel):
    status_id: int
    evidence_id: Optional[int] = None
    submission_notes: Optional[str] = None
    l1_approver_id: Optional[int] = None  # auto-resolved from assignment rules when omitted

class MakerCheckerResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    submission_id: int
    status_id: int
    submitted_by: int
    submitted_dt: datetime
    final_status: str
    l1_approver_id: Optional[int] = None
    l1_action: Optional[str] = None
    l2_approver_id: Optional[int] = None
    l2_action: Optional[str] = None
    l3_approver_id: Optional[int] = None
    l3_action: Optional[str] = None
    submitter_name: Optional[str] = None
    kri_name: Optional[str] = None


class MakerCheckerActionRequest(BaseModel):
    action: str  # APPROVED, REJECTED, REWORK
    comments: Optional[str] = None
    next_approver_id: Optional[int] = None


# ─── Variance ───────────────────────────────────────────────
class VarianceSubmitRequest(BaseModel):
    metric_id: int
    status_id: Optional[int] = None
    commentary: str

class VarianceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    variance_id: int
    metric_id: int
    variance_pct: float
    commentary: str
    submitted_by: int
    submitted_dt: datetime
    review_status: str
    reviewed_by: Optional[int] = None
    review_comments: Optional[str] = None
    kri_name: Optional[str] = None


# ─── Metric Values ──────────────────────────────────────────
class MetricValueResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    metric_id: int
    kri_id: int
    dimension_id: int
    period_year: int
    period_month: int
    current_value: Optional[float] = None
    previous_value: Optional[float] = None
    variance_pct: Optional[float] = None
    variance_status: Optional[str] = None


# ─── Dashboard ──────────────────────────────────────────────
class DashboardSummary(BaseModel):
    total_kris: int
    sla_met: int
    sla_met_pct: float
    sla_breached: int
    sla_breached_pct: float
    not_started: int
    not_started_pct: float
    pending_approvals: int
    regions: List[str]
    period: str
    last_updated: Optional[datetime] = None


class RAGBreakdown(BaseModel):
    green: int
    amber: int
    red: int
    total: int


class TrendDataPoint(BaseModel):
    period: str
    sla_met: int
    sla_breached: int
    not_started: int


class DimensionBreakdown(BaseModel):
    dimension_name: str
    sla_met: int
    breached: int
    not_started: int


class ControlHealthRadar(BaseModel):
    dimension: str
    met: int
    breached: int
    not_started: int


# ─── Escalation Config ──────────────────────────────────────
class EscalationConfigBase(BaseModel):
    region_id: Optional[int] = None
    escalation_type: str
    threshold_hours: int = 72
    reminder_hours: int = 24
    max_reminders: int = 3
    escalate_to_role: str
    email_template: Optional[str] = None

class EscalationConfigCreate(EscalationConfigBase):
    pass

class EscalationConfigUpdate(BaseModel):
    escalation_type: Optional[str] = None
    threshold_hours: Optional[int] = None
    reminder_hours: Optional[int] = None
    max_reminders: Optional[int] = None
    escalate_to_role: Optional[str] = None
    region_id: Optional[int] = None
    email_template: Optional[str] = None

class EscalationConfigResponse(EscalationConfigBase):
    model_config = ConfigDict(from_attributes=True)
    config_id: int
    is_active: bool


# ─── Notification ───────────────────────────────────────────
class NotificationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    notification_id: int
    title: str
    message: str
    notification_type: Optional[str] = None
    is_read: bool
    link_url: Optional[str] = None
    created_dt: datetime


# ─── KRI Comments ───────────────────────────────────────────
class CommentCreate(BaseModel):
    kri_id: int
    dimension_id: Optional[int] = None
    status_id: Optional[int] = None
    comment_text: str
    comment_type: str = "GENERAL"
    parent_comment_id: Optional[int] = None

class CommentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    comment_id: int
    kri_id: int
    comment_text: str
    comment_type: str
    posted_by: int
    posted_dt: datetime
    is_resolved: bool
    poster_name: Optional[str] = None


# ─── KRI Onboarding Wizard ──────────────────────────────────
class KriOnboardRequest(BaseModel):
    """Multi-step wizard payload."""
    # Step 1: Basic info
    kri_code: str
    kri_name: str
    description: Optional[str] = None
    category_id: int
    region_id: int
    risk_level: RiskLevel = RiskLevel.MEDIUM
    framework: Optional[str] = None
    # Step 2: Control dimensions config
    dimensions: List[KriConfigCreate] = []
    # Step 3: Assignments
    assignments: List[dict] = []
    # Step 4: Data sources
    data_sources: List[dict] = []


# ─── Pagination ─────────────────────────────────────────────
class PaginatedResponse(BaseModel):
    items: List[Any]
    total: int
    page: int
    page_size: int
    total_pages: int


# ─── Data Source ────────────────────────────────────────────
class DataSourceBase(BaseModel):
    kri_id: int
    source_name: str
    source_type: Optional[str] = None
    connection_info: Optional[str] = None
    query_template: Optional[str] = None
    schedule_cron: Optional[str] = None

class DataSourceCreate(DataSourceBase):
    pass

class DataSourceResponse(DataSourceBase):
    model_config = ConfigDict(from_attributes=True)
    source_id: int
    is_active: bool
