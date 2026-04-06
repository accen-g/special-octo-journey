"""Utility functions for BIC-CCD backend."""
from math import ceil


def paginate_response(items: list, total: int, page: int, page_size: int) -> dict:
    """Standard paginated response format."""
    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": ceil(total / page_size) if page_size > 0 else 0,
        "has_next": page * page_size < total,
        "has_prev": page > 1,
    }


# Role constants
ROLES = {
    "MANAGEMENT": "Management",
    "L1_APPROVER": "L1 Approver",
    "L2_APPROVER": "L2 Approver",
    "L3_ADMIN": "L3 / Admin",
    "DATA_PROVIDER": "Data Provider",
    "METRIC_OWNER": "Metric Owner",
    "SYSTEM_ADMIN": "System Admin",
}

# Status constants
STATUSES = {
    "NOT_STARTED": "Not Started",
    "IN_PROGRESS": "In Progress",
    "PENDING_APPROVAL": "Pending Approval",
    "APPROVED": "Approved",
    "REWORK": "Rework",
    "SLA_BREACHED": "SLA Breached",
    "COMPLETED": "Completed",
}

# Allowed file types for evidence
ALLOWED_FILE_TYPES = {"xlsx", "msg", "pdf", "pptx", "csv", "docx"}

# SLA defaults
DEFAULT_SLA_DAYS = 3
DEFAULT_VARIANCE_THRESHOLD = 10.0
DEFAULT_FREEZE_DAY = 15

# ─── Management Status Mapping ─────────────────────────────────────────────────
# Maps granular internal statuses → simplified 3-value view for MANAGEMENT role.
# Never stored in DB — applied at serialization time, gated by caller role.
MANAGEMENT_STATUS_MAP: dict[str, str] = {
    "NOT_STARTED":       "IN_PROGRESS",
    "IN_PROGRESS":       "IN_PROGRESS",
    "PENDING_APPROVAL":  "IN_PROGRESS",
    "NOT_RECEIVED":      "IN_PROGRESS",
    "SLA_MET":           "PASS",
    "COMPLETED":         "PASS",
    "APPROVED":          "PASS",
    "SLA_BREACHED":      "FAIL",
    "RECEIVED_POST_BREACH": "FAIL",
    "ADMIN_RESET":       "FAIL",
    "REWORK":            "FAIL",
    # Special pass-through values
    "INSUFFICIENT_MAPPING": "INSUFFICIENT_MAPPING",
    "N/A":               "N/A",
}


def to_management_status(raw_status: str) -> str:
    """Convert a raw internal status to the simplified management view.

    Falls back to 'IN_PROGRESS' for any unrecognised status so new statuses
    added later don't silently surface granular values to management.
    """
    return MANAGEMENT_STATUS_MAP.get(raw_status, "IN_PROGRESS")


def compute_pending_with(sub) -> str:
    """Derive which approval level currently holds the submission.

    Computed from lN_action IS NULL so frontend never has to replicate
    the state machine logic.
    """
    if sub.l1_action is None:
        return "L1" if sub.l1_approver_id else "L1 (Unassigned)"
    if sub.l2_action is None:
        return "L2" if sub.l2_approver_id else "L2 (Unassigned)"
    if sub.l3_action is None:
        return "L3" if sub.l3_approver_id else "L3 (Unassigned)"
    return "Complete"
