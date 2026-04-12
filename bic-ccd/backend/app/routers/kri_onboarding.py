"""KRI Onboarding (Bluesheet) router.

Handles the full KRI onboarding lifecycle:
  GET  /api/kri-onboarding           — list all KRIs with approval status
  GET  /api/kri-onboarding/{kri_id}  — full detail (bluesheet + approval log)
  POST /api/kri-onboarding           — submit new KRI (all 7 wizard steps)
  POST /api/kri-onboarding/{kri_id}/runbook  — upload runbook file
  POST /api/kri-onboarding/{kri_id}/approve  — L3 approve / reject / rework
"""
from datetime import datetime, date
from typing import Optional, List
import os, uuid

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, UploadFile, File, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import KriMaster, KriBluesheet, KriApprovalLog, AppUser, RegionMaster, KriCategoryMaster
from app.schemas import KriBluesheetCreate, KriBluesheetResponse, KriApprovalLogResponse, KriApprovalActionRequest, KriConfigListItem
from app.middleware import get_current_user, require_l3, require_any_authenticated

router = APIRouter(prefix="/api/kri-onboarding", tags=["KRI Onboarding"])

# Import lazily to avoid circular imports at module load time
def _get_email_trigger():
    from app.routers.audit_evidence import trigger_outbound_email_background
    return trigger_outbound_email_background

# S3-compatible path template (hardcoded as per spec)
S3_BUCKET = "bic-kri-runbooks"
_RUNBOOK_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "runbooks")


def _s3_path(kri_code: str, filename: str) -> str:
    region = kri_code.split("-")[0].lower() if kri_code else "uk"
    return f"s3://{S3_BUCKET}/{region}/{kri_code}/{filename}"


def _ensure_runbook_dir(kri_code: str) -> str:
    region = kri_code.split("-")[0].lower() if kri_code else "uk"
    path = os.path.join(_RUNBOOK_DIR, region, kri_code)
    os.makedirs(path, exist_ok=True)
    return path


def _bluesheet_to_dict(bs: KriBluesheet) -> dict:
    """Flatten bluesheet + parent KRI into a response dict."""
    kri = bs.kri
    return {
        "bluesheet_id": bs.bluesheet_id,
        "kri_id": bs.kri_id,
        "kri_code": kri.kri_code if kri else None,
        "kri_name": kri.kri_name if kri else None,
        "description": kri.description if kri else None,
        "region_name": kri.region.region_name if kri and kri.region else None,
        "category_name": kri.category.category_name if kri and kri.category else None,
        "risk_level": kri.risk_level if kri else None,
        "frequency": kri.frequency if kri else None,
        "legacy_kri_id": bs.legacy_kri_id,
        "threshold": bs.threshold,
        "circuit_breaker": bs.circuit_breaker,
        "control_ids": bs.control_ids,
        "dq_objectives": bs.dq_objectives,
        "primary_senior_manager": bs.primary_senior_manager,
        "metric_owner_name": bs.metric_owner_name,
        "remediation_owner_name": bs.remediation_owner_name,
        "bi_metrics_lead": bs.bi_metrics_lead,
        "data_provider_name": bs.data_provider_name,
        "sc_uk": bs.sc_uk,
        "sc_finance": bs.sc_finance,
        "sc_risk": bs.sc_risk,
        "sc_liquidity": bs.sc_liquidity,
        "sc_capital": bs.sc_capital,
        "sc_risk_reports": bs.sc_risk_reports,
        "sc_markets": bs.sc_markets,
        "why_selected": bs.why_selected,
        "threshold_rationale": bs.threshold_rationale,
        "limitations": bs.limitations,
        "kri_calculation": bs.kri_calculation,
        "runbook_s3_path": bs.runbook_s3_path,
        "runbook_filename": bs.runbook_filename,
        "runbook_version": bs.runbook_version,
        "runbook_review_date": bs.runbook_review_date,
        "runbook_notes": bs.runbook_notes,
        "approval_status": bs.approval_status,
        "submitted_by": bs.submitted_by,
        "submitted_dt": bs.submitted_dt,
        "submitter_name": bs.submitter.full_name if bs.submitter else None,
        "created_dt": bs.created_dt,
    }


# ═══════════════════════════════════════════════════════════
# LIST
# ═══════════════════════════════════════════════════════════

@router.get("")
def list_kri_onboarding(
    approval_status: Optional[str] = None,
    region_id: Optional[int] = None,
    search: Optional[str] = None,
    db: Session = Depends(get_db),
    _user: dict = Depends(require_any_authenticated),
):
    """Return all KRIs for the KRI Config listing table.

    Includes:
    1. KRIs with a bluesheet (onboarded via the wizard) — full detail.
    2. KRIs WITHOUT a bluesheet (Data Control / seeded KRIs) — shown as ACTIVE,
       view-only entries so the Config page is kept in sync with Data Control.
    """
    # ── (1) Bluesheet-backed KRIs ──────────────────────────────
    bs_query = db.query(KriBluesheet).join(KriMaster, KriBluesheet.kri_id == KriMaster.kri_id)

    if approval_status and approval_status != "ACTIVE":
        bs_query = bs_query.filter(KriBluesheet.approval_status == approval_status)
    elif approval_status == "ACTIVE":
        # "ACTIVE" is a virtual status for Data Control KRIs — skip bluesheet rows
        bs_query = bs_query.filter(False)
    if region_id:
        bs_query = bs_query.filter(KriMaster.region_id == region_id)
    if search:
        s = f"%{search.lower()}%"
        bs_query = bs_query.filter(
            (KriMaster.kri_code.ilike(s)) | (KriMaster.kri_name.ilike(s))
        )

    bluesheet_rows = bs_query.all()
    bluesheet_kri_ids = {bs.kri_id for bs in bluesheet_rows}
    result = [_bluesheet_to_dict(bs) for bs in bluesheet_rows]

    # ── (2) KRIs WITHOUT a bluesheet (Data Control KRIs) ──────
    if not approval_status or approval_status == "ACTIVE":
        dc_query = (
            db.query(KriMaster)
            .filter(~KriMaster.kri_id.in_(bluesheet_kri_ids) if bluesheet_kri_ids else True)
        )
        if region_id:
            dc_query = dc_query.filter(KriMaster.region_id == region_id)
        if search:
            s = f"%{search.lower()}%"
            dc_query = dc_query.filter(
                (KriMaster.kri_code.ilike(s)) | (KriMaster.kri_name.ilike(s))
            )

        for kri in dc_query.all():
            result.append({
                "bluesheet_id": None,
                "kri_id": kri.kri_id,
                "kri_code": kri.kri_code,
                "kri_name": kri.kri_name,
                "description": kri.description,
                "region_name": kri.region.region_name if kri.region else None,
                "category_name": kri.category.category_name if kri and kri.category else None,
                "risk_level": kri.risk_level,
                "frequency": kri.frequency,
                # All role/bluesheet fields null — these are Data Control KRIs
                "legacy_kri_id": None, "threshold": None, "circuit_breaker": None,
                "control_ids": None, "dq_objectives": None,
                "primary_senior_manager": None, "metric_owner_name": None,
                "remediation_owner_name": None, "bi_metrics_lead": None,
                "data_provider_name": None,
                "sc_uk": False, "sc_finance": False, "sc_risk": False,
                "sc_liquidity": False, "sc_capital": False, "sc_risk_reports": False,
                "sc_markets": False,
                "why_selected": None, "threshold_rationale": None,
                "limitations": None, "kri_calculation": None,
                "runbook_s3_path": None, "runbook_filename": None,
                "runbook_version": None, "runbook_review_date": None, "runbook_notes": None,
                # Mark as ACTIVE (already live in Data Control — not pending onboarding)
                "approval_status": "ACTIVE",
                "submitted_by": None, "submitted_dt": None,
                "submitter_name": None, "created_dt": kri.onboarded_dt,
                "version": None,
            })

    return result


# ═══════════════════════════════════════════════════════════
# DETAIL
# ═══════════════════════════════════════════════════════════

@router.get("/{kri_id}")
def get_kri_onboarding_detail(
    kri_id: int,
    db: Session = Depends(get_db),
    _user: dict = Depends(require_any_authenticated),
):
    bs = db.query(KriBluesheet).filter(KriBluesheet.kri_id == kri_id).first()
    if not bs:
        raise HTTPException(status_code=404, detail="KRI bluesheet not found")

    # Fetch approval log
    logs = (
        db.query(KriApprovalLog)
        .filter(KriApprovalLog.kri_id == kri_id)
        .order_by(KriApprovalLog.performed_dt)
        .all()
    )
    log_items = [
        {
            "log_id": lg.log_id,
            "action": lg.action,
            "performed_by": lg.performed_by,
            "performer_name": lg.performer.full_name if lg.performer else None,
            "performed_dt": lg.performed_dt,
            "comments": lg.comments,
            "previous_status": lg.previous_status,
            "new_status": lg.new_status,
        }
        for lg in logs
    ]

    detail = _bluesheet_to_dict(bs)
    detail["approval_log"] = log_items
    return detail


# ═══════════════════════════════════════════════════════════
# CREATE (wizard submission)
# ═══════════════════════════════════════════════════════════

@router.post("")
def submit_kri_onboarding(
    payload: KriBluesheetCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_any_authenticated),
):
    """Create a new KRI + bluesheet and set status to PENDING_APPROVAL."""
    # Validate KRI code uniqueness
    if db.query(KriMaster).filter(KriMaster.kri_code == payload.kri_code).first():
        raise HTTPException(status_code=409, detail=f"KRI code '{payload.kri_code}' already exists")

    # Create KriMaster
    kri = KriMaster(
        kri_code=payload.kri_code,
        kri_name=payload.kri_name,
        description=payload.description,
        region_id=payload.region_id,
        category_id=payload.category_id,
        risk_level=payload.risk_level,
        frequency=payload.frequency,
        is_active=False,  # activated only after approval
        onboarded_dt=datetime.utcnow(),
        created_by=current_user["soe_id"],
        updated_by=current_user["soe_id"],
    )
    db.add(kri)
    db.flush()  # get kri_id

    # Create KriBluesheet
    bs = KriBluesheet(
        kri_id=kri.kri_id,
        legacy_kri_id=payload.legacy_kri_id,
        threshold=payload.threshold,
        circuit_breaker=payload.circuit_breaker,
        control_ids=payload.control_ids,
        dq_objectives=payload.dq_objectives,
        primary_senior_manager=payload.primary_senior_manager,
        metric_owner_name=payload.metric_owner_name,
        remediation_owner_name=payload.remediation_owner_name,
        bi_metrics_lead=payload.bi_metrics_lead,
        data_provider_name=payload.data_provider_name,
        sc_uk=payload.sc_uk,
        sc_finance=payload.sc_finance,
        sc_risk=payload.sc_risk,
        sc_liquidity=payload.sc_liquidity,
        sc_capital=payload.sc_capital,
        sc_risk_reports=payload.sc_risk_reports,
        sc_markets=payload.sc_markets,
        why_selected=payload.why_selected,
        threshold_rationale=payload.threshold_rationale,
        limitations=payload.limitations,
        kri_calculation=payload.kri_calculation,
        runbook_version=payload.runbook_version,
        runbook_review_date=payload.runbook_review_date,
        runbook_notes=payload.runbook_notes,
        approval_status="PENDING_APPROVAL",
        submitted_by=current_user["user_id"],
        submitted_dt=datetime.utcnow(),
        created_by=current_user["soe_id"],
        updated_by=current_user["soe_id"],
    )
    db.add(bs)
    db.flush()

    # Write initial approval log entry
    log = KriApprovalLog(
        kri_id=kri.kri_id,
        action="SUBMITTED",
        performed_by=current_user["user_id"],
        performed_dt=datetime.utcnow(),
        comments="KRI submitted for L3 review",
        previous_status="DRAFT",
        new_status="PENDING_APPROVAL",
    )
    db.add(log)
    db.commit()
    db.refresh(bs)

    return {"kri_id": kri.kri_id, "bluesheet_id": bs.bluesheet_id, "approval_status": bs.approval_status}


# ═══════════════════════════════════════════════════════════
# DRAFT SAVE / UPDATE
# ═══════════════════════════════════════════════════════════

def _bluesheet_fields(payload: KriBluesheetCreate, soe_id: str) -> dict:
    """Return the common fields used when creating/updating a bluesheet."""
    return dict(
        legacy_kri_id=payload.legacy_kri_id,
        threshold=payload.threshold,
        circuit_breaker=payload.circuit_breaker,
        control_ids=payload.control_ids,
        dq_objectives=payload.dq_objectives,
        primary_senior_manager=payload.primary_senior_manager,
        metric_owner_name=payload.metric_owner_name,
        remediation_owner_name=payload.remediation_owner_name,
        bi_metrics_lead=payload.bi_metrics_lead,
        data_provider_name=payload.data_provider_name,
        sc_uk=payload.sc_uk,
        sc_finance=payload.sc_finance,
        sc_risk=payload.sc_risk,
        sc_liquidity=payload.sc_liquidity,
        sc_capital=payload.sc_capital,
        sc_risk_reports=payload.sc_risk_reports,
        sc_markets=payload.sc_markets,
        why_selected=payload.why_selected,
        threshold_rationale=payload.threshold_rationale,
        limitations=payload.limitations,
        kri_calculation=payload.kri_calculation,
        runbook_version=payload.runbook_version,
        runbook_review_date=payload.runbook_review_date,
        runbook_notes=payload.runbook_notes,
        updated_by=soe_id,
    )


@router.post("/draft")
def save_draft(
    payload: KriBluesheetCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_any_authenticated),
):
    """Create a new KRI bluesheet draft without submitting for approval."""
    if db.query(KriMaster).filter(KriMaster.kri_code == payload.kri_code).first():
        raise HTTPException(status_code=409, detail=f"KRI code '{payload.kri_code}' already exists")

    kri = KriMaster(
        kri_code=payload.kri_code,
        kri_name=payload.kri_name,
        description=payload.description,
        region_id=payload.region_id,
        category_id=payload.category_id,
        risk_level=payload.risk_level,
        frequency=payload.frequency,
        is_active=False,
        onboarded_dt=datetime.utcnow(),
        created_by=current_user["soe_id"],
        updated_by=current_user["soe_id"],
    )
    db.add(kri)
    db.flush()

    bs = KriBluesheet(
        kri_id=kri.kri_id,
        approval_status="DRAFT",
        submitted_by=current_user["user_id"],
        created_by=current_user["soe_id"],
        **_bluesheet_fields(payload, current_user["soe_id"]),
    )
    db.add(bs)
    db.commit()
    db.refresh(bs)

    return {"kri_id": kri.kri_id, "bluesheet_id": bs.bluesheet_id, "approval_status": "DRAFT"}


@router.patch("/{kri_id}/draft")
def update_draft(
    kri_id: int,
    payload: KriBluesheetCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_any_authenticated),
):
    """Update an existing draft bluesheet (only while still in DRAFT status)."""
    bs = db.query(KriBluesheet).filter(KriBluesheet.kri_id == kri_id).first()
    if not bs:
        raise HTTPException(status_code=404, detail="KRI bluesheet not found")
    if bs.approval_status not in ("DRAFT", "REWORK"):
        raise HTTPException(status_code=409, detail="Only DRAFT or REWORK bluesheets can be updated")

    # Update KriMaster fields too
    kri = db.query(KriMaster).filter(KriMaster.kri_id == kri_id).first()
    if kri:
        kri.kri_name = payload.kri_name
        kri.description = payload.description
        kri.region_id = payload.region_id
        kri.category_id = payload.category_id
        kri.risk_level = payload.risk_level
        kri.frequency = payload.frequency
        kri.updated_by = current_user["soe_id"]

    for field, value in _bluesheet_fields(payload, current_user["soe_id"]).items():
        setattr(bs, field, value)

    db.commit()
    db.refresh(bs)

    return {"kri_id": kri_id, "bluesheet_id": bs.bluesheet_id, "approval_status": bs.approval_status}


# ═══════════════════════════════════════════════════════════
# RESUBMIT (REWORK → PENDING_APPROVAL)
# ═══════════════════════════════════════════════════════════

@router.post("/{kri_id}/resubmit")
def resubmit_kri(
    kri_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_any_authenticated),
):
    """Re-submit a REWORK or DRAFT bluesheet for L3 review.

    Updates all editable fields first (via the body-less version) then transitions
    the approval status to PENDING_APPROVAL and writes an audit log entry.
    """
    bs = db.query(KriBluesheet).filter(KriBluesheet.kri_id == kri_id).first()
    if not bs:
        raise HTTPException(status_code=404, detail="KRI bluesheet not found")
    if bs.approval_status not in ("DRAFT", "REWORK"):
        raise HTTPException(
            status_code=409,
            detail=f"KRI is in '{bs.approval_status}' state — only DRAFT or REWORK can be re-submitted",
        )

    previous = bs.approval_status
    bs.approval_status = "PENDING_APPROVAL"
    bs.submitted_by = current_user["user_id"]
    bs.submitted_dt = datetime.utcnow()
    bs.updated_by = current_user["soe_id"]

    log = KriApprovalLog(
        kri_id=kri_id,
        action="RESUBMITTED",
        performed_by=current_user["user_id"],
        performed_dt=datetime.utcnow(),
        comments=f"Re-submitted after {previous}",
        previous_status=previous,
        new_status="PENDING_APPROVAL",
    )
    db.add(log)
    db.commit()
    db.refresh(bs)

    return {"kri_id": kri_id, "bluesheet_id": bs.bluesheet_id, "approval_status": bs.approval_status}


# ═══════════════════════════════════════════════════════════
# RUNBOOK UPLOAD
# ═══════════════════════════════════════════════════════════

@router.post("/{kri_id}/runbook")
async def upload_runbook(
    kri_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_any_authenticated),
):
    """Upload runbook file; stores locally and records S3-style path."""
    bs = db.query(KriBluesheet).filter(KriBluesheet.kri_id == kri_id).first()
    kri = db.query(KriMaster).filter(KriMaster.kri_id == kri_id).first()
    if not kri:
        raise HTTPException(status_code=404, detail="KRI not found")

    # Validate extension
    allowed_ext = {".pdf", ".docx", ".xlsx"}
    _, ext = os.path.splitext(file.filename or "")
    if ext.lower() not in allowed_ext:
        raise HTTPException(status_code=400, detail=f"Unsupported file type '{ext}'. Allowed: PDF, DOCX, XLSX")

    # Save file locally (simulates S3 upload)
    safe_code = kri.kri_code or f"kri-{kri_id}"
    save_dir = _ensure_runbook_dir(safe_code)
    dest_filename = f"{safe_code}_Runbook{ext}"
    dest_path = os.path.join(save_dir, dest_filename)

    content = await file.read()
    with open(dest_path, "wb") as f:
        f.write(content)

    s3_path = _s3_path(safe_code, dest_filename)

    # Update or create bluesheet record
    if bs:
        bs.runbook_s3_path = s3_path
        bs.runbook_filename = dest_filename
        bs.updated_by = current_user["soe_id"]
    else:
        # Bluesheet may not exist yet for draft KRIs
        bs = KriBluesheet(
            kri_id=kri_id,
            runbook_s3_path=s3_path,
            runbook_filename=dest_filename,
            approval_status="DRAFT",
            created_by=current_user["soe_id"],
            updated_by=current_user["soe_id"],
        )
        db.add(bs)

    db.commit()

    return {
        "kri_id": kri_id,
        "s3_path": s3_path,
        "filename": dest_filename,
        "size_bytes": len(content),
    }


# ═══════════════════════════════════════════════════════════
# APPROVE / REJECT / REWORK  (L3 only)
# ═══════════════════════════════════════════════════════════

@router.post("/{kri_id}/approve")
def approve_kri(
    kri_id: int,
    payload: KriApprovalActionRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_l3),
):
    """L3 Admin performs an approval action on a pending KRI."""
    bs = db.query(KriBluesheet).filter(KriBluesheet.kri_id == kri_id).first()
    if not bs:
        raise HTTPException(status_code=404, detail="KRI bluesheet not found")

    if bs.approval_status not in ("PENDING_APPROVAL", "REWORK"):
        raise HTTPException(
            status_code=409,
            detail=f"KRI is not in a reviewable state (current: {bs.approval_status})"
        )

    if payload.action in ("REJECTED", "REWORK") and not payload.comments:
        raise HTTPException(status_code=422, detail="Comments are required when rejecting or requesting rework")

    status_map = {
        "APPROVED": "APPROVED",
        "REJECTED": "REJECTED",
        "REWORK": "REWORK",
    }
    previous = bs.approval_status
    new_status = status_map[payload.action]

    bs.approval_status = new_status
    bs.updated_by = current_user["soe_id"]

    # Activate KRI when approved
    if new_status == "APPROVED":
        kri = db.query(KriMaster).filter(KriMaster.kri_id == kri_id).first()
        if kri:
            kri.is_active = True
            kri.updated_by = current_user["soe_id"]

    # Log the action
    log = KriApprovalLog(
        kri_id=kri_id,
        action=payload.action,
        performed_by=current_user["user_id"],
        performed_dt=datetime.utcnow(),
        comments=payload.comments,
        previous_status=previous,
        new_status=new_status,
    )
    db.add(log)
    db.commit()

    # ── Trigger outbound email as background task (do NOT block response) ──
    # Map approval action → email subject action word per spec
    _action_map = {
        "APPROVED": "Final Approved",
        "REJECTED": "Rejected",
        "REWORK":   "Rework Required",
    }
    email_action = _action_map.get(payload.action, payload.action)

    # Collect L3 approver email as recipient (self-notification + submitter if available)
    recipients = [current_user["email"]] if current_user.get("email") else []
    bs = db.query(KriBluesheet).filter(KriBluesheet.kri_id == kri_id).first()
    if bs and bs.submitter and bs.submitter.email and bs.submitter.email not in recipients:
        recipients.append(bs.submitter.email)

    if recipients:
        now = datetime.utcnow()
        trigger_fn = _get_email_trigger()
        # NOTE: background task opens its own DB session via SessionLocal
        from app.database import SessionLocal as _SessionLocal

        def _email_bg():
            bg_db = _SessionLocal()
            try:
                trigger_fn(kri_id, now.year, now.month, email_action,
                           recipients, current_user["user_id"], bg_db)
            finally:
                bg_db.close()

        background_tasks.add_task(_email_bg)

    return {
        "kri_id": kri_id,
        "action": payload.action,
        "new_status": new_status,
        "performed_by": current_user["soe_id"],
    }
