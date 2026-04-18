"""Service layer — business logic for BIC-CCD."""
import logging
from datetime import datetime, timedelta, date
from typing import Optional, List
from sqlalchemy.orm import Session
from fastapi import HTTPException, status
import hashlib, secrets, json

logger = logging.getLogger("bic_ccd.services")

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
from app.models import MakerCheckerSubmission, AppUser
from app.utils import compute_pending_with


# ─── Status Transition Guard ────────────────────────────────
# Valid transitions: {from_status: {action: to_status}}
# Actions are the normalised strings used in MakerCheckerService (APPROVED, REWORK, REJECTED)
_VALID_TRANSITIONS: dict[str, set[str]] = {
    "NOT_STARTED":      {"start"},
    "IN_PROGRESS":      {"SUBMIT"},
    "PENDING_APPROVAL": {"APPROVED", "REWORK", "REJECTED", "ESCALATE"},
    "REWORK":           {"SUBMIT"},
    "REJECTED":         set(),          # terminal
    "COMPLETED":        set(),          # terminal
    "APPROVED":         set(),          # terminal
    "SLA_BREACHED":     {"SUBMIT"},     # late submission still allowed
}


def validate_transition(from_status: str, action: str, is_admin: bool = False) -> bool:
    """Return True if *action* is valid from *from_status*.

    Admins always pass (override intent); a warning should be logged by the caller.
    """
    if is_admin:
        return True
    allowed = _VALID_TRANSITIONS.get(from_status, set())
    return action.upper() in allowed


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
        # Previous month boundaries
        prev_month = month - 1
        prev_year = year
        if prev_month <= 0:
            prev_month += 12
            prev_year -= 1

        # Single query fetches current + previous month status counts.
        # Previously two sequential get_summary_counts calls = 2 Oracle round-trips.
        multi = self.status_repo.get_multi_period_summary_counts(
            [(year, month), (prev_year, prev_month)], region_id
        )
        counts = multi.get((year, month), {})
        prev_counts = multi.get((prev_year, prev_month), {})

        total = sum(counts.values())
        pct_base = total or 1
        sla_met = counts.get("COMPLETED", 0) + counts.get("APPROVED", 0)
        sla_breached = counts.get("SLA_BREACHED", 0)
        not_started = counts.get("NOT_STARTED", 0)
        pending = counts.get("PENDING_APPROVAL", 0)

        # Pending approvals grouped by level
        pending_by_level = self.status_repo.get_pending_approvals_by_level(year, month, region_id)

        prev_total = sum(prev_counts.values()) or 1
        prev_sla_met = prev_counts.get("COMPLETED", 0) + prev_counts.get("APPROVED", 0)
        prev_sla_breached = prev_counts.get("SLA_BREACHED", 0)
        mom_sla_met_pct = round((sla_met - prev_sla_met) / prev_total * 100, 1) if prev_total else None
        mom_sla_breached_delta = sla_breached - prev_sla_breached
        mom_period_label = f"{datetime(prev_year, prev_month, 1):%b %Y}"

        if region_id:
            region = self.region_repo.get_by_id(region_id)
            region_codes = [region.region_code] if region else []
        else:
            region_codes = [r.region_code for r in self.region_repo.get_all()]

        return {
            "total_kris": total,
            "sla_met": sla_met,
            "sla_met_pct": round(sla_met / pct_base * 100, 1),
            "sla_breached": sla_breached,
            "sla_breached_pct": round(sla_breached / pct_base * 100, 1),
            "not_started": not_started,
            "not_started_pct": round(not_started / pct_base * 100, 1),
            "pending_approvals": pending,
            "pending_by_level": pending_by_level,
            "regions": region_codes,
            "period": f"{datetime(year, month, 1):%B %Y}",
            "last_updated": datetime.utcnow(),
            "mom_sla_met_pct": mom_sla_met_pct,
            "mom_sla_breached_delta": mom_sla_breached_delta,
            "mom_period_label": mom_period_label,
        }

    def get_trend(self, months: int = 6, region_id: int = None, year: int = None, month: int = None) -> List[dict]:
        return self.status_repo.get_trend_data(months, region_id, year, month)

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
        from app.utils import sort_kris
        items, total = self.kri_repo.get_all(region_id, category_id, True, page, page_size)
        results = []
        for kri in sort_kris(items):
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

        # Accumulate all inserts/updates in the session; commit once at the end.
        # Previously 4 sequential commits = 4 Oracle round-trips (~800ms at 200ms RTT).
        sub = self.mc_repo.create({
            "status_id": req.status_id,
            "evidence_id": req.evidence_id,
            "submitted_by": submitted_by,
            "submission_notes": req.submission_notes,
            "l1_approver_id": l1_approver_id,
            "final_status": "L1_PENDING",
            "created_by": str(submitted_by),
            "updated_by": str(submitted_by),
        }, autocommit=False)

        self.status_repo.update_status(
            status_obj, "PENDING_APPROVAL", "L1", l1_approver_id, autocommit=False
        )

        self.audit_repo.create({
            "status_id": req.status_id,
            "action": "SUBMITTED",
            "performed_by": submitted_by,
            "previous_status": "IN_PROGRESS",
            "new_status": "PENDING_APPROVAL",
            "created_by": str(submitted_by),
            "updated_by": str(submitted_by),
        }, autocommit=False)

        if l1_approver_id:
            self.notif_repo.create({
                "user_id": l1_approver_id,
                "title": "New Approval Request",
                "message": f"Submission #{sub.submission_id} awaits your L1 review.",
                "notification_type": "APPROVAL_REQUEST",
                "created_by": str(submitted_by),
                "updated_by": str(submitted_by),
            }, autocommit=False)

        self.db.commit()
        self.db.refresh(sub)
        return sub

    def _resolve_escalation_target(
        self, sub: MakerCheckerSubmission, current_level: str, next_approver_id_hint: Optional[int]
    ) -> int:
        """Resolve the correct escalation target user ID.

        Priority order:
          1. current pending-with user at the NEXT level (already assigned)
          2. next_approver_id_hint from the request (explicit override — frontend sends this)
          3. assignment rules lookup for the next level role
          4. any active user with the required role (last-resort DB scan)

        Raises HTTP 422 only when no target can be resolved through any mechanism.
        """
        # Determine which level we are escalating TO
        next_level_map = {"L1": "L2", "L2": "L3"}
        next_level = next_level_map.get(current_level)
        if not next_level:
            raise HTTPException(422, "L3 submissions cannot be escalated further")

        next_role_map = {"L2": "L2_APPROVER", "L3": "L3_ADMIN"}
        next_role = next_role_map[next_level]

        # 1. Already-assigned approver for the next level
        existing = sub.l2_approver_id if next_level == "L2" else sub.l3_approver_id
        if existing:
            logger.debug("Escalation target resolved from existing FK: user #%s", existing)
            return existing

        # 2. Explicit hint from caller (frontend sends next_approver_id for ESCALATE)
        if next_approver_id_hint:
            logger.debug("Escalation target resolved from request hint: user #%s", next_approver_id_hint)
            return next_approver_id_hint

        # 3. Assignment rule lookup
        status_obj = self.status_repo.get_by_id(sub.status_id)
        kri_id = status_obj.kri_id if status_obj else None
        resolved = self.assign_svc.resolve_approver(role_code=next_role, kri_id=kri_id)
        if resolved:
            logger.debug("Escalation target resolved from assignment rules: user #%s", resolved)
            return resolved

        # 4. Last-resort: find any active user with the required role
        from app.models import UserRoleMapping as _UserRoleMapping
        fallback_user = (
            self.db.query(AppUser)
            .join(_UserRoleMapping, _UserRoleMapping.user_id == AppUser.user_id)
            .filter(
                _UserRoleMapping.role_code == next_role,
                _UserRoleMapping.is_active == True,
                AppUser.is_active == True,
            )
            .first()
        )
        if fallback_user:
            logger.warning(
                "Escalation target resolved by role scan (no assignment rule): "
                "user #%s for role %s on submission #%s",
                fallback_user.user_id, next_role, sub.submission_id,
            )
            return fallback_user.user_id

        raise HTTPException(
            422,
            f"No active {next_role} user found for escalation from {current_level}. "
            "Please ensure at least one user has this role assigned."
        )

    def process_action(self, submission_id: int, action_req: MakerCheckerActionRequest,
                       performed_by: int, is_admin: bool = False) -> MakerCheckerSubmission:
        sub = self.mc_repo.get_by_id(submission_id)
        if not sub:
            raise HTTPException(404, "Submission not found")

        action = action_req.action.upper()
        level = sub.final_status.replace("_PENDING", "")  # L1, L2, L3

        # ── 2H: Status transition guard ──────────────────────
        if not validate_transition("PENDING_APPROVAL", action, is_admin=is_admin):
            if is_admin:
                logger.warning(
                    "Admin override: transition PENDING_APPROVAL → %s on submission %s by user %s",
                    action, submission_id, performed_by,
                )
            else:
                raise HTTPException(422, f"Action '{action}' is not valid from PENDING_APPROVAL status")

        now = datetime.utcnow()

        if level == "L1":
            sub.l1_action = action
            sub.l1_action_dt = now
            sub.l1_comments = action_req.comments
            if action == "APPROVED":
                l2_id = action_req.next_approver_id
                if not l2_id:
                    # Auto-resolve L2 approver via assignment rules
                    _mcs = self.status_repo.get_by_id(sub.status_id)
                    l2_id = self.assign_svc.resolve_approver(
                        role_code="L2_APPROVER",
                        kri_id=_mcs.kri_id if _mcs else None,
                    )
                if not l2_id:
                    # Last-resort: any active L2_APPROVER in the system
                    from app.models import UserRoleMapping as _URM
                    _fb = (
                        self.db.query(AppUser)
                        .join(_URM, _URM.user_id == AppUser.user_id)
                        .filter(_URM.role_code == "L2_APPROVER", _URM.is_active == True, AppUser.is_active == True)
                        .first()
                    )
                    if _fb:
                        l2_id = _fb.user_id
                if l2_id:
                    sub.l2_approver_id = l2_id
                    sub.final_status = "L2_PENDING"
                    self._notify(l2_id, sub, "L2")
                else:
                    sub.final_status = "APPROVED"
            elif action == "REWORK":
                sub.final_status = "REWORK"
            elif action == "REJECTED":
                sub.final_status = "REJECTED"
            elif action == "ESCALATE":
                # Dynamically resolve the correct L2 user
                target_l2 = self._resolve_escalation_target(sub, "L1", action_req.next_approver_id)
                sub.l2_approver_id = target_l2
                sub.final_status = "L2_PENDING"
                pending_with = compute_pending_with(sub)
                logger.info(
                    "Submission %s escalated from L1 to L2 (user #%s) by user #%s. Previously pending with: %s",
                    submission_id, target_l2, performed_by, pending_with,
                )
                self._notify(target_l2, sub, "L2")
                # Override action label for audit — use canonical ESCALATED
                action = "ESCALATED"
                action_req = type(action_req)(
                    action="ESCALATED",
                    comments=action_req.comments or f"Escalated to L2 (user #{target_l2})",
                    next_approver_id=target_l2,
                )

        elif level == "L2":
            sub.l2_action = action
            sub.l2_action_dt = now
            sub.l2_comments = action_req.comments
            if action == "APPROVED":
                l3_id = action_req.next_approver_id
                if not l3_id:
                    # Auto-resolve L3 approver via assignment rules
                    _mcs = self.status_repo.get_by_id(sub.status_id)
                    l3_id = self.assign_svc.resolve_approver(
                        role_code="L3_ADMIN",
                        kri_id=_mcs.kri_id if _mcs else None,
                    )
                if not l3_id:
                    # Last-resort: any active L3_ADMIN in the system
                    from app.models import UserRoleMapping as _URM
                    _fb = (
                        self.db.query(AppUser)
                        .join(_URM, _URM.user_id == AppUser.user_id)
                        .filter(_URM.role_code == "L3_ADMIN", _URM.is_active == True, AppUser.is_active == True)
                        .first()
                    )
                    if _fb:
                        l3_id = _fb.user_id
                if l3_id:
                    sub.l3_approver_id = l3_id
                    sub.final_status = "L3_PENDING"
                    self._notify(l3_id, sub, "L3")
                else:
                    sub.final_status = "APPROVED"
            elif action == "REWORK":
                sub.final_status = "REWORK"
            elif action == "REJECTED":
                sub.l2_action = "REJECTED"
                sub.l1_action = None
                sub.l1_action_dt = None
                sub.final_status = "L1_PENDING"
                if sub.l1_approver_id:
                    self._notify(sub.l1_approver_id, sub, "L1")
            elif action == "ESCALATE":
                # Dynamically resolve the correct L3 user
                target_l3 = self._resolve_escalation_target(sub, "L2", action_req.next_approver_id)
                sub.l3_approver_id = target_l3
                sub.final_status = "L3_PENDING"
                pending_with = compute_pending_with(sub)
                logger.info(
                    "Submission %s escalated from L2 to L3 (user #%s) by user #%s. Previously pending with: %s",
                    submission_id, target_l3, performed_by, pending_with,
                )
                self._notify(target_l3, sub, "L3")
                action = "ESCALATED"
                action_req = type(action_req)(
                    action="ESCALATED",
                    comments=action_req.comments or f"Escalated to L3 (user #{target_l3})",
                    next_approver_id=target_l3,
                )

        elif level == "L3":
            sub.l3_action = action
            sub.l3_action_dt = now
            sub.l3_comments = action_req.comments
            if action == "APPROVED":
                sub.final_status = "APPROVED"
            elif action == "REWORK":
                # Reset chain so L1 must re-approve after data is reworked
                sub.l3_action = "REWORK"
                sub.l2_action = None
                sub.l2_action_dt = None
                sub.l1_action = None
                sub.l1_action_dt = None
                sub.final_status = "L1_PENDING"
                if sub.l1_approver_id:
                    self._notify(sub.l1_approver_id, sub, "L1")
            elif action == "REJECTED":
                sub.l3_action = "REJECTED"
                sub.l2_action = None
                sub.l2_action_dt = None
                sub.l1_action = None
                sub.l1_action_dt = None
                sub.final_status = "L1_PENDING"
                if sub.l1_approver_id:
                    self._notify(sub.l1_approver_id, sub, "L1")
            elif action == "ESCALATE":
                # L3 escalation: re-assign within L3 to a different SYSTEM_ADMIN
                if not action_req.next_approver_id:
                    raise HTTPException(
                        422,
                        "L3 escalation requires an explicit next_approver_id (another SYSTEM_ADMIN or L3 user)."
                    )
                original_l3 = sub.l3_approver_id
                sub.l3_approver_id = action_req.next_approver_id
                sub.l3_action = None  # reset so new L3 can act
                sub.l3_action_dt = None
                sub.final_status = "L3_PENDING"
                logger.info(
                    "Submission %s re-assigned at L3 from user #%s to user #%s by user #%s",
                    submission_id, original_l3, action_req.next_approver_id, performed_by,
                )
                self._notify(action_req.next_approver_id, sub, "L3")
                action = "ESCALATED"
                action_req = type(action_req)(
                    action="ESCALATED",
                    comments=action_req.comments or f"Re-assigned at L3 from user #{original_l3} to user #{action_req.next_approver_id}",
                    next_approver_id=action_req.next_approver_id,
                )

        # ── Update monthly control status ────────────────────
        # All three writes below (status + audit + submission) are deferred and
        # committed together in mc_repo.update(), saving 2 Oracle round-trips.
        status_obj = self.status_repo.get_by_id(sub.status_id)
        if sub.final_status == "APPROVED":
            self.status_repo.update_status(status_obj, "COMPLETED", autocommit=False)
        elif sub.final_status == "REWORK":
            self.status_repo.update_status(status_obj, "REWORK", autocommit=False)
        elif sub.final_status == "REJECTED":
            self.status_repo.update_status(status_obj, "REJECTED", autocommit=False)
        elif sub.final_status == "L1_PENDING":
            self.status_repo.update_status(status_obj, "PENDING_APPROVAL", "L1", sub.l1_approver_id, autocommit=False)
        elif sub.final_status == "L2_PENDING":
            self.status_repo.update_status(status_obj, "PENDING_APPROVAL", "L2", sub.l2_approver_id, autocommit=False)
        elif sub.final_status == "L3_PENDING":
            self.status_repo.update_status(status_obj, "PENDING_APPROVAL", "L3", sub.l3_approver_id, autocommit=False)

        # ── Write audit trail entry ──────────────────────────
        if action == "ESCALATED":
            audit_action = "ESCALATED"
        else:
            audit_action = f"{level}_{action}"  # e.g. L1_APPROVED, L2_REWORK

        self.audit_repo.create({
            "status_id": sub.status_id,
            "action": audit_action,
            "performed_by": performed_by,
            "comments": action_req.comments,
            "previous_status": f"{level}_PENDING",
            "new_status": sub.final_status,
            "created_by": str(performed_by),
            "updated_by": str(performed_by),
        }, autocommit=False)

        # Single commit: flushes status update + audit trail + submission update together.
        return self.mc_repo.update(sub)

    def _notify(self, user_id: int, sub: MakerCheckerSubmission, level: str):
        self.notif_repo.create({
            "user_id": user_id,
            "title": f"{level} Approval Request",
            "message": f"Submission #{sub.submission_id} needs your {level} review.",
            "notification_type": "APPROVAL_REQUEST",
            "created_by": "SYSTEM",
            "updated_by": "SYSTEM",
        }, autocommit=False)


# ─── Variance Service ──────────────────────────────────────
class VarianceService:
    def __init__(self, db: Session):
        self.var_repo = VarianceRepository(db)
        self.metric_repo = MetricRepository(db)
        self.db = db

    def submit_variance(self, req: VarianceSubmitRequest, submitted_by: int):
        metric = self.db.query(MetricRepository).filter_by(metric_id=req.metric_id).first() if False else None
        # Just use metric_id from request
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
        self.status_repo = MonthlyStatusRepository(db)
        self.db = db

    def _check_freeze(self, kri_id: int, dimension_id: int, year: int, month: int):
        """Raise HTTP 423 if today is past the freeze date for this KRI/dimension/period."""
        from app.utils.sla import calculate_sla_dates
        from app.models import KriMaster, KriConfiguration, ControlDimensionMaster

        kri = self.db.query(KriMaster).filter(KriMaster.kri_id == kri_id).first()
        if not kri:
            return  # KRI not found — let the caller handle 404

        cfg = self.db.query(KriConfiguration).filter(
            KriConfiguration.kri_id == kri_id,
            KriConfiguration.dimension_id == dimension_id,
        ).first()

        dim = self.db.query(ControlDimensionMaster).filter(
            ControlDimensionMaster.dimension_id == dimension_id
        ).first()

        sla_start_day = cfg.sla_start_day if cfg else None
        sla_end_day   = cfg.sla_end_day   if cfg else None
        sla_days      = cfg.sla_days       if cfg else 3

        _, _, freeze_date = calculate_sla_dates(
            kri_is_dcrm=kri.is_dcrm,
            dimension_code=dim.dimension_code if dim else "",
            year=year,
            month=month,
            sla_start_day=sla_start_day,
            sla_end_day=sla_end_day,
            sla_days=sla_days,
        )

        today = date.today()
        if today > freeze_date:
            raise HTTPException(
                status_code=423,
                detail={
                    "error": "FREEZE_DATE_PASSED",
                    "message": f"Evidence upload is frozen. Freeze date was {freeze_date.isoformat()}.",
                    "freeze_date": freeze_date.isoformat(),
                },
            )

    def upload(self, kri_id: int, dimension_id: int, year: int, month: int,
               file_name: str, file_type: str, file_size: int,
               s3_bucket: str, s3_key: str, uploaded_by: int, region_id: int = None):
        """Create evidence record with status=DRAFT (temp S3 prefix).

        The record stays DRAFT until the caller invokes submit().
        """
        self._check_freeze(kri_id, dimension_id, year, month)

        # Use a temp/ prefix so S3 lifecycle rules can auto-expire abandoned uploads
        temp_s3_key = s3_key.replace("evidence/", "evidence/temp/", 1) if not s3_key.startswith("evidence/temp/") else s3_key

        ev = self.ev_repo.create({
            "kri_id": kri_id,
            "dimension_id": dimension_id,
            "period_year": year,
            "period_month": month,
            "file_name": file_name,
            "file_type": file_type,
            "file_size_bytes": file_size,
            "s3_bucket": s3_bucket,
            "s3_key": temp_s3_key,
            "region_id": region_id,
            "uploaded_by": uploaded_by,
            "evidence_status": "DRAFT",
            "created_by": str(uploaded_by),
            "updated_by": str(uploaded_by),
        })
        self.ev_repo.create_version({
            "evidence_id": ev.evidence_id,
            "version_number": 1,
            "s3_key": temp_s3_key,
            "file_size_bytes": file_size,
            "action": "UPLOAD",
            "performed_by": uploaded_by,
            "created_by": str(uploaded_by),
            "updated_by": str(uploaded_by),
        })
        return ev

    def submit(self, evidence_id: int, submitted_by: int,
               metric_value: float = None, short_comment: str = None,
               long_comment: str = None, rag_status: str = None):
        """Promote evidence from DRAFT → ACTIVE within a single transaction.

        Steps (all-or-nothing):
          1. Validate freeze date still holds
          2. Promote S3 key from temp/ → permanent prefix
          3. Set evidence_status = ACTIVE
          4. Update linked MonthlyControlStatus metric / rag / status
          5. Create EvidenceVersionAudit entry with metric, rag, comments
        """
        ev = self.ev_repo.get_by_id(evidence_id)
        if not ev:
            raise HTTPException(404, "Evidence not found")
        if ev.evidence_status == "ACTIVE":
            raise HTTPException(409, "Evidence is already active")
        if ev.evidence_status == "DELETED":
            raise HTTPException(410, "Evidence has been deleted")

        self._check_freeze(ev.kri_id, ev.dimension_id, ev.period_year, ev.period_month)

        # Promote S3 key: evidence/temp/... → evidence/...
        permanent_key = ev.s3_key.replace("evidence/temp/", "evidence/", 1)

        try:
            # Attempt S3 copy if a real bucket is configured
            s3_bucket = ev.s3_bucket
            if s3_bucket and s3_bucket not in ("local", ""):
                import boto3
                s3 = boto3.client("s3")
                s3.copy_object(
                    Bucket=s3_bucket,
                    CopySource={"Bucket": s3_bucket, "Key": ev.s3_key},
                    Key=permanent_key,
                )
                s3.delete_object(Bucket=s3_bucket, Key=ev.s3_key)

            # Compute RAG if metric value provided
            if metric_value is not None and rag_status is None:
                from app.utils import compute_rag
                from app.models import KriConfiguration
                cfg = self.db.query(KriConfiguration).filter(
                    KriConfiguration.kri_id == ev.kri_id,
                    KriConfiguration.dimension_id == ev.dimension_id,
                ).first()
                rag_status = compute_rag(
                    metric_value=metric_value,
                    rag_thresholds=cfg.rag_thresholds if cfg else None,
                    rag_green_max=cfg.rag_green_max if cfg else None,
                    rag_amber_max=cfg.rag_amber_max if cfg else None,
                )

            # Update evidence record
            ev.s3_key = permanent_key
            ev.evidence_status = "ACTIVE"
            ev.updated_by = str(submitted_by)

            # Create version audit entry
            next_version = (ev.version_number or 1) + 1
            ev.version_number = next_version
            self.ev_repo.create_version({
                "evidence_id": ev.evidence_id,
                "version_number": next_version,
                "s3_key": permanent_key,
                "file_size_bytes": ev.file_size_bytes,
                "action": "SUBMIT",
                "performed_by": submitted_by,
                "metric_value": metric_value,
                "rag_status": rag_status,
                "short_comment": short_comment,
                "long_comment": long_comment,
                "created_by": str(submitted_by),
                "updated_by": str(submitted_by),
            })

            # Update linked MonthlyControlStatus if metric provided
            if metric_value is not None:
                from app.models import MonthlyControlStatus, MetricValues
                mcs = self.db.query(MonthlyControlStatus).filter(
                    MonthlyControlStatus.kri_id == ev.kri_id,
                    MonthlyControlStatus.dimension_id == ev.dimension_id,
                    MonthlyControlStatus.period_year == ev.period_year,
                    MonthlyControlStatus.period_month == ev.period_month,
                ).first()
                if mcs:
                    mcs.rag_status = rag_status
                    mcs.updated_by = str(submitted_by)

                mv = self.db.query(MetricValues).filter(
                    MetricValues.kri_id == ev.kri_id,
                    MetricValues.dimension_id == ev.dimension_id,
                    MetricValues.period_year == ev.period_year,
                    MetricValues.period_month == ev.period_month,
                ).first()
                if mv:
                    mv.current_value = metric_value
                    mv.variance_status = rag_status
                    mv.updated_by = str(submitted_by)

            self.db.commit()
            self.db.refresh(ev)
            return ev

        except HTTPException:
            self.db.rollback()
            raise
        except Exception as e:
            self.db.rollback()
            raise HTTPException(500, f"Evidence submit failed: {e}")

    def generate_download_url(self, evidence_id: int, requesting_user_roles: list) -> dict:
        """Return a pre-signed S3 URL or a local path token for evidence download."""
        ev = self.ev_repo.get_by_id(evidence_id)
        if not ev:
            raise HTTPException(404, "Evidence not found")
        if ev.evidence_status == "DELETED":
            raise HTTPException(410, "Evidence has been deleted")

        allowed_roles = {"DOWNLOAD", "SYSTEM_ADMIN", "DATA_PROVIDER", "MANAGEMENT",
                         "L1_APPROVER", "L2_APPROVER", "L3_ADMIN", "METRIC_OWNER"}
        user_roles = {r.get("role_code") for r in requesting_user_roles}
        if not user_roles.intersection(allowed_roles):
            raise HTTPException(403, "Insufficient permissions to download evidence")

        s3_bucket = ev.s3_bucket
        if s3_bucket and s3_bucket not in ("local", ""):
            try:
                import boto3
                s3 = boto3.client("s3")
                url = s3.generate_presigned_url(
                    "get_object",
                    Params={"Bucket": s3_bucket, "Key": ev.s3_key},
                    ExpiresIn=900,  # 15 minutes
                )
                return {"url": url, "expires_in": 900, "file_name": ev.file_name}
            except Exception as e:
                raise HTTPException(500, f"Could not generate download URL: {e}")

        # Local storage fallback — return a token the frontend exchanges at /files/
        return {
            "url": f"/api/evidence/{evidence_id}/file",
            "expires_in": None,
            "file_name": ev.file_name,
            "local_path": ev.s3_key,
        }

    def lock_evidence(self, evidence_id: int, locked_by: str):
        ev = self.ev_repo.get_by_id(evidence_id)
        if not ev:
            raise HTTPException(404, "Evidence not found")
        self.ev_repo.lock(ev, locked_by)
        return ev
