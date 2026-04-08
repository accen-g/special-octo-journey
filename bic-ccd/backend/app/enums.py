"""
Central enum definitions for BIC-CCD.

This module is the SINGLE SOURCE OF TRUTH for all categorical values used in:
  1. Pydantic request/response validation (imported by schemas/__init__.py)
  2. SQLAlchemy ORM type hints (imported by models/__init__.py where needed)
  3. Oracle CHECK constraint DDL (imported by Alembic migrations via enum_values())

Rule: if a value is valid in any of the three layers above, it MUST appear here.
Rule: never define business-domain string literals anywhere else in the codebase.

DB_Design_Reference.pdf alignment:
  - ControlStatus   → BIC_KRI_CONTROL_STATUS_TRACKER.STATUS
  - RoleCode        → USER_ROLE_MAPPING.ROLE_CODE
  - RAGStatus       → BIC_KRI_METRIC.RAG_STATUS, BIC_KRI_CONTROL_STATUS_TRACKER.RAG_STATUS
  - ApprovalAction  → APPROVAL_AUDIT_TRAIL.ACTION
  - SubmissionFinalStatus → MAKER_CHECKER_SUBMISSION.FINAL_STATUS
  - EvidenceFileStatus   → BIC_KRI_EVIDENCE.FILE_STATUS
  - EscalationType       → ESCALATION_CONFIG.ESCALATION_TYPE
  - VarianceReviewStatus → VARIANCE_SUBMISSION.REVIEW_STATUS
  - NotificationType     → NOTIFICATION.NOTIFICATION_TYPE
  - ApprovalLevel        → BIC_KRI_CONTROL_STATUS_TRACKER.APPROVAL_LEVEL
  - VarianceStatus       → BIC_KRI_METRIC.VARIANCE_STATUS
"""
from enum import Enum
from typing import List, Type


# ─── Helper utilities ────────────────────────────────────────

def enum_values(cls: Type[Enum]) -> List[str]:
    """Return a list of string values for a StrEnum class.

    Primary use: generating Oracle CHECK constraint IN-lists in Alembic
    migrations so the DDL can never drift from the Python enum.

    Example:
        enum_values(ControlStatus)
        # → ['NOT_STARTED', 'IN_PROGRESS', 'PENDING_APPROVAL', ...]
    """
    return [m.value for m in cls]


def oracle_check_in(col: str, cls: Type[Enum]) -> str:
    """Build the Oracle CHECK constraint expression for an enum column.

    Example:
        oracle_check_in("STATUS", ControlStatus)
        # → "STATUS IN ('NOT_STARTED','IN_PROGRESS',...)"
    """
    values = ", ".join(f"'{v}'" for v in enum_values(cls))
    return f"{col} IN ({values})"


# ─── Core Status Enums ───────────────────────────────────────

class ControlStatus(str, Enum):
    """All valid values for BIC_KRI_CONTROL_STATUS_TRACKER.STATUS.

    Original BIC statuses (7 legacy values from schema.sql CHECK constraint):
      NOT_STARTED, IN_PROGRESS, PENDING_APPROVAL, APPROVED, REWORK,
      SLA_BREACHED, COMPLETED

    Phase 1C additions (BRD-required, additive only — existing values unchanged):
      SLA_MET, RECEIVED_POST_BREACH, REJECTED, RECEIVED, NOT_RECEIVED,
      INSUFFICIENT_MAPPING

    Evidence-scoped lifecycle statuses (used in EvidenceMetadata.evidence_status):
      DRAFT, ACTIVE, DELETED
    """
    # ── Original BIC 7 ──────────────────────────
    NOT_STARTED          = "NOT_STARTED"
    IN_PROGRESS          = "IN_PROGRESS"
    PENDING_APPROVAL     = "PENDING_APPROVAL"
    APPROVED             = "APPROVED"
    REWORK               = "REWORK"
    SLA_BREACHED         = "SLA_BREACHED"
    COMPLETED            = "COMPLETED"
    # ── Phase 1C additions ───────────────────────
    SLA_MET              = "SLA_MET"
    RECEIVED_POST_BREACH = "RECEIVED_POST_BREACH"
    REJECTED             = "REJECTED"
    RECEIVED             = "RECEIVED"
    NOT_RECEIVED         = "NOT_RECEIVED"
    INSUFFICIENT_MAPPING = "INSUFFICIENT_MAPPING"
    # ── Evidence lifecycle ────────────────────────
    DRAFT                = "DRAFT"
    ACTIVE               = "ACTIVE"
    DELETED              = "DELETED"


class RoleCode(str, Enum):
    """All valid values for USER_ROLE_MAPPING.ROLE_CODE.

    Original BIC roles (7 core roles from schema.sql CHECK constraint):
      MANAGEMENT, L1_APPROVER, L2_APPROVER, L3_ADMIN,
      DATA_PROVIDER, METRIC_OWNER, SYSTEM_ADMIN

    Phase 1C additions (BRD-required, additive only):
      UPLOAD, DOWNLOAD, SCORECARD_MAKER, SCORECARD_CHECKER, READ,
      ANC_APPROVER_L1, ANC_APPROVER_L2, ANC_APPROVER_L3
    """
    # ── Core 7 ──────────────────────────────────
    MANAGEMENT       = "MANAGEMENT"
    L1_APPROVER      = "L1_APPROVER"
    L2_APPROVER      = "L2_APPROVER"
    L3_ADMIN         = "L3_ADMIN"
    DATA_PROVIDER    = "DATA_PROVIDER"
    METRIC_OWNER     = "METRIC_OWNER"
    SYSTEM_ADMIN     = "SYSTEM_ADMIN"
    # ── Phase 1C additions ───────────────────────
    UPLOAD           = "UPLOAD"
    DOWNLOAD         = "DOWNLOAD"
    SCORECARD_MAKER  = "SCORECARD_MAKER"
    SCORECARD_CHECKER = "SCORECARD_CHECKER"
    READ             = "READ"
    ANC_APPROVER_L1  = "ANC_APPROVER_L1"
    ANC_APPROVER_L2  = "ANC_APPROVER_L2"
    ANC_APPROVER_L3  = "ANC_APPROVER_L3"


class RAGStatus(str, Enum):
    """RAG (Red/Amber/Green) rating values.

    GREY = no data / not applicable (BRD §11 gap, now included).
    Applies to: BIC_KRI_METRIC.RAG_STATUS, BIC_KRI_CONTROL_STATUS_TRACKER.RAG_STATUS (extra col).
    """
    GREEN = "GREEN"
    AMBER = "AMBER"
    RED   = "RED"
    GREY  = "GREY"


class ApprovalAction(str, Enum):
    """All valid values for APPROVAL_AUDIT_TRAIL.ACTION.

    Directly aligned with the schema.sql CHECK constraint on approval_audit_trail.
    """
    SUBMITTED   = "SUBMITTED"
    L1_APPROVED = "L1_APPROVED"
    L1_REJECTED = "L1_REJECTED"
    L1_REWORK   = "L1_REWORK"
    L2_APPROVED = "L2_APPROVED"
    L2_REJECTED = "L2_REJECTED"
    L2_REWORK   = "L2_REWORK"
    L3_APPROVED = "L3_APPROVED"
    L3_REJECTED = "L3_REJECTED"
    L3_REWORK   = "L3_REWORK"
    ESCALATED   = "ESCALATED"
    RECALLED    = "RECALLED"
    OVERRIDDEN  = "OVERRIDDEN"


class SubmissionFinalStatus(str, Enum):
    """All valid values for MAKER_CHECKER_SUBMISSION.FINAL_STATUS.

    Aligned with the schema.sql CHECK constraint on maker_checker_submission.
    """
    PENDING    = "PENDING"
    L1_PENDING = "L1_PENDING"
    L2_PENDING = "L2_PENDING"
    L3_PENDING = "L3_PENDING"
    APPROVED   = "APPROVED"
    REJECTED   = "REJECTED"
    REWORK     = "REWORK"


class EvidenceFileStatus(str, Enum):
    """Valid values for BIC_KRI_EVIDENCE.FILE_STATUS.

    DRAFT → ACTIVE lifecycle enforced in Phase 2 (BRD §8).
    LOCKED = immutable after freeze date.
    """
    DRAFT   = "DRAFT"
    ACTIVE  = "ACTIVE"
    LOCKED  = "LOCKED"
    DELETED = "DELETED"


class EscalationType(str, Enum):
    """Valid values for ESCALATION_CONFIG.ESCALATION_TYPE.

    Aligned with schema.sql CHECK constraint on escalation_config.
    """
    SLA_BREACH          = "SLA_BREACH"
    APPROVAL_DELAY      = "APPROVAL_DELAY"
    EVIDENCE_MISSING    = "EVIDENCE_MISSING"
    VARIANCE_UNRESOLVED = "VARIANCE_UNRESOLVED"


class VarianceReviewStatus(str, Enum):
    """Valid values for VARIANCE_SUBMISSION.REVIEW_STATUS.

    Aligned with schema.sql CHECK constraint on variance_submission.
    """
    PENDING  = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    REWORK   = "REWORK"


class NotificationType(str, Enum):
    """Valid values for NOTIFICATION.NOTIFICATION_TYPE.

    Aligned with schema.sql CHECK constraint on notification.
    """
    APPROVAL_REQUEST = "APPROVAL_REQUEST"
    SLA_WARNING      = "SLA_WARNING"
    ESCALATION       = "ESCALATION"
    REWORK           = "REWORK"
    EVIDENCE_REQUIRED = "EVIDENCE_REQUIRED"
    SYSTEM           = "SYSTEM"
    VARIANCE         = "VARIANCE"


class ApprovalLevel(str, Enum):
    """Valid values for BIC_KRI_CONTROL_STATUS_TRACKER.APPROVAL_LEVEL.

    Aligned with schema.sql CHECK constraint on monthly_control_status.
    """
    L1 = "L1"
    L2 = "L2"
    L3 = "L3"


class VarianceStatus(str, Enum):
    """Valid values for BIC_KRI_METRIC.VARIANCE_STATUS.

    Aligned with schema.sql CHECK constraint on metric_values.
    """
    PASS = "PASS"
    FAIL = "FAIL"


class RiskLevel(str, Enum):
    """Valid values for BIC_KRI_CONFIG.RISK_LEVEL (extra column, not in BIC spec).

    Aligned with schema.sql CHECK constraint on kri_master.
    """
    LOW      = "LOW"
    MEDIUM   = "MEDIUM"
    HIGH     = "HIGH"
    CRITICAL = "CRITICAL"


class EvidenceAction(str, Enum):
    """Valid values for BIC_KRI_CONTROL_EVIDENCE_AUDIT.ACTION (extra col).

    Aligned with schema.sql CHECK constraint on evidence_version_audit.
    """
    UPLOAD  = "UPLOAD"
    REPLACE = "REPLACE"
    DELETE  = "DELETE"
    LOCK    = "LOCK"
    UNLOCK  = "UNLOCK"


class DataSourceType(str, Enum):
    """Valid values for BIC_KRI_DATA_SOURCE_MAPPING source_type (extra col).

    Aligned with schema.sql CHECK constraint on data_source_mapping.
    """
    DATABASE = "DATABASE"
    FILE     = "FILE"
    API      = "API"
    MANUAL   = "MANUAL"


class CommentType(str, Enum):
    """Valid values for BIC_KRI_COMMENT.COMMENT_TYPE (extra col).

    Aligned with schema.sql CHECK constraint on kri_comments.
    """
    GENERAL   = "GENERAL"
    APPROVAL  = "APPROVAL"
    REWORK    = "REWORK"
    ESCALATION = "ESCALATION"
    VARIANCE  = "VARIANCE"


# ─── Convenience groupings ───────────────────────────────────

#: Statuses that count as "terminal" — no further workflow transitions
TERMINAL_STATUSES = frozenset({
    ControlStatus.APPROVED,
    ControlStatus.COMPLETED,
    ControlStatus.SLA_MET,
    ControlStatus.REJECTED,
    ControlStatus.DELETED,
})

#: Statuses that the MANAGEMENT simplified view maps to PASS
MANAGEMENT_PASS_STATUSES = frozenset({
    ControlStatus.COMPLETED,
    ControlStatus.APPROVED,
    ControlStatus.SLA_MET,
})

#: Statuses that the MANAGEMENT simplified view maps to FAIL
MANAGEMENT_FAIL_STATUSES = frozenset({
    ControlStatus.SLA_BREACHED,
    ControlStatus.RECEIVED_POST_BREACH,
    ControlStatus.REJECTED,
    ControlStatus.REWORK,
})

#: Roles that can approve at any level (used in RBAC helpers)
APPROVER_ROLES = frozenset({
    RoleCode.L1_APPROVER,
    RoleCode.L2_APPROVER,
    RoleCode.L3_ADMIN,
    RoleCode.SYSTEM_ADMIN,
    RoleCode.ANC_APPROVER_L1,
    RoleCode.ANC_APPROVER_L2,
    RoleCode.ANC_APPROVER_L3,
    RoleCode.SCORECARD_CHECKER,
})
