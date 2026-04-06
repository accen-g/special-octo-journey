"""FastAPI routers for BIC-CCD."""
from datetime import datetime, date
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query, Form, Body
from sqlalchemy.orm import Session
from sqlalchemy import desc
import os, uuid

from app.database import get_db
from app.models import ApprovalAuditTrail, AppUser
from app.utils import compute_pending_with
from app.middleware import (
    get_current_user, create_access_token,
    # Page-level checkers (derived from PAGE_ACCESS — single source of truth)
    require_dashboard, require_data_control, require_approvals,
    require_evidence, require_variance, require_scorecard,
    require_escalation_metrics, require_system_admin,
    # Legacy / operation-level checkers
    require_admin, require_management, require_approver,
    require_l1, require_l2, require_l3,
    require_data_provider, require_any_authenticated,
    require_page_access,
)
from app.services import (
    AuthService, DashboardService, KriService,
    MakerCheckerService, VarianceService, EvidenceService,
)
from app.repositories import (
    RegionRepository, CategoryRepository, DimensionRepository,
    UserRepository, KriRepository, KriConfigRepository,
    MonthlyStatusRepository, ApprovalAuditRepository,
    EvidenceRepository, MakerCheckerRepository,
    VarianceRepository, MetricRepository, EscalationRepository,
    NotificationRepository, CommentRepository, DataSourceRepository,
    AssignmentRepository, SavedViewRepository, ApproverRuleRepository,
)
from app.schemas import (
    LoginRequest, TokenResponse, UserCreate, UserUpdate, UserResponse,
    RegionCreate, RegionResponse, CategoryCreate, CategoryResponse,
    DimensionResponse, KriCreate, KriUpdate, KriResponse,
    KriConfigCreate, KriConfigResponse, KriOnboardRequest,
    MonthlyStatusResponse, ApprovalActionRequest, ApprovalAuditResponse,
    EvidenceResponse, MakerCheckerSubmitRequest, MakerCheckerActionRequest,
    MakerCheckerResponse, VarianceSubmitRequest, VarianceResponse,
    MetricValueResponse, DashboardSummary, TrendDataPoint,
    DimensionBreakdown, EscalationConfigCreate, EscalationConfigUpdate, EscalationConfigResponse,
    NotificationResponse, CommentCreate, CommentResponse,
    RoleAssignment, DataSourceCreate, DataSourceResponse, PaginatedResponse,
)


# ═══════════════════════════════════════════════════════════
# AUTH
# ═══════════════════════════════════════════════════════════
auth_router = APIRouter(prefix="/api/auth", tags=["Authentication"])

@auth_router.post("/login")
def login(req: LoginRequest, db: Session = Depends(get_db)):
    svc = AuthService(db)
    user_data = svc.authenticate(req.soe_id, req.password)
    token = create_access_token({"soe_id": user_data["soe_id"], "user_id": user_data["user_id"]})
    return {"access_token": token, "token_type": "bearer", "user": user_data}

@auth_router.get("/me")
def get_me(current_user: dict = Depends(get_current_user)):
    return current_user


# ═══════════════════════════════════════════════════════════
# LOOKUPS
# ═══════════════════════════════════════════════════════════
lookup_router = APIRouter(prefix="/api/lookups", tags=["Lookups"])

@lookup_router.get("/regions")
def list_regions(db: Session = Depends(get_db)):
    return [{"region_id": r.region_id, "region_code": r.region_code, "region_name": r.region_name}
            for r in RegionRepository(db).get_all()]

@lookup_router.get("/categories")
def list_categories(db: Session = Depends(get_db)):
    return [{"category_id": c.category_id, "category_code": c.category_code, "category_name": c.category_name}
            for c in CategoryRepository(db).get_all()]

@lookup_router.get("/dimensions")
def list_dimensions(db: Session = Depends(get_db)):
    return [{"dimension_id": d.dimension_id, "dimension_code": d.dimension_code,
             "dimension_name": d.dimension_name, "display_order": d.display_order}
            for d in DimensionRepository(db).get_all()]


# ═══════════════════════════════════════════════════════════
# DASHBOARD
# ═══════════════════════════════════════════════════════════
dashboard_router = APIRouter(prefix="/api/dashboard", tags=["Dashboard"])

@dashboard_router.get("/summary")
def dashboard_summary(
    year: int = Query(default=None),
    month: int = Query(default=None),
    region_id: Optional[int] = None,
    db: Session = Depends(get_db),
    _user: dict = Depends(require_dashboard),
):
    now = datetime.utcnow()
    y = year or now.year
    m = month or now.month
    return DashboardService(db).get_summary(y, m, region_id)

@dashboard_router.get("/trend")
def dashboard_trend(
    months: int = 6,
    region_id: Optional[int] = None,
    db: Session = Depends(get_db),
    _user: dict = Depends(require_dashboard),
):
    return DashboardService(db).get_trend(months, region_id)

@dashboard_router.get("/dimension-breakdown")
def dimension_breakdown(
    year: int = Query(default=None),
    month: int = Query(default=None),
    region_id: Optional[int] = None,
    db: Session = Depends(get_db),
    _user: dict = Depends(require_dashboard),
):
    now = datetime.utcnow()
    return DashboardService(db).get_dimension_breakdown(year or now.year, month or now.month, region_id)

@dashboard_router.get("/sla-distribution")
def sla_distribution(
    year: int = Query(default=None),
    month: int = Query(default=None),
    region_id: Optional[int] = None,
    db: Session = Depends(get_db),
    _user: dict = Depends(require_dashboard),
):
    now = datetime.utcnow()
    return DashboardService(db).get_sla_distribution(year or now.year, month or now.month, region_id)

@dashboard_router.get("/evidence-completeness")
def evidence_completeness(
    year: int = Query(default=None),
    month: int = Query(default=None),
    db: Session = Depends(get_db),
    _user: dict = Depends(require_dashboard),
):
    now = datetime.utcnow()
    return DashboardService(db).get_evidence_completeness(year or now.year, month or now.month)


# ═══════════════════════════════════════════════════════════
# KRI
# ═══════════════════════════════════════════════════════════
kri_router = APIRouter(prefix="/api/kris", tags=["KRI Management"])

@kri_router.get("")
def list_kris(
    region_id: Optional[int] = None,
    category_id: Optional[int] = None,
    page: int = 1,
    page_size: int = 50,
    db: Session = Depends(get_db),
    _user: dict = Depends(require_data_control),
):
    svc = KriService(db)
    items, total = svc.list_kris(region_id, category_id, page, page_size)
    return {"items": items, "total": total, "page": page, "page_size": page_size,
            "total_pages": (total + page_size - 1) // page_size}

@kri_router.get("/{kri_id}")
def get_kri(kri_id: int, db: Session = Depends(get_db), _user: dict = Depends(require_data_control)):
    kri = KriRepository(db).get_by_id(kri_id)
    if not kri:
        raise HTTPException(404, "KRI not found")
    return {
        "kri_id": kri.kri_id, "kri_code": kri.kri_code, "kri_name": kri.kri_name,
        "description": kri.description, "category_id": kri.category_id,
        "category_name": kri.category.category_name if kri.category else None,
        "region_id": kri.region_id,
        "region_name": kri.region.region_name if kri.region else None,
        "risk_level": kri.risk_level, "framework": kri.framework,
        "is_active": kri.is_active, "onboarded_dt": kri.onboarded_dt,
        "configurations": [
            {"config_id": c.config_id, "dimension_id": c.dimension_id,
             "sla_days": c.sla_days, "variance_threshold": c.variance_threshold}
            for c in kri.configurations
        ]
    }

@kri_router.post("")
def create_kri(data: KriCreate, db: Session = Depends(get_db), user: dict = Depends(require_system_admin)):
    return KriService(db).create_kri(data, user["soe_id"])

@kri_router.put("/{kri_id}")
def update_kri(kri_id: int, data: KriUpdate, db: Session = Depends(get_db), user: dict = Depends(require_system_admin)):
    return KriService(db).update_kri(kri_id, data, user["soe_id"])

@kri_router.post("/onboard")
def onboard_kri(req: KriOnboardRequest, db: Session = Depends(get_db), user: dict = Depends(require_system_admin)):
    return KriService(db).onboard_kri(req, user["soe_id"])


# ═══════════════════════════════════════════════════════════
# KRI CONFIGURATION
# ═══════════════════════════════════════════════════════════
config_router = APIRouter(prefix="/api/kri-config", tags=["KRI Configuration"])

@config_router.get("/{kri_id}")
def get_kri_configs(kri_id: int, db: Session = Depends(get_db), _user: dict = Depends(require_data_control)):
    configs = KriConfigRepository(db).get_for_kri(kri_id)
    return [{"config_id": c.config_id, "kri_id": c.kri_id, "dimension_id": c.dimension_id,
             "sla_days": c.sla_days, "variance_threshold": c.variance_threshold,
             "requires_evidence": c.requires_evidence, "requires_approval": c.requires_approval,
             "freeze_day": c.freeze_day}
            for c in configs]

@config_router.post("")
def create_kri_config(data: KriConfigCreate, db: Session = Depends(get_db), user: dict = Depends(require_system_admin)):
    return KriConfigRepository(db).create({**data.model_dump(), "created_by": user["soe_id"], "updated_by": user["soe_id"]})


# ═══════════════════════════════════════════════════════════
# MONTHLY CONTROL STATUS (Data Control Workbench)
# ═══════════════════════════════════════════════════════════
control_router = APIRouter(prefix="/api/controls", tags=["Data Control"])

@control_router.get("")
def list_controls(
    year: int = Query(default=None),
    month: int = Query(default=None),
    region_id: Optional[int] = None,
    dimension_id: Optional[int] = None,
    status: Optional[str] = None,
    page: int = 1,
    page_size: int = 100,
    db: Session = Depends(get_db),
    _user: dict = Depends(require_data_control),
):
    from app.utils import to_management_status
    now = datetime.utcnow()
    repo = MonthlyStatusRepository(db)
    items, total = repo.get_for_period(
        year or now.year, month or now.month, region_id, dimension_id, status, page, page_size
    )
    # MANAGEMENT role sees simplified PASS / FAIL / IN_PROGRESS statuses
    is_management = any(r.get("role_code") == "MANAGEMENT" for r in _user.get("roles", []))
    results = []
    for s in items:
        kri = s.kri
        dim = s.dimension
        display_status = to_management_status(s.status) if is_management else s.status
        results.append({
            "status_id": s.status_id, "kri_id": s.kri_id,
            "kri_code": kri.kri_code if kri else None,
            "kri_name": kri.kri_name if kri else None,
            "dimension_id": s.dimension_id,
            "dimension_name": dim.dimension_name if dim else None,
            "period_year": s.period_year, "period_month": s.period_month,
            "status": display_status, "rag_status": s.rag_status,
            "sla_due_dt": s.sla_due_dt, "sla_met": s.sla_met,
            "approval_level": s.approval_level,
            "region_name": kri.region.region_name if kri and kri.region else None,
            "category_name": kri.category.category_name if kri and kri.category else None,
        })
    return {"items": results, "total": total, "page": page, "page_size": page_size}

@control_router.get("/{status_id}")
def get_control(status_id: int, db: Session = Depends(get_db), _user: dict = Depends(require_data_control)):
    obj = MonthlyStatusRepository(db).get_by_id(status_id)
    if not obj:
        raise HTTPException(404, "Control status not found")
    return {
        "status_id": obj.status_id, "kri_id": obj.kri_id,
        "dimension_id": obj.dimension_id, "status": obj.status,
        "rag_status": obj.rag_status, "approval_level": obj.approval_level,
        "sla_due_dt": obj.sla_due_dt, "sla_met": obj.sla_met,
    }

@control_router.get("/{status_id}/audit-trail")
def control_audit_trail(status_id: int, db: Session = Depends(get_db), _user: dict = Depends(require_data_control)):
    audits = ApprovalAuditRepository(db).get_for_status(status_id)
    return [{"audit_id": a.audit_id, "action": a.action, "performed_by": a.performed_by,
             "performed_dt": a.performed_dt, "comments": a.comments,
             "previous_status": a.previous_status, "new_status": a.new_status,
             "performer_name": a.performer.full_name if a.performer else f"User #{a.performed_by}"}
            for a in audits]


# ═══════════════════════════════════════════════════════════
# MAKER CHECKER
# ═══════════════════════════════════════════════════════════
mc_router = APIRouter(prefix="/api/maker-checker", tags=["Maker Checker"])

@mc_router.post("/submit")
def submit_for_approval(req: MakerCheckerSubmitRequest, db: Session = Depends(get_db),
                        user: dict = Depends(require_data_control)):
    svc = MakerCheckerService(db)
    sub = svc.submit(req, user["user_id"])
    return {"submission_id": sub.submission_id, "final_status": sub.final_status}

@mc_router.get("/pending")
def pending_approvals(
    level: str = "L1",
    page: int = 1,
    page_size: int = 50,
    db: Session = Depends(get_db),
    user: dict = Depends(require_approvals),
):
    repo = MakerCheckerRepository(db)
    # L3 Admin and SYSTEM_ADMIN see ALL pending items across all levels
    admin_roles = {"L3_ADMIN", "SYSTEM_ADMIN"}
    is_admin = any(r.get("role_code") in admin_roles for r in user.get("roles", []))
    if is_admin:
        items, total = repo.get_all_pending(level, page, page_size)
    else:
        items, total = repo.get_pending_for_approver(user["user_id"], level, page, page_size)

    # Batch-resolve approver names to avoid N+1 queries
    all_approver_ids = {
        aid for s in items
        for aid in [s.l1_approver_id, s.l2_approver_id, s.l3_approver_id] if aid
    }
    approver_map: dict = {}
    if all_approver_ids:
        users_q = db.query(AppUser).filter(AppUser.user_id.in_(all_approver_ids)).all()
        approver_map = {u.user_id: u.full_name for u in users_q}

    def _enrich(s):
        cs = s.control_status
        kri = cs.kri if cs else None
        return {
            "submission_id": s.submission_id,
            "status_id": s.status_id,
            "kri_id": cs.kri_id if cs else None,
            "final_status": s.final_status,
            "submitted_dt": s.submitted_dt,
            "submitted_by": s.submitted_by,
            "submitted_by_name": s.submitter.full_name if s.submitter else f"User #{s.submitted_by}",
            "kri_name": kri.kri_name if kri else None,
            "kri_code": kri.kri_code if kri else None,
            "region_name": kri.region.region_name if kri and kri.region else None,
            "period_year": cs.period_year if cs else None,
            "period_month": cs.period_month if cs else None,
            "sla_due_dt": cs.sla_due_dt if cs else None,
            "sla_met": cs.sla_met if cs else None,
            "pending_with": compute_pending_with(s),
            "l1_approver_id": s.l1_approver_id,
            "l1_approver_name": approver_map.get(s.l1_approver_id) if s.l1_approver_id else None,
            "l1_action": s.l1_action,
            "l2_approver_id": s.l2_approver_id,
            "l2_approver_name": approver_map.get(s.l2_approver_id) if s.l2_approver_id else None,
            "l2_action": s.l2_action,
            "l3_approver_id": s.l3_approver_id,
            "l3_approver_name": approver_map.get(s.l3_approver_id) if s.l3_approver_id else None,
            "l3_action": s.l3_action,
        }
    return {"items": [_enrich(s) for s in items], "total": total}

@mc_router.get("/queue-summary")
def queue_summary(db: Session = Depends(get_db), _user: dict = Depends(require_approvals)):
    """L3 Admin view: item counts per approval level."""
    return MakerCheckerRepository(db).get_queue_summary()

@mc_router.get("/all-pending")
def all_pending(
    level: str = Query(default=None),
    page: int = 1, page_size: int = 50,
    db: Session = Depends(get_db),
    _user: dict = Depends(require_approvals),
):
    """L3 Admin: see all pending items across all levels."""
    items, total = MakerCheckerRepository(db).get_all_pending(level, page, page_size)
    all_approver_ids = {
        aid for s in items
        for aid in [s.l1_approver_id, s.l2_approver_id, s.l3_approver_id] if aid
    }
    approver_map: dict = {}
    if all_approver_ids:
        users_q = db.query(AppUser).filter(AppUser.user_id.in_(all_approver_ids)).all()
        approver_map = {u.user_id: u.full_name for u in users_q}

    def _enrich_sub(s):
        cs = s.control_status
        kri = cs.kri if cs else None
        return {
            "submission_id": s.submission_id,
            "status_id": s.status_id,
            "kri_id": cs.kri_id if cs else None,
            "final_status": s.final_status,
            "submitted_dt": s.submitted_dt,
            "submitted_by": s.submitted_by,
            "submitted_by_name": s.submitter.full_name if s.submitter else f"User #{s.submitted_by}",
            "kri_name": kri.kri_name if kri else None,
            "kri_code": kri.kri_code if kri else None,
            "region_name": kri.region.region_name if kri and kri.region else None,
            "period_year": cs.period_year if cs else None,
            "period_month": cs.period_month if cs else None,
            "sla_due_dt": cs.sla_due_dt if cs else None,
            "sla_met": cs.sla_met if cs else None,
            "pending_with": compute_pending_with(s),
            "l1_approver_id": s.l1_approver_id,
            "l1_approver_name": approver_map.get(s.l1_approver_id) if s.l1_approver_id else None,
            "l1_action": s.l1_action,
            "l2_approver_id": s.l2_approver_id,
            "l2_approver_name": approver_map.get(s.l2_approver_id) if s.l2_approver_id else None,
            "l2_action": s.l2_action,
            "l3_approver_id": s.l3_approver_id,
            "l3_approver_name": approver_map.get(s.l3_approver_id) if s.l3_approver_id else None,
            "l3_action": s.l3_action,
        }
    return {"items": [_enrich_sub(s) for s in items], "total": total}

@mc_router.get("/history")
def approval_history(
    year: int = Query(default=None),
    month: int = Query(default=None),
    page: int = 1,
    page_size: int = 50,
    db: Session = Depends(get_db),
    user: dict = Depends(require_approvals),
):
    """Return completed/rejected/rework submissions for the current user (or all for admins)."""
    repo = MakerCheckerRepository(db)
    admin_roles = {"L3_ADMIN", "SYSTEM_ADMIN"}
    is_admin = any(r.get("role_code") in admin_roles for r in user.get("roles", []))
    if is_admin:
        items, total = repo.get_history_admin(year, month, page, page_size)
    else:
        items, total = repo.get_history(user["user_id"], year, month, page, page_size)

    all_approver_ids = {
        aid for s in items
        for aid in [s.l1_approver_id, s.l2_approver_id, s.l3_approver_id] if aid
    }
    approver_map: dict = {}
    if all_approver_ids:
        users_q = db.query(AppUser).filter(AppUser.user_id.in_(all_approver_ids)).all()
        approver_map = {u.user_id: u.full_name for u in users_q}

    def _enrich_hist(s):
        cs = s.control_status
        kri = cs.kri if cs else None
        return {
            "submission_id": s.submission_id,
            "status_id": s.status_id,
            "kri_id": cs.kri_id if cs else None,
            "kri_name": kri.kri_name if kri else None,
            "kri_code": kri.kri_code if kri else None,
            "region_name": kri.region.region_name if kri and kri.region else None,
            "period_year": cs.period_year if cs else None,
            "period_month": cs.period_month if cs else None,
            "final_status": s.final_status,
            "submitted_dt": s.submitted_dt,
            "submitted_by": s.submitted_by,
            "submitted_by_name": s.submitter.full_name if s.submitter else f"User #{s.submitted_by}",
            "l1_approver_name": approver_map.get(s.l1_approver_id) if s.l1_approver_id else None,
            "l1_action": s.l1_action,
            "l2_approver_name": approver_map.get(s.l2_approver_id) if s.l2_approver_id else None,
            "l2_action": s.l2_action,
            "l3_approver_name": approver_map.get(s.l3_approver_id) if s.l3_approver_id else None,
            "l3_action": s.l3_action,
        }
    return {"items": [_enrich_hist(s) for s in items], "total": total, "page": page, "page_size": page_size}


@mc_router.post("/{submission_id}/action")
def process_approval(submission_id: int, req: MakerCheckerActionRequest,
                     db: Session = Depends(get_db), user: dict = Depends(require_approvals)):
    svc = MakerCheckerService(db)
    sub = svc.process_action(submission_id, req, user["user_id"])
    return {"submission_id": sub.submission_id, "final_status": sub.final_status}

@mc_router.get("/{submission_id}")
def get_submission(submission_id: int, db: Session = Depends(get_db),
                   _user: dict = Depends(require_approvals)):
    sub = MakerCheckerRepository(db).get_by_id(submission_id)
    if not sub:
        raise HTTPException(404, "Submission not found")
    return {
        "submission_id": sub.submission_id, "status_id": sub.status_id,
        "final_status": sub.final_status, "submitted_by": sub.submitted_by,
        "submitted_dt": sub.submitted_dt,
        "l1_approver_id": sub.l1_approver_id, "l1_action": sub.l1_action,
        "l2_approver_id": sub.l2_approver_id, "l2_action": sub.l2_action,
        "l3_approver_id": sub.l3_approver_id, "l3_action": sub.l3_action,
    }


# ═══════════════════════════════════════════════════════════
# L3 ADMIN — CONTROL STATUS OVERRIDE
# ═══════════════════════════════════════════════════════════
admin_override_router = APIRouter(prefix="/api/admin", tags=["L3 Admin Override"])

@admin_override_router.post("/controls/{status_id}/override")
def admin_override_status(
    status_id: int,
    new_status: str = Body(...),
    reason: str = Body(...),
    db: Session = Depends(get_db),
    user: dict = Depends(require_system_admin),
):
    """L3 Admin can override any control status with audit trail."""
    mcs = MonthlyStatusRepository(db).get_by_id(status_id)
    if not mcs:
        raise HTTPException(404, "Control status not found")

    old_status = mcs.status
    old_rag = mcs.rag_status

    # Update status
    rag_map = {"COMPLETED": "GREEN", "APPROVED": "GREEN", "SLA_BREACHED": "RED",
               "NOT_STARTED": None, "PENDING_APPROVAL": "AMBER", "IN_PROGRESS": "AMBER"}
    mcs.status = new_status
    mcs.rag_status = rag_map.get(new_status, mcs.rag_status)
    mcs.updated_by = user["soe_id"]
    mcs.updated_dt = datetime.utcnow()
    if new_status in ("COMPLETED", "APPROVED"):
        mcs.completed_dt = datetime.utcnow()
        mcs.sla_met = mcs.sla_due_dt and datetime.utcnow() <= mcs.sla_due_dt
    db.commit()

    # Create audit trail
    audit = ApprovalAuditTrail(
        status_id=status_id,
        performed_by=user["user_id"],
        action="ADMIN_OVERRIDE",
        previous_status=old_status,
        new_status=new_status,
        comments=f"Admin override: {reason}. Previous RAG: {old_rag}",
        created_by=user["soe_id"], updated_by=user["soe_id"]
    )
    db.add(audit)
    db.commit()

    return {
        "status_id": status_id,
        "old_status": old_status, "new_status": new_status,
        "old_rag": old_rag, "new_rag": mcs.rag_status,
        "overridden_by": user["soe_id"],
        "reason": reason,
        "audit_id": audit.audit_id,
    }

@admin_override_router.get("/controls/{status_id}/audit-trail")
def get_admin_audit_trail(status_id: int, db: Session = Depends(get_db),
                          _user: dict = Depends(require_data_control)):
    """Retrieve full audit trail for a control status."""
    trails = db.query(ApprovalAuditTrail).filter(
        ApprovalAuditTrail.status_id == status_id
    ).order_by(desc(ApprovalAuditTrail.performed_dt)).all()
    return [
        {"audit_id": t.audit_id, "status_id": t.status_id,
         "performed_by": t.performed_by, "action": t.action,
         "previous_status": t.previous_status, "new_status": t.new_status,
         "comments": t.comments, "performed_dt": t.performed_dt,
         "performer_name": t.performer.full_name if t.performer else f"User #{t.performed_by}"}
        for t in trails
    ]


# ═══════════════════════════════════════════════════════════
# EVIDENCE
# ═══════════════════════════════════════════════════════════
evidence_router = APIRouter(prefix="/api/evidence", tags=["Evidence Management"])

@evidence_router.get("")
def list_evidence(
    year: int = Query(default=None), month: int = Query(default=None),
    region_id: Optional[int] = None, page: int = 1, page_size: int = 50,
    db: Session = Depends(get_db), _user: dict = Depends(require_evidence),
):
    now = datetime.utcnow()
    items, total = EvidenceRepository(db).get_all(year or now.year, month or now.month, region_id, page, page_size)
    return {"items": [
        {"evidence_id": e.evidence_id, "kri_id": e.kri_id,
         "file_name": e.file_name, "file_type": e.file_type,
         "version_number": e.version_number, "is_locked": e.is_locked,
         "uploaded_dt": e.uploaded_dt, "kri_name": e.kri.kri_name if e.kri else None}
        for e in items
    ], "total": total}

@evidence_router.post("/upload")
def upload_evidence(
    kri_id: int = Form(...), dimension_id: int = Form(...),
    year: int = Form(...), month: int = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db), user: dict = Depends(require_evidence),
):
    from app.utils import ALLOWED_FILE_TYPES

    file_ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
    if file_ext not in ALLOWED_FILE_TYPES:
        raise HTTPException(400, f"File type .{file_ext} not allowed. Allowed: {sorted(ALLOWED_FILE_TYPES)}")

    # Resolve region from the KRI (KRI is already region-bound)
    kri = KriRepository(db).get_by_id(kri_id)
    if not kri:
        raise HTTPException(404, "KRI not found")
    region_id = kri.region_id

    safe_filename = f"{uuid.uuid4().hex}_{file.filename}"
    s3_key = f"evidence/{year}/{month:02d}/region_{region_id}/kri_{kri_id}/{safe_filename}"
    content = file.file.read()
    file_size = len(content)

    s3_bucket = os.getenv("S3_BUCKET_NAME", "")
    storage_backend = "local"

    if s3_bucket:
        try:
            import boto3
            from botocore.exceptions import BotoCoreError, ClientError
            import io
            s3 = boto3.client("s3")
            s3.upload_fileobj(io.BytesIO(content), s3_bucket, s3_key)
            storage_backend = s3_bucket
        except Exception:
            # Fall through to local storage on any S3 error
            s3_bucket = ""

    if not s3_bucket:
        upload_dir = os.path.join("/tmp", "evidence", str(year), f"{month:02d}", f"region_{region_id}", f"kri_{kri_id}")
        os.makedirs(upload_dir, exist_ok=True)
        with open(os.path.join(upload_dir, safe_filename), "wb") as fh:
            fh.write(content)
        storage_backend = "local"

    svc = EvidenceService(db)
    ev = svc.upload(kri_id, dimension_id, year, month, file.filename, file_ext,
                    file_size, storage_backend, s3_key, user["user_id"], region_id)
    return {"evidence_id": ev.evidence_id, "file_name": ev.file_name, "version": ev.version_number, "region_id": region_id}

@evidence_router.post("/{evidence_id}/lock")
def lock_evidence(evidence_id: int, db: Session = Depends(get_db), user: dict = Depends(require_system_admin)):
    EvidenceService(db).lock_evidence(evidence_id, user["soe_id"])
    return {"status": "locked"}


# ═══════════════════════════════════════════════════════════
# VARIANCE
# ═══════════════════════════════════════════════════════════
variance_router = APIRouter(prefix="/api/variance", tags=["Variance Analysis"])

@variance_router.post("/submit")
def submit_variance(req: VarianceSubmitRequest, db: Session = Depends(get_db),
                    user: dict = Depends(require_variance)):
    svc = VarianceService(db)
    var = svc.submit_variance(req, user["user_id"])
    return {"variance_id": var.variance_id, "review_status": var.review_status}

@variance_router.get("/pending")
def pending_variance(page: int = 1, page_size: int = 50,
                     db: Session = Depends(get_db), _user: dict = Depends(require_variance)):
    items, total = VarianceRepository(db).get_pending(page, page_size)
    return {"items": [
        {"variance_id": v.variance_id, "metric_id": v.metric_id,
         "variance_pct": v.variance_pct, "commentary": v.commentary,
         "review_status": v.review_status, "submitted_dt": v.submitted_dt}
        for v in items
    ], "total": total}

@variance_router.post("/{variance_id}/review")
def review_variance(variance_id: int, action: str = Query(...), comments: str = Query(default=None),
                    db: Session = Depends(get_db), user: dict = Depends(require_variance)):
    svc = VarianceService(db)
    var = svc.review_variance(variance_id, action, user["user_id"], comments)
    return {"variance_id": var.variance_id, "review_status": var.review_status}


# ═══════════════════════════════════════════════════════════
# USERS & ROLES
# ═══════════════════════════════════════════════════════════
user_router = APIRouter(prefix="/api/users", tags=["User Management"])

@user_router.get("")
def list_users(page: int = 1, page_size: int = 50, db: Session = Depends(get_db),
               _user: dict = Depends(require_system_admin)):
    items, total = UserRepository(db).get_all(page, page_size)
    return {"items": [
        {"user_id": u.user_id, "soe_id": u.soe_id, "full_name": u.full_name,
         "email": u.email, "department": u.department, "is_active": u.is_active,
         "roles": [
             {"mapping_id": r.mapping_id, "role_code": r.role_code, "region_id": r.region_id, "is_active": r.is_active}
             for r in u.roles if r.is_active
         ]}
        for u in items
    ], "total": total}

@user_router.post("")
def create_user(data: UserCreate, db: Session = Depends(get_db), user: dict = Depends(require_system_admin)):
    repo = UserRepository(db)
    if repo.get_by_soe_id(data.soe_id):
        raise HTTPException(400, "SOE ID already exists")
    return repo.create({**data.model_dump(exclude={"password", "roles"}),
                        "created_by": user["soe_id"], "updated_by": user["soe_id"]})

@user_router.put("/{user_id}")
def update_user(user_id: int, data: UserUpdate, db: Session = Depends(get_db),
                user: dict = Depends(require_system_admin)):
    repo = UserRepository(db)
    target = repo.get_by_id(user_id)
    if not target:
        raise HTTPException(404, "User not found")
    return repo.update(target, {**data.model_dump(exclude_unset=True), "updated_by": user["soe_id"]})

@user_router.post("/assign-role")
def assign_role(data: RoleAssignment, db: Session = Depends(get_db), user: dict = Depends(require_system_admin)):
    user_repo = UserRepository(db)
    
    # Check if user already has an active role
    existing_roles = user_repo.get_roles(data.user_id)
    had_previous_role = len(existing_roles) > 0
    
    if had_previous_role:
        previous_role_code = existing_roles[0].role_code if existing_roles else None
    
    # Assign new role (automatically deactivates previous)
    result = user_repo.assign_role({
        **data.model_dump(),
        "is_active": True,
        "created_by": user["soe_id"],
        "updated_by": user["soe_id"]
    })
    
    return {
        "mapping_id": result.mapping_id,
        "user_id": result.user_id,
        "role_code": result.role_code,
        "region_id": result.region_id,
        "previous_role_code": previous_role_code if had_previous_role else None,
        "replaced_existing": had_previous_role
    }

@user_router.get("/{user_id}/roles")
def get_user_roles(user_id: int, db: Session = Depends(get_db), _user: dict = Depends(require_system_admin)):
    roles = UserRepository(db).get_roles(user_id)
    return [{"mapping_id": r.mapping_id, "role_code": r.role_code, "region_id": r.region_id,
             "effective_from": r.effective_from, "effective_to": r.effective_to} for r in roles]

@user_router.get("/by-role/{role_code}")
def users_by_role(role_code: str, region_id: Optional[int] = None,
                  db: Session = Depends(get_db), _user: dict = Depends(require_system_admin)):
    users = UserRepository(db).get_users_by_role(role_code, region_id)
    return [{"user_id": u.user_id, "soe_id": u.soe_id, "full_name": u.full_name} for u in users]


# ═══════════════════════════════════════════════════════════
# ESCALATION CONFIG
# ═══════════════════════════════════════════════════════════
escalation_router = APIRouter(prefix="/api/escalation", tags=["Escalation"])

@escalation_router.get("")
def list_escalations(db: Session = Depends(get_db), _user: dict = Depends(require_escalation_metrics)):
    configs = EscalationRepository(db).get_all()
    return [{"config_id": c.config_id, "escalation_type": c.escalation_type,
             "threshold_hours": c.threshold_hours, "reminder_hours": c.reminder_hours,
             "escalate_to_role": c.escalate_to_role} for c in configs]

@escalation_router.post("")
def create_escalation(data: EscalationConfigCreate, db: Session = Depends(get_db),
                      user: dict = Depends(require_system_admin)):
    return EscalationRepository(db).create({**data.model_dump(), "created_by": user["soe_id"], "updated_by": user["soe_id"]})

@escalation_router.put("/{config_id}")
def update_escalation(config_id: int, data: EscalationConfigUpdate,
                      db: Session = Depends(get_db), user: dict = Depends(require_system_admin)):
    repo = EscalationRepository(db)
    config = repo.get_by_id(config_id)
    if not config:
        raise HTTPException(404, "Escalation config not found")
    updated = repo.update(config, {**data.model_dump(exclude_unset=True), "updated_by": user["soe_id"]})
    return {"config_id": updated.config_id, "escalation_type": updated.escalation_type,
            "threshold_hours": updated.threshold_hours, "reminder_hours": updated.reminder_hours,
            "max_reminders": updated.max_reminders, "escalate_to_role": updated.escalate_to_role,
            "region_id": updated.region_id, "is_active": updated.is_active}

@escalation_router.delete("/{config_id}")
def delete_escalation(config_id: int, db: Session = Depends(get_db), user: dict = Depends(require_system_admin)):
    repo = EscalationRepository(db)
    config = repo.get_by_id(config_id)
    if not config:
        raise HTTPException(404, "Escalation config not found")
    repo.update(config, {"is_active": False, "updated_by": user["soe_id"]})
    return {"status": "deleted", "config_id": config_id}


# ═══════════════════════════════════════════════════════════
# NOTIFICATIONS
# ═══════════════════════════════════════════════════════════
notification_router = APIRouter(prefix="/api/notifications", tags=["Notifications"])

@notification_router.get("")
def list_notifications(unread_only: bool = False, db: Session = Depends(get_db),
                       user: dict = Depends(get_current_user)):
    items = NotificationRepository(db).get_for_user(user["user_id"], unread_only)
    return [{"notification_id": n.notification_id, "title": n.title, "message": n.message,
             "notification_type": n.notification_type, "is_read": n.is_read,
             "created_dt": n.created_dt} for n in items]

@notification_router.get("/count")
def unread_count(db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    return {"count": NotificationRepository(db).unread_count(user["user_id"])}

@notification_router.post("/{notification_id}/read")
def mark_read(notification_id: int, db: Session = Depends(get_db), _user: dict = Depends(get_current_user)):
    NotificationRepository(db).mark_read(notification_id)
    return {"status": "ok"}


# ═══════════════════════════════════════════════════════════
# COMMENTS
# ═══════════════════════════════════════════════════════════
comment_router = APIRouter(prefix="/api/comments", tags=["Comments"])

@comment_router.post("")
def add_comment(data: CommentCreate, db: Session = Depends(get_db), user: dict = Depends(require_any_authenticated)):
    return CommentRepository(db).create({**data.model_dump(), "posted_by": user["user_id"],
                                          "created_by": user["soe_id"], "updated_by": user["soe_id"]})

@comment_router.get("/kri/{kri_id}")
def kri_comments(kri_id: int, db: Session = Depends(get_db), _user: dict = Depends(require_any_authenticated)):
    comments = CommentRepository(db).get_for_kri(kri_id)
    return [{"comment_id": c.comment_id, "comment_text": c.comment_text,
             "comment_type": c.comment_type, "posted_dt": c.posted_dt,
             "poster_name": c.poster.full_name if c.poster else None}
            for c in comments]


# ═══════════════════════════════════════════════════════════
# DATA SOURCES
# ═══════════════════════════════════════════════════════════
datasource_router = APIRouter(prefix="/api/data-sources", tags=["Data Sources"])

@datasource_router.get("/{kri_id}")
def get_data_sources(kri_id: int, db: Session = Depends(get_db), _user: dict = Depends(require_data_control)):
    return [{"source_id": s.source_id, "source_name": s.source_name,
             "source_type": s.source_type, "is_active": s.is_active}
            for s in DataSourceRepository(db).get_for_kri(kri_id)]

@datasource_router.post("")
def create_data_source(data: DataSourceCreate, db: Session = Depends(get_db), user: dict = Depends(require_system_admin)):
    return DataSourceRepository(db).create({**data.model_dump(), "created_by": user["soe_id"], "updated_by": user["soe_id"]})


# ═══════════════════════════════════════════════════════════
# ESCALATION METRICS (read-only — MANAGEMENT + SYSTEM_ADMIN)
# ═══════════════════════════════════════════════════════════
escalation_metrics_router = APIRouter(prefix="/api/escalation-metrics", tags=["Escalation Metrics"])

@escalation_metrics_router.get("/summary")
def escalation_metrics_summary(
    db: Session = Depends(get_db),
    _user: dict = Depends(require_escalation_metrics),
):
    """KPI summary for the Escalation Metrics page (derived from EscalationConfig rules)."""
    from app.models import EscalationConfig

    configs = db.query(EscalationConfig).filter(EscalationConfig.is_active == True).all()

    # Group by escalate_to_role to find most targeted role
    role_counts: dict = {}
    type_counts: dict = {}
    for c in configs:
        role_counts[c.escalate_to_role] = role_counts.get(c.escalate_to_role, 0) + 1
        type_counts[c.escalation_type] = type_counts.get(c.escalation_type, 0) + 1

    top_role = max(role_counts, key=role_counts.get) if role_counts else "—"
    by_type = [{"escalation_type": k, "count": v} for k, v in type_counts.items()]

    return {
        "total_escalations": 0,       # No EscalationLog table yet — placeholder
        "pending_escalations": 0,     # No EscalationLog table yet — placeholder
        "top_escalated_role": top_role,
        "by_type": by_type,
    }


# ═══════════════════════════════════════════════════════════
# APPROVAL ASSIGNMENT RULES
# ═══════════════════════════════════════════════════════════
assignment_rule_router = APIRouter(prefix="/api/assignment-rules", tags=["Assignment Rules"])

@assignment_rule_router.get("")
def list_assignment_rules(
    db: Session = Depends(get_db),
    _user: dict = Depends(require_system_admin),
):
    """List all active approval assignment rules."""
    rules = ApproverRuleRepository(db).get_all(active_only=False)
    return [
        {
            "rule_id": r.rule_id, "role_code": r.role_code,
            "user_id": r.user_id,
            "user_name": r.user.full_name if r.user else None,
            "region_id": r.region_id,
            "region_name": r.region.region_name if r.region else None,
            "kri_id": r.kri_id,
            "kri_name": r.kri.kri_name if r.kri else None,
            "category_id": r.category_id,
            "category_name": r.category.category_name if r.category else None,
            "priority": r.priority, "is_active": r.is_active,
        }
        for r in rules
    ]

@assignment_rule_router.post("")
def create_assignment_rule(
    data: dict = Body(...),
    db: Session = Depends(get_db),
    user: dict = Depends(require_system_admin),
):
    rule = ApproverRuleRepository(db).create({
        **data,
        "created_by": user["soe_id"], "updated_by": user["soe_id"],
    })
    return {"rule_id": rule.rule_id, "role_code": rule.role_code, "priority": rule.priority}

@assignment_rule_router.put("/{rule_id}")
def update_assignment_rule(
    rule_id: int, data: dict = Body(...),
    db: Session = Depends(get_db),
    user: dict = Depends(require_system_admin),
):
    repo = ApproverRuleRepository(db)
    rule = repo.get_by_id(rule_id)
    if not rule:
        raise HTTPException(404, "Rule not found")
    updated = repo.update(rule, {**data, "updated_by": user["soe_id"]})
    return {"rule_id": updated.rule_id, "role_code": updated.role_code}

@assignment_rule_router.delete("/{rule_id}")
def delete_assignment_rule(
    rule_id: int,
    db: Session = Depends(get_db),
    _user: dict = Depends(require_system_admin),
):
    repo = ApproverRuleRepository(db)
    rule = repo.get_by_id(rule_id)
    if not rule:
        raise HTTPException(404, "Rule not found")
    repo.deactivate(rule)
    return {"status": "deactivated"}


# ═══════════════════════════════════════════════════════════
# HEALTH
# ═══════════════════════════════════════════════════════════
health_router = APIRouter(tags=["Health"])

@health_router.get("/health")
def health():
    return {"status": "healthy", "version": "1.0.0", "timestamp": datetime.utcnow().isoformat()}

@health_router.get("/api/health")
def api_health(db: Session = Depends(get_db)):
    try:
        db.execute("SELECT 1" if False else None)
    except:
        pass
    return {"status": "healthy", "database": "connected", "timestamp": datetime.utcnow().isoformat()}
