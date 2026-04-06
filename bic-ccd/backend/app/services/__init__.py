"""Service layer — business logic for BIC-CCD."""
from datetime import datetime, timedelta, date
from typing import Optional, List
from sqlalchemy.orm import Session
from fastapi import HTTPException, status
import hashlib, secrets, json

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
    KriCreate, KriUpdate, KriOnboardRequest,
    MakerCheckerSubmitRequest, MakerCheckerActionRequest,
    VarianceSubmitRequest, ApprovalActionRequest, CommentCreate,
)
from app.models import MakerCheckerSubmission


# ─── Auth Service ───────────────────────────────────────────
class AuthService:
    """Simple auth for demo; replace with SSO/LDAP in production."""
    def __init__(self, db: Session):
        self.user_repo = UserRepository(db)
        self.db = db

    def authenticate(self, soe_id: str, password: str) -> dict:
        user = self.user_repo.get_by_soe_id(soe_id)
        if not user:
            raise HTTPException(status_code=401, detail="Invalid credentials")
        # Demo: accept any password for dev; real impl uses LDAP/SSO
        if not user.is_active:
            raise HTTPException(status_code=403, detail="Account disabled")
        user.last_login_dt = datetime.utcnow()
        self.db.commit()
        roles = self.user_repo.get_roles(user.user_id)
        return {
            "user_id": user.user_id,
            "soe_id": user.soe_id,
            "full_name": user.full_name,
            "email": user.email,
            "roles": [
                {"role_code": r.role_code, "region_id": r.region_id}
                for r in roles
            ]
        }


# ─── Dashboard Service ──────────────────────────────────────
class DashboardService:
    def __init__(self, db: Session):
        self.status_repo = MonthlyStatusRepository(db)
        self.kri_repo = KriRepository(db)
        self.evidence_repo = EvidenceRepository(db)
        self.region_repo = RegionRepository(db)

    def get_summary(self, year: int, month: int, region_id: int = None) -> dict:
        counts = self.status_repo.get_summary_counts(year, month, region_id)
        total = sum(counts.values()) or 1  # avoid div zero
        sla_met = counts.get("COMPLETED", 0) + counts.get("APPROVED", 0)
        sla_breached = counts.get("SLA_BREACHED", 0)
        not_started = counts.get("NOT_STARTED", 0)
        pending = counts.get("PENDING_APPROVAL", 0)

        regions = self.region_repo.get_all()
        return {
            "total_kris": total,
            "sla_met": sla_met,
            "sla_met_pct": round(sla_met / total * 100, 1) if total else 0,
            "sla_breached": sla_breached,
            "sla_breached_pct": round(sla_breached / total * 100, 1) if total else 0,
            "not_started": not_started,
            "not_started_pct": round(not_started / total * 100, 1) if total else 0,
            "pending_approvals": pending,
            "regions": [r.region_code for r in regions],
            "period": f"{datetime(year, month, 1):%B %Y}",
            "last_updated": datetime.utcnow(),
        }

    def get_trend(self, months: int = 6, region_id: int = None) -> List[dict]:
        return self.status_repo.get_trend_data(months, region_id)

    def get_dimension_breakdown(self, year: int, month: int, region_id: int = None) -> List[dict]:
        return self.status_repo.get_dimension_breakdown(year, month, region_id)

    def get_sla_distribution(self, year: int, month: int, region_id: int = None) -> dict:
        counts = self.status_repo.get_summary_counts(year, month, region_id)
        return {
            "sla_met": counts.get("COMPLETED", 0) + counts.get("APPROVED", 0),
            "sla_breached": counts.get("SLA_BREACHED", 0),
            "not_started": counts.get("NOT_STARTED", 0),
        }

    def get_evidence_completeness(self, year: int, month: int) -> dict:
        return self.evidence_repo.get_completeness(year, month)


# ─── KRI Service ────────────────────────────────────────────
class KriService:
    def __init__(self, db: Session):
        self.kri_repo = KriRepository(db)
        self.config_repo = KriConfigRepository(db)
        self.assign_repo = AssignmentRepository(db)
        self.ds_repo = DataSourceRepository(db)
        self.db = db

    def list_kris(self, region_id=None, category_id=None, page=1, page_size=50):
        items, total = self.kri_repo.get_all(region_id, category_id, True, page, page_size)
        results = []
        for kri in items:
            results.append({
                "kri_id": kri.kri_id,
                "kri_code": kri.kri_code,
                "kri_name": kri.kri_name,
                "description": kri.description,
                "category_id": kri.category_id,
                "category_name": kri.category.category_name if kri.category else None,
                "region_id": kri.region_id,
                "region_name": kri.region.region_name if kri.region else None,
                "risk_level": kri.risk_level,
                "framework": kri.framework,
                "is_active": kri.is_active,
                "onboarded_dt": kri.onboarded_dt,
                "created_dt": kri.created_dt,
            })
        return results, total

    def create_kri(self, data: KriCreate, created_by: str):
        if self.kri_repo.get_by_code(data.kri_code):
            raise HTTPException(400, "KRI code already exists")
        return self.kri_repo.create({
            **data.model_dump(),
            "created_by": created_by,
            "updated_by": created_by,
            "onboarded_dt": datetime.utcnow(),
        })

    def update_kri(self, kri_id: int, data: KriUpdate, updated_by: str):
        kri = self.kri_repo.get_by_id(kri_id)
        if not kri:
            raise HTTPException(404, "KRI not found")
        return self.kri_repo.update(kri, {**data.model_dump(exclude_unset=True), "updated_by": updated_by})

    def onboard_kri(self, req: KriOnboardRequest, created_by: str) -> dict:
        """Multi-step wizard: create KRI, configs, assignments, data sources."""
        kri = self.create_kri(KriCreate(
            kri_code=req.kri_code, kri_name=req.kri_name,
            description=req.description, category_id=req.category_id,
            region_id=req.region_id, risk_level=req.risk_level,
            framework=req.framework
        ), created_by)

        configs = []
        for dim_cfg in req.dimensions:
            cfg = self.config_repo.create({
                **dim_cfg.model_dump(),
                "kri_id": kri.kri_id,
                "created_by": created_by,
                "updated_by": created_by,
            })
            configs.append(cfg)

        assignments = []
        for assign in req.assignments:
            a = self.assign_repo.create({
                **assign,
                "kri_id": kri.kri_id,
                "created_by": created_by,
                "updated_by": created_by,
            })
            assignments.append(a)

        sources = []
        for ds in req.data_sources:
            s = self.ds_repo.create({
                **ds,
                "kri_id": kri.kri_id,
                "created_by": created_by,
                "updated_by": created_by,
            })
            sources.append(s)

        return {
            "kri_id": kri.kri_id,
            "kri_code": kri.kri_code,
            "configurations": len(configs),
            "assignments": len(assignments),
            "data_sources": len(sources),
        }


# ─── Assignment Service ─────────────────────────────────────
class AssignmentService:
    """Resolves which user should approve at each level for a given KRI."""

    def __init__(self, db: Session):
        self.rule_repo = ApproverRuleRepository(db)
        self.kri_repo = KriRepository(db)

    def resolve_approver(self, role_code: str, kri_id: int = None) -> Optional[int]:
        """Return the best-matching approver user_id for role_code + kri context.

        Falls back through: kri-specific → category → region → global rule.
        Returns None when no matching rule exists (caller must handle).
        """
        region_id = None
        category_id = None
        if kri_id:
            kri = self.kri_repo.get_by_id(kri_id)
            if kri:
                region_id = kri.region_id
                category_id = kri.category_id

        return self.rule_repo.resolve(
            role_code=role_code,
            kri_id=kri_id,
            region_id=region_id,
            category_id=category_id,
        )


# ─── Maker Checker Service ──────────────────────────────────
class MakerCheckerService:
    def __init__(self, db: Session):
        self.mc_repo = MakerCheckerRepository(db)
        self.status_repo = MonthlyStatusRepository(db)
        self.audit_repo = ApprovalAuditRepository(db)
        self.notif_repo = NotificationRepository(db)
        self.assign_svc = AssignmentService(db)
        self.db = db

    def submit(self, req: MakerCheckerSubmitRequest, submitted_by: int) -> MakerCheckerSubmission:
        status_obj = self.status_repo.get_by_id(req.status_id)
        if not status_obj:
            raise HTTPException(404, "Control status not found")

        # Auto-resolve L1 approver from assignment rules when not explicitly provided
        l1_approver_id = req.l1_approver_id
        if not l1_approver_id:
            l1_approver_id = self.assign_svc.resolve_approver(
                role_code="L1_APPROVER",
                kri_id=status_obj.kri_id,
            )

        sub = self.mc_repo.create({
            "status_id": req.status_id,
            "evidence_id": req.evidence_id,
            "submitted_by": submitted_by,
            "submission_notes": req.submission_notes,
            "l1_approver_id": l1_approver_id,
            "final_status": "L1_PENDING",
            "created_by": str(submitted_by),
            "updated_by": str(submitted_by),
        })

        self.status_repo.update_status(status_obj, "PENDING_APPROVAL", "L1", l1_approver_id)

        self.audit_repo.create({
            "status_id": req.status_id,
            "action": "SUBMITTED",
            "performed_by": submitted_by,
            "previous_status": "IN_PROGRESS",
            "new_status": "PENDING_APPROVAL",
            "created_by": str(submitted_by),
            "updated_by": str(submitted_by),
        })

        if l1_approver_id:
            self.notif_repo.create({
                "user_id": l1_approver_id,
                "title": "New Approval Request",
                "message": f"Submission #{sub.submission_id} awaits your L1 review.",
                "notification_type": "APPROVAL_REQUEST",
                "created_by": str(submitted_by),
                "updated_by": str(submitted_by),
            })

        return sub

    def process_action(self, submission_id: int, action_req: MakerCheckerActionRequest,
                       performed_by: int) -> MakerCheckerSubmission:
        sub = self.mc_repo.get_by_id(submission_id)
        if not sub:
            raise HTTPException(404, "Submission not found")

        action = action_req.action.upper()
        level = sub.final_status.replace("_PENDING", "")  # L1, L2, L3

        if level == "L1":
            if action == "ESCALATE":
                escalate_to = self._resolve_escalation_target(sub, "L2_APPROVER", action_req.next_approver_id)
                sub.l2_approver_id = escalate_to
                sub.final_status = "L2_PENDING"
                if escalate_to:
                    self._notify(escalate_to, sub, "L2 (Escalated)")
            else:
                sub.l1_action = action
                sub.l1_action_dt = datetime.utcnow()
                sub.l1_comments = action_req.comments
                if action == "APPROVED":
                    if action_req.next_approver_id:
                        sub.l2_approver_id = action_req.next_approver_id
                        sub.final_status = "L2_PENDING"
                        self._notify(action_req.next_approver_id, sub, "L2")
                    else:
                        sub.final_status = "APPROVED"
                elif action in ("REJECTED", "REWORK"):
                    sub.final_status = "REWORK" if action == "REWORK" else "REJECTED"
        elif level == "L2":
            if action == "ESCALATE":
                escalate_to = self._resolve_escalation_target(sub, "L3_ADMIN", action_req.next_approver_id)
                sub.l3_approver_id = escalate_to
                sub.final_status = "L3_PENDING"
                if escalate_to:
                    self._notify(escalate_to, sub, "L3 (Escalated)")
            else:
                sub.l2_action = action
                sub.l2_action_dt = datetime.utcnow()
                sub.l2_comments = action_req.comments
                if action == "APPROVED":
                    if action_req.next_approver_id:
                        sub.l3_approver_id = action_req.next_approver_id
                        sub.final_status = "L3_PENDING"
                        self._notify(action_req.next_approver_id, sub, "L3")
                    else:
                        sub.final_status = "APPROVED"
                elif action in ("REJECTED", "REWORK"):
                    sub.final_status = "REWORK" if action == "REWORK" else "REJECTED"
        elif level == "L3":
            sub.l3_action = action
            sub.l3_action_dt = datetime.utcnow()
            sub.l3_comments = action_req.comments
            sub.final_status = "APPROVED" if action == "APPROVED" else ("REWORK" if action == "REWORK" else "REJECTED")

        # Update monthly control status
        status_obj = self.status_repo.get_by_id(sub.status_id)
        if sub.final_status == "APPROVED":
            self.status_repo.update_status(status_obj, "COMPLETED")
        elif sub.final_status == "REWORK":
            self.status_repo.update_status(status_obj, "REWORK")
        elif sub.final_status == "REJECTED":
            self.status_repo.update_status(status_obj, "REWORK")

        self.audit_repo.create({
            "status_id": sub.status_id,
            "action": f"{level}_{action}",
            "performed_by": performed_by,
            "comments": action_req.comments,
            "previous_status": f"{level}_PENDING",
            "new_status": sub.final_status,
            "created_by": str(performed_by),
            "updated_by": str(performed_by),
        })

        return self.mc_repo.update(sub)

    def _resolve_escalation_target(self, sub: MakerCheckerSubmission, role_code: str,
                                    explicit_id: Optional[int] = None) -> Optional[int]:
        """Find the best escalation target: explicit override > KRI assignment > assignment rule."""
        if explicit_id:
            return explicit_id
        # Look for KRI-specific assignment in kri_assignment table
        from app.models import KriAssignment, MonthlyControlStatus
        status_obj = self.status_repo.get_by_id(sub.status_id)
        if status_obj:
            assignment = self.db.query(KriAssignment).filter(
                KriAssignment.kri_id == status_obj.kri_id,
                KriAssignment.role_code == role_code,
                KriAssignment.is_active == True,
            ).first()
            if assignment:
                return assignment.assigned_user_id
            # Fall back to assignment rules
            return self.assign_svc.resolve_approver(role_code=role_code, kri_id=status_obj.kri_id)
        return None

    def _notify(self, user_id: int, sub: MakerCheckerSubmission, level: str):
        self.notif_repo.create({
            "user_id": user_id,
            "title": f"{level} Approval Request",
            "message": f"Submission #{sub.submission_id} needs your {level} review.",
            "notification_type": "APPROVAL_REQUEST",
            "created_by": "SYSTEM",
            "updated_by": "SYSTEM",
        })


# ─── Variance Service ──────────────────────────────────────
class VarianceService:
    def __init__(self, db: Session):
        self.var_repo = VarianceRepository(db)
        self.metric_repo = MetricRepository(db)
        self.db = db

    def submit_variance(self, req: VarianceSubmitRequest, submitted_by: int):
        from app.models import MetricValues
        metric = self.db.query(MetricValues).filter(MetricValues.metric_id == req.metric_id).first()
        if not metric:
            raise HTTPException(404, "Metric not found")

        return self.var_repo.create({
            "metric_id": req.metric_id,
            "status_id": req.status_id,
            "variance_pct": metric.variance_pct or 0,
            "commentary": req.commentary,
            "submitted_by": submitted_by,
            "created_by": str(submitted_by),
            "updated_by": str(submitted_by),
        })

    def review_variance(self, variance_id: int, action: str, reviewer_id: int, comments: str = None):
        var = self.var_repo.get_by_id(variance_id)
        if not var:
            raise HTTPException(404, "Variance submission not found")
        var.review_status = action
        var.reviewed_by = reviewer_id
        var.reviewed_dt = datetime.utcnow()
        var.review_comments = comments
        self.db.commit()
        self.db.refresh(var)
        return var


# ─── Evidence Service ───────────────────────────────────────
class EvidenceService:
    def __init__(self, db: Session):
        self.ev_repo = EvidenceRepository(db)
        self.db = db

    def upload(self, kri_id: int, dimension_id: int, year: int, month: int,
               file_name: str, file_type: str, file_size: int,
               s3_bucket: str, s3_key: str, uploaded_by: int, region_id: int = None):
        ev = self.ev_repo.create({
            "kri_id": kri_id,
            "dimension_id": dimension_id,
            "period_year": year,
            "period_month": month,
            "file_name": file_name,
            "file_type": file_type,
            "file_size_bytes": file_size,
            "s3_bucket": s3_bucket,
            "s3_key": s3_key,
            "region_id": region_id,
            "uploaded_by": uploaded_by,
            "created_by": str(uploaded_by),
            "updated_by": str(uploaded_by),
        })
        self.ev_repo.create_version({
            "evidence_id": ev.evidence_id,
            "version_number": 1,
            "s3_key": s3_key,
            "file_size_bytes": file_size,
            "action": "UPLOAD",
            "performed_by": uploaded_by,
            "created_by": str(uploaded_by),
            "updated_by": str(uploaded_by),
        })
        return ev

    def lock_evidence(self, evidence_id: int, locked_by: str):
        ev = self.ev_repo.get_by_id(evidence_id)
        if not ev:
            raise HTTPException(404, "Evidence not found")
        self.ev_repo.lock(ev, locked_by)
        return ev
