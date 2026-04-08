"""Utility functions for BIC-CCD backend."""
from math import ceil
import json
import re
from typing import Optional


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
    # Phase 1C additions
    "UPLOAD": "Upload",
    "DOWNLOAD": "Download",
    "SCORECARD_MAKER": "Scorecard Maker",
    "SCORECARD_CHECKER": "Scorecard Checker",
    "READ": "Read Only",
    "ANC_APPROVER_L1": "ANC Approver L1",
    "ANC_APPROVER_L2": "ANC Approver L2",
    "ANC_APPROVER_L3": "ANC Approver L3",
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
    # Phase 1C additions
    "SLA_MET": "SLA Met",
    "RECEIVED_POST_BREACH": "Received Post Breach",
    "REJECTED": "Rejected",
    "RECEIVED": "Received",
    "NOT_RECEIVED": "Not Received",
    "INSUFFICIENT_MAPPING": "Insufficient Mapping",
    "DRAFT": "Draft",
    "ACTIVE": "Active",
    "DELETED": "Deleted",
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
    "REJECTED":          "FAIL",
    "ADMIN_RESET":       "FAIL",
    "REWORK":            "FAIL",
    # Special pass-through values
    "INSUFFICIENT_MAPPING": "INSUFFICIENT_MAPPING",
    "N/A":               "N/A",
}


def compute_rag(
    metric_value: float,
    rag_thresholds: Optional[str],
    rag_green_max: Optional[float] = None,
    rag_amber_max: Optional[float] = None,
) -> str:
    """Compute RAG status from metric value.

    Tries structured ``rag_thresholds`` JSON first (Phase 1 field).
    Falls back to scalar ``rag_green_max`` / ``rag_amber_max`` for
    existing records that have not been migrated to structured bands.

    Structured format: [{"color": "GREEN", "min": 0, "max": 5}, ...]
    A band matches when min <= metric_value <= max (both inclusive).
    Returns "GREY" when no band matches or value is None.
    """
    if metric_value is None:
        return "GREY"

    if rag_thresholds:
        try:
            bands = json.loads(rag_thresholds)
            for band in bands:
                lo = band.get("min")
                hi = band.get("max")
                color = band.get("color", "").upper()
                lo_ok = lo is None or metric_value >= lo
                hi_ok = hi is None or metric_value <= hi
                if lo_ok and hi_ok:
                    return color
        except (json.JSONDecodeError, TypeError):
            pass  # fall through to scalar fallback

    # Scalar fallback: value <= green_max → GREEN, <= amber_max → AMBER, else RED
    if rag_green_max is not None and metric_value <= rag_green_max:
        return "GREEN"
    if rag_amber_max is not None and metric_value <= rag_amber_max:
        return "AMBER"
    if rag_green_max is not None or rag_amber_max is not None:
        return "RED"

    return "GREY"


_KRI_CODE_PREFIX_ORDER = {"UK": 0, "SGP": 1, "CEP": 2}


def sort_kris(kris: list) -> list:
    """Sort KRI objects/dicts by BRD-specified priority.

    Priority: UK-K* → SGP-K* → CEP-K* → others, alphabetical within each group.
    Works with both ORM objects (kri.kri_code) and plain dicts (kri["kri_code"]).
    """
    def _sort_key(kri):
        code = kri.kri_code if hasattr(kri, "kri_code") else kri.get("kri_code", "")
        # Extract region prefix from code like "KRI-UK-001" or "UK-K001"
        match = re.match(r"[A-Z]+-([A-Z]+)-", code) or re.match(r"([A-Z]+)-", code)
        prefix = match.group(1) if match else ""
        return (_KRI_CODE_PREFIX_ORDER.get(prefix, 99), code)

    return sorted(kris, key=_sort_key)


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
