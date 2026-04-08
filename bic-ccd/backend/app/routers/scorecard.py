"""Scorecard Maker/Checker workflow endpoints.

Six endpoints:
  GET  /api/scorecard                      — list scorecards (filter by period/region)
  GET  /api/scorecard/{scorecard_id}       — get scorecard detail with KRI summary
  POST /api/scorecard                      — maker creates a scorecard draft for a period
  POST /api/scorecard/{scorecard_id}/submit   — maker submits for checker review
  POST /api/scorecard/{scorecard_id}/approve  — checker approves
  POST /api/scorecard/{scorecard_id}/reject   — checker rejects (returns to maker)

A scorecard is a period-level aggregate of MonthlyControlStatus rows.
It is represented as a MakerCheckerSubmission with submission_notes
containing the serialised scorecard payload, identified by
submission_notes starting with "SCORECARD:".
"""
import json
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Body
from sqlalchemy.orm import Session

from app.database import get_db
from app.middleware import (
    get_current_user,
    require_scorecard,
    require_approvals,
    RoleChecker,
)
from app.models import (
    MakerCheckerSubmission, ApprovalAuditTrail,
    MonthlyControlStatus, KriMaster, ControlDimensionMaster,
    AppUser, UserRoleMapping,
)

scorecard_router = APIRouter(prefix="/api/scorecard", tags=["Scorecard"])

# Roles that may act as Scorecard Checker
_CHECKER_ROLES = {"L2_APPROVER", "L3_ADMIN", "SYSTEM_ADMIN", "SCORECARD_CHECKER"}
_MAKER_ROLES   = {"L1_APPROVER", "DATA_PROVIDER", "METRIC_OWNER",
                  "SCORECARD_MAKER", "MANAGEMENT", "SYSTEM_ADMIN"}

require_scorecard_maker   = RoleChecker(list(_MAKER_ROLES))
require_scorecard_checker = RoleChecker(list(_CHECKER_ROLES))


# ─── helpers ─────────────────────────────────────────────────────────────────

def _is_scorecard(sub: MakerCheckerSubmission) -> bool:
    return bool(sub.submission_notes and sub.submission_notes.startswith("SCORECARD:"))


def _build_summary(db: Session, year: int, month: int, region_id: Optional[int]) -> dict:
    """Aggregate MonthlyControlStatus into a scorecard payload."""
    q = (
        db.query(MonthlyControlStatus)
        .filter_by(period_year=year, period_month=month)
    )
    if region_id:
        q = q.join(KriMaster, MonthlyControlStatus.kri_id == KriMaster.kri_id).filter(
            KriMaster.region_id == region_id
        )
    rows = q.all()

    total = len(rows)
    by_status: dict = {}
    by_rag: dict = {}
    sla_met = 0

    for r in rows:
        by_status[r.status] = by_status.get(r.status, 0) + 1
        rag = r.rag_status or "GREY"
        by_rag[rag] = by_rag.get(rag, 0) + 1
        if r.sla_met:
            sla_met += 1

    sla_compliance_pct = round(sla_met / total * 100, 1) if total else 0

    return {
        "year": year,
        "month": month,
        "region_id": region_id,
        "total_controls": total,
        "by_status": by_status,
        "by_rag": by_rag,
        "sla_compliance_pct": sla_compliance_pct,
    }


def _scorecard_response(sub: MakerCheckerSubmission, db: Session) -> dict:
    payload: dict = {}
    if sub.submission_notes and sub.submission_notes.startswith("SCORECARD:"):
        try:
            payload = json.loads(sub.submission_notes[len("SCORECARD:"):])
        except Exception:
            pass

    submitter = db.get(AppUser, sub.submitted_by)
    return {
        "scorecard_id": sub.submission_id,
        "year":  payload.get("year"),
        "month": payload.get("month"),
        "region_id": payload.get("region_id"),
        "final_status": sub.final_status,
        "submitted_by": submitter.full_name if submitter else f"User #{sub.submitted_by}",
        "submitted_dt": sub.submitted_dt,
        "l1_action": sub.l1_action,
        "l1_action_dt": sub.l1_action_dt,
        "l2_action": sub.l2_action,
        "l2_action_dt": sub.l2_action_dt,
        "summary": {k: v for k, v in payload.items() if k not in ("year", "month", "region_id")},
    }


# ─── GET /api/scorecard ───────────────────────────────────────────────────────

@scorecard_router.get("")
def list_scorecards(
    year: Optional[int] = None,
    month: Optional[int] = None,
    region_id: Optional[int] = None,
    db: Session = Depends(get_db),
    _user: dict = Depends(require_scorecard),
):
    """List scorecard submissions, optionally filtered by period / region."""
    q = db.query(MakerCheckerSubmission).filter(
        MakerCheckerSubmission.submission_notes.like("SCORECARD:%")
    )
    subs = q.order_by(MakerCheckerSubmission.submitted_dt.desc()).all()

    results = []
    for sub in subs:
        r = _scorecard_response(sub, db)
        if year and r.get("year") != year:
            continue
        if month and r.get("month") != month:
            continue
        if region_id and r.get("region_id") != region_id:
            continue
        results.append(r)

    return {"items": results, "total": len(results)}


# ─── GET /api/scorecard/{scorecard_id} ───────────────────────────────────────

@scorecard_router.get("/{scorecard_id}")
def get_scorecard(
    scorecard_id: int,
    db: Session = Depends(get_db),
    _user: dict = Depends(require_scorecard),
):
    """Get scorecard detail including full KRI row breakdown."""
    sub = db.get(MakerCheckerSubmission, scorecard_id)
    if not sub or not _is_scorecard(sub):
        raise HTTPException(404, "Scorecard not found")

    resp = _scorecard_response(sub, db)

    # Attach live KRI breakdown for the period
    year  = resp.get("year")
    month = resp.get("month")
    region_id = resp.get("region_id")

    if year and month:
        q = (
            db.query(MonthlyControlStatus)
            .filter_by(period_year=year, period_month=month)
        )
        if region_id:
            q = q.join(KriMaster, MonthlyControlStatus.kri_id == KriMaster.kri_id).filter(
                KriMaster.region_id == region_id
            )
        rows = q.all()
        resp["kri_rows"] = [
            {
                "status_id": r.status_id,
                "kri_id": r.kri_id,
                "kri_name": r.kri.kri_name if r.kri else None,
                "dimension_id": r.dimension_id,
                "dimension_name": r.dimension.dimension_name if hasattr(r, "dimension") else None,
                "status": r.status,
                "rag_status": r.rag_status,
                "sla_met": r.sla_met,
                "sla_due_dt": r.sla_due_dt,
            }
            for r in rows
        ]

    # Audit trail
    audits = (
        db.query(ApprovalAuditTrail)
        .filter_by(status_id=sub.status_id)
        .order_by(ApprovalAuditTrail.performed_dt.asc())
        .all()
    )
    resp["audit_trail"] = [
        {
            "action": a.action,
            "performed_by": a.performer.full_name if a.performer else f"User #{a.performed_by}",
            "performed_dt": a.performed_dt,
            "comments": a.comments,
        }
        for a in audits
    ]

    return resp


# ─── POST /api/scorecard ──────────────────────────────────────────────────────

@scorecard_router.post("")
def create_scorecard(
    year: int = Body(...),
    month: int = Body(...),
    region_id: Optional[int] = Body(default=None),
    notes: Optional[str] = Body(default=None),
    db: Session = Depends(get_db),
    user: dict = Depends(require_scorecard_maker),
):
    """Maker creates a scorecard DRAFT for the given period."""
    # Prevent duplicate drafts
    existing = db.query(MakerCheckerSubmission).filter(
        MakerCheckerSubmission.submission_notes.like(f"SCORECARD:%\"year\": {year}%\"month\": {month}%"),
        MakerCheckerSubmission.final_status.notin_(["REJECTED", "APPROVED"]),
    ).first()
    if existing:
        raise HTTPException(409, f"A scorecard for {year}-{month:02d} is already in progress (id={existing.submission_id})")

    summary = _build_summary(db, year, month, region_id)
    payload = json.dumps({"year": year, "month": month, "region_id": region_id,
                          "notes": notes, **{k: v for k, v in summary.items()
                                             if k not in ("year", "month", "region_id")}})

    # MakerCheckerSubmission doesn't have a status_id requirement in the scorecard context;
    # we set status_id = 0 as a sentinel (no linked control-status row).
    sub = MakerCheckerSubmission(
        status_id=0,
        submitted_by=user["user_id"],
        submission_notes=f"SCORECARD:{payload}",
        final_status="DRAFT",
        created_by=user["soe_id"],
        updated_by=user["soe_id"],
    )
    db.add(sub)
    db.commit()
    db.refresh(sub)

    return {"scorecard_id": sub.submission_id, "final_status": sub.final_status,
            "year": year, "month": month, "summary": summary}


# ─── POST /api/scorecard/{scorecard_id}/submit ───────────────────────────────

@scorecard_router.post("/{scorecard_id}/submit")
def submit_scorecard(
    scorecard_id: int,
    notes: Optional[str] = Body(default=None),
    db: Session = Depends(get_db),
    user: dict = Depends(require_scorecard_maker),
):
    """Maker submits the scorecard draft for checker review."""
    sub = db.get(MakerCheckerSubmission, scorecard_id)
    if not sub or not _is_scorecard(sub):
        raise HTTPException(404, "Scorecard not found")
    if sub.final_status not in ("DRAFT", "REWORK"):
        raise HTTPException(400, f"Cannot submit scorecard in status '{sub.final_status}'")

    # Assign first available checker
    checker = (
        db.query(AppUser)
        .join(UserRoleMapping, UserRoleMapping.user_id == AppUser.user_id)
        .filter(
            UserRoleMapping.role_code.in_(list(_CHECKER_ROLES)),
            UserRoleMapping.is_active == True,
            AppUser.is_active == True,
        )
        .first()
    )
    sub.l1_approver_id = checker.user_id if checker else None
    sub.final_status = "L1_PENDING"
    sub.updated_by = user["soe_id"]

    audit = ApprovalAuditTrail(
        status_id=sub.status_id,
        action="SUBMITTED",
        performed_by=user["user_id"],
        performed_dt=datetime.utcnow(),
        comments=notes or "Submitted for review",
        previous_status="DRAFT",
        new_status="L1_PENDING",
        created_by=user["soe_id"],
        updated_by=user["soe_id"],
    )
    db.add(audit)
    db.commit()

    # 6.7 scorecard notification to management
    try:
        from app.services.email import notify_scorecard
        payload = json.loads(sub.submission_notes[len("SCORECARD:"):])
        period_str = f"{payload.get('year')}-{payload.get('month', 0):02d}"
        mgmt_users = (
            db.query(AppUser)
            .join(UserRoleMapping, UserRoleMapping.user_id == AppUser.user_id)
            .filter(
                UserRoleMapping.role_code.in_(["MANAGEMENT", "SYSTEM_ADMIN"]),
                UserRoleMapping.is_active == True,
                AppUser.is_active == True,
            )
            .all()
        )
        for mgmt in mgmt_users:
            notify_scorecard(db, mgmt.user_id, mgmt.email, period_str, "submitted", user["full_name"], commit=False)
        db.commit()
    except Exception as exc:
        import logging
        logging.getLogger("bic_ccd.scorecard").warning("Scorecard notification failed: %s", exc)

    return {"scorecard_id": scorecard_id, "final_status": sub.final_status}


# ─── POST /api/scorecard/{scorecard_id}/approve ──────────────────────────────

@scorecard_router.post("/{scorecard_id}/approve")
def approve_scorecard(
    scorecard_id: int,
    comments: Optional[str] = Body(default=None),
    db: Session = Depends(get_db),
    user: dict = Depends(require_scorecard_checker),
):
    """Checker approves the scorecard."""
    sub = db.get(MakerCheckerSubmission, scorecard_id)
    if not sub or not _is_scorecard(sub):
        raise HTTPException(404, "Scorecard not found")
    if sub.final_status not in ("L1_PENDING", "L2_PENDING"):
        raise HTTPException(400, f"Cannot approve scorecard in status '{sub.final_status}'")

    sub.l1_action = "APPROVED"
    sub.l1_action_dt = datetime.utcnow()
    sub.final_status = "APPROVED"
    sub.updated_by = user["soe_id"]

    audit = ApprovalAuditTrail(
        status_id=sub.status_id,
        action="APPROVED",
        performed_by=user["user_id"],
        performed_dt=datetime.utcnow(),
        comments=comments or "Approved",
        previous_status="L1_PENDING",
        new_status="APPROVED",
        created_by=user["soe_id"],
        updated_by=user["soe_id"],
    )
    db.add(audit)
    db.commit()

    # 6.7 approval notification
    try:
        from app.services.email import notify_scorecard
        payload = json.loads(sub.submission_notes[len("SCORECARD:"):])
        period_str = f"{payload.get('year')}-{payload.get('month', 0):02d}"
        mgmt_users = (
            db.query(AppUser)
            .join(UserRoleMapping, UserRoleMapping.user_id == AppUser.user_id)
            .filter(
                UserRoleMapping.role_code.in_(["MANAGEMENT", "SYSTEM_ADMIN"]),
                UserRoleMapping.is_active == True,
            )
            .all()
        )
        for mgmt in mgmt_users:
            notify_scorecard(db, mgmt.user_id, mgmt.email, period_str, "approved", user["full_name"], commit=False)
        db.commit()
    except Exception as exc:
        import logging
        logging.getLogger("bic_ccd.scorecard").warning("Scorecard notification failed: %s", exc)

    return {"scorecard_id": scorecard_id, "final_status": "APPROVED"}


# ─── POST /api/scorecard/{scorecard_id}/reject ───────────────────────────────

@scorecard_router.post("/{scorecard_id}/reject")
def reject_scorecard(
    scorecard_id: int,
    comments: str = Body(...),
    db: Session = Depends(get_db),
    user: dict = Depends(require_scorecard_checker),
):
    """Checker rejects the scorecard — returns it to maker for rework."""
    sub = db.get(MakerCheckerSubmission, scorecard_id)
    if not sub or not _is_scorecard(sub):
        raise HTTPException(404, "Scorecard not found")
    if sub.final_status not in ("L1_PENDING", "L2_PENDING"):
        raise HTTPException(400, f"Cannot reject scorecard in status '{sub.final_status}'")

    prev_status = sub.final_status
    sub.l1_action = "REJECTED"
    sub.l1_action_dt = datetime.utcnow()
    sub.final_status = "REWORK"
    sub.updated_by = user["soe_id"]

    audit = ApprovalAuditTrail(
        status_id=sub.status_id,
        action="REJECTED",
        performed_by=user["user_id"],
        performed_dt=datetime.utcnow(),
        comments=comments,
        previous_status=prev_status,
        new_status="REWORK",
        created_by=user["soe_id"],
        updated_by=user["soe_id"],
    )
    db.add(audit)
    db.commit()

    return {"scorecard_id": scorecard_id, "final_status": "REWORK", "comments": comments}
