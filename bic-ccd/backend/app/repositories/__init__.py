"""Repository layer — data access for all domain entities."""
from datetime import datetime, date
from typing import Optional, List, Tuple
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, and_, or_, desc, case
from app.models import (
    RegionMaster, KriCategoryMaster, ControlDimensionMaster,
    KriMaster, AppUser, UserRoleMapping, KriConfiguration,
    KriAssignment, DataSourceMapping, MonthlyControlStatus,
    MetricValues, ApprovalAuditTrail, EvidenceMetadata,
    EvidenceVersionAudit, MakerCheckerSubmission, VarianceSubmission,
    KriComment, EscalationConfig, EmailAudit, Notification, SavedView,
    ApprovalAssignmentRule,
)


# ─── Generic helpers ────────────────────────────────────────
def paginate(query, page: int, page_size: int):
    total = query.count()
    items = query.offset((page - 1) * page_size).limit(page_size).all()
    return items, total


# ─── Region ─────────────────────────────────────────────────
class RegionRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_all(self, active_only: bool = True) -> List[RegionMaster]:
        q = self.db.query(RegionMaster)
        if active_only:
            q = q.filter(RegionMaster.is_active == True)
        return q.order_by(RegionMaster.region_code).all()

    def get_by_id(self, region_id: int) -> Optional[RegionMaster]:
        return self.db.query(RegionMaster).filter(RegionMaster.region_id == region_id).first()

    def create(self, data: dict) -> RegionMaster:
        obj = RegionMaster(**data)
        self.db.add(obj)
        self.db.commit()
        self.db.refresh(obj)
        return obj


# ─── Category ───────────────────────────────────────────────
class CategoryRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_all(self, active_only: bool = True) -> List[KriCategoryMaster]:
        q = self.db.query(KriCategoryMaster)
        if active_only:
            q = q.filter(KriCategoryMaster.is_active == True)
        return q.order_by(KriCategoryMaster.category_name).all()

    def get_by_id(self, cat_id: int) -> Optional[KriCategoryMaster]:
        return self.db.query(KriCategoryMaster).filter(KriCategoryMaster.category_id == cat_id).first()

    def create(self, data: dict) -> KriCategoryMaster:
        obj = KriCategoryMaster(**data)
        self.db.add(obj)
        self.db.commit()
        self.db.refresh(obj)
        return obj


# ─── Dimension ──────────────────────────────────────────────
class DimensionRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_all(self, active_only: bool = True) -> List[ControlDimensionMaster]:
        q = self.db.query(ControlDimensionMaster)
        if active_only:
            q = q.filter(ControlDimensionMaster.is_active == True)
        return q.order_by(ControlDimensionMaster.display_order).all()


# ─── User ───────────────────────────────────────────────────
class UserRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_soe_id(self, soe_id: str) -> Optional[AppUser]:
        return self.db.query(AppUser).filter(AppUser.soe_id == soe_id).first()

    def get_by_id(self, user_id: int) -> Optional[AppUser]:
        return self.db.query(AppUser).options(joinedload(AppUser.roles)).filter(AppUser.user_id == user_id).first()

    def get_all(self, page: int = 1, page_size: int = 50) -> Tuple[List[AppUser], int]:
        q = self.db.query(AppUser).order_by(AppUser.full_name)
        return paginate(q, page, page_size)

    def create(self, data: dict) -> AppUser:
        obj = AppUser(**data)
        self.db.add(obj)
        self.db.commit()
        self.db.refresh(obj)
        return obj

    def update(self, user: AppUser, data: dict) -> AppUser:
        for k, v in data.items():
            if v is not None:
                setattr(user, k, v)
        user.updated_dt = datetime.utcnow()
        self.db.commit()
        self.db.refresh(user)
        return user

    def get_roles(self, user_id: int) -> List[UserRoleMapping]:
        return self.db.query(UserRoleMapping).filter(
            UserRoleMapping.user_id == user_id,
            UserRoleMapping.is_active == True
        ).all()

    def assign_role(self, data: dict) -> UserRoleMapping:
        """
        Assign a role to user. Enforces single role per user:
        - Deactivates previous active roles
        - Creates new active role
        - Returns the new role assignment
        """
        user_id = data.get("user_id")
        
        # Deactivate all previous active roles for this user
        previous_roles = self.db.query(UserRoleMapping).filter(
            UserRoleMapping.user_id == user_id,
            UserRoleMapping.is_active == True
        ).all()
        
        for prev_role in previous_roles:
            prev_role.is_active = False
            prev_role.updated_dt = datetime.utcnow()
        
        # Create new role assignment
        obj = UserRoleMapping(**data)
        self.db.add(obj)
        self.db.commit()
        self.db.refresh(obj)
        
        return obj

    def get_users_by_role(self, role_code: str, region_id: int = None) -> List[AppUser]:
        q = self.db.query(AppUser).join(UserRoleMapping).filter(
            UserRoleMapping.role_code == role_code,
            UserRoleMapping.is_active == True,
            AppUser.is_active == True
        )
        if region_id:
            q = q.filter(UserRoleMapping.region_id == region_id)
        return q.all()


# ─── KRI ────────────────────────────────────────────────────
class KriRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_all(self, region_id: int = None, category_id: int = None,
                active_only: bool = True, page: int = 1, page_size: int = 50):
        q = self.db.query(KriMaster)
        if active_only:
            q = q.filter(KriMaster.is_active == True)
        if region_id:
            q = q.filter(KriMaster.region_id == region_id)
        if category_id:
            q = q.filter(KriMaster.category_id == category_id)
        q = q.order_by(KriMaster.kri_code)
        return paginate(q, page, page_size)

    def get_by_id(self, kri_id: int) -> Optional[KriMaster]:
        return self.db.query(KriMaster).options(
            joinedload(KriMaster.category),
            joinedload(KriMaster.region),
            joinedload(KriMaster.configurations)
        ).filter(KriMaster.kri_id == kri_id).first()

    def get_by_code(self, code: str) -> Optional[KriMaster]:
        return self.db.query(KriMaster).filter(KriMaster.kri_code == code).first()

    def create(self, data: dict) -> KriMaster:
        obj = KriMaster(**data)
        self.db.add(obj)
        self.db.commit()
        self.db.refresh(obj)
        return obj

    def update(self, kri: KriMaster, data: dict) -> KriMaster:
        for k, v in data.items():
            if v is not None:
                setattr(kri, k, v)
        kri.updated_dt = datetime.utcnow()
        self.db.commit()
        self.db.refresh(kri)
        return kri

    def count_by_region(self) -> dict:
        rows = self.db.query(
            RegionMaster.region_code, func.count(KriMaster.kri_id)
        ).join(KriMaster).filter(KriMaster.is_active == True).group_by(RegionMaster.region_code).all()
        return {r[0]: r[1] for r in rows}


# ─── KRI Configuration ─────────────────────────────────────
class KriConfigRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_for_kri(self, kri_id: int) -> List[KriConfiguration]:
        return self.db.query(KriConfiguration).filter(
            KriConfiguration.kri_id == kri_id,
            KriConfiguration.is_active == True
        ).all()

    def create(self, data: dict) -> KriConfiguration:
        obj = KriConfiguration(**data)
        self.db.add(obj)
        self.db.commit()
        self.db.refresh(obj)
        return obj

    def update(self, config: KriConfiguration, data: dict) -> KriConfiguration:
        for k, v in data.items():
            if v is not None:
                setattr(config, k, v)
        self.db.commit()
        self.db.refresh(config)
        return config


# ─── Monthly Control Status ─────────────────────────────────
class MonthlyStatusRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_for_period(self, year: int, month: int, region_id: int = None,
                       dimension_id: int = None, status: str = None,
                       page: int = 1, page_size: int = 100):
        q = self.db.query(MonthlyControlStatus).join(
            KriMaster, MonthlyControlStatus.kri_id == KriMaster.kri_id
        )
        q = q.filter(
            MonthlyControlStatus.period_year == year,
            MonthlyControlStatus.period_month == month
        )
        if region_id:
            q = q.filter(KriMaster.region_id == region_id)
        if dimension_id:
            q = q.filter(MonthlyControlStatus.dimension_id == dimension_id)
        if status:
            q = q.filter(MonthlyControlStatus.status == status)
        q = q.order_by(KriMaster.kri_code)
        return paginate(q, page, page_size)

    def get_by_id(self, status_id: int) -> Optional[MonthlyControlStatus]:
        return self.db.query(MonthlyControlStatus).filter(
            MonthlyControlStatus.status_id == status_id
        ).first()

    def create(self, data: dict) -> MonthlyControlStatus:
        obj = MonthlyControlStatus(**data)
        self.db.add(obj)
        self.db.commit()
        self.db.refresh(obj)
        return obj

    def update_status(self, obj: MonthlyControlStatus, new_status: str,
                      approval_level: str = None, approver_id: int = None):
        obj.status = new_status
        if approval_level:
            obj.approval_level = approval_level
        if approver_id:
            obj.current_approver = approver_id
        obj.updated_dt = datetime.utcnow()
        if new_status in ("COMPLETED", "APPROVED"):
            obj.completed_dt = datetime.utcnow()
            obj.sla_met = obj.sla_due_dt and datetime.utcnow() <= obj.sla_due_dt
        self.db.commit()
        self.db.refresh(obj)
        return obj

    def get_summary_counts(self, year: int, month: int, region_id: int = None) -> dict:
        q = self.db.query(
            MonthlyControlStatus.status,
            func.count(MonthlyControlStatus.status_id)
        ).join(KriMaster).filter(
            MonthlyControlStatus.period_year == year,
            MonthlyControlStatus.period_month == month
        )
        if region_id:
            q = q.filter(KriMaster.region_id == region_id)
        q = q.group_by(MonthlyControlStatus.status)
        return {row[0]: row[1] for row in q.all()}

    def get_rag_counts(self, year: int, month: int, region_id: int = None) -> dict:
        q = self.db.query(
            MonthlyControlStatus.rag_status,
            func.count(MonthlyControlStatus.status_id)
        ).join(KriMaster).filter(
            MonthlyControlStatus.period_year == year,
            MonthlyControlStatus.period_month == month
        )
        if region_id:
            q = q.filter(KriMaster.region_id == region_id)
        q = q.group_by(MonthlyControlStatus.rag_status)
        return {row[0]: row[1] for row in q.all()}

    def get_trend_data(self, months: int = 6, region_id: int = None) -> List[dict]:
        """Return status counts per month for last N months."""
        now = datetime.utcnow()
        results = []
        for i in range(months - 1, -1, -1):
            m = now.month - i
            y = now.year
            while m <= 0:
                m += 12
                y -= 1
            counts = self.get_summary_counts(y, m, region_id)
            sla_met = counts.get("COMPLETED", 0) + counts.get("APPROVED", 0)
            breached = counts.get("SLA_BREACHED", 0)
            not_started = counts.get("NOT_STARTED", 0)
            results.append({
                "period": f"{datetime(y, m, 1):%b %y}",
                "sla_met": sla_met,
                "sla_breached": breached,
                "not_started": not_started
            })
        return results

    def get_dimension_breakdown(self, year: int, month: int, region_id: int = None) -> List[dict]:
        q = self.db.query(
            ControlDimensionMaster.dimension_name,
            MonthlyControlStatus.status,
            func.count(MonthlyControlStatus.status_id)
        ).join(
            ControlDimensionMaster,
            MonthlyControlStatus.dimension_id == ControlDimensionMaster.dimension_id
        ).join(KriMaster).filter(
            MonthlyControlStatus.period_year == year,
            MonthlyControlStatus.period_month == month
        )
        if region_id:
            q = q.filter(KriMaster.region_id == region_id)
        q = q.group_by(ControlDimensionMaster.dimension_name, MonthlyControlStatus.status)
        rows = q.all()

        dims = {}
        for dim_name, status, cnt in rows:
            if dim_name not in dims:
                dims[dim_name] = {"dimension_name": dim_name, "sla_met": 0, "breached": 0, "not_started": 0}
            if status in ("COMPLETED", "APPROVED"):
                dims[dim_name]["sla_met"] += cnt
            elif status == "SLA_BREACHED":
                dims[dim_name]["breached"] += cnt
            elif status == "NOT_STARTED":
                dims[dim_name]["not_started"] += cnt
        return list(dims.values())

    def get_pending_approvals(self, approver_id: int = None, page: int = 1, page_size: int = 50):
        q = self.db.query(MonthlyControlStatus).filter(
            MonthlyControlStatus.status == "PENDING_APPROVAL"
        )
        if approver_id:
            q = q.filter(MonthlyControlStatus.current_approver == approver_id)
        return paginate(q, page, page_size)


# ─── Approval Audit ─────────────────────────────────────────
class ApprovalAuditRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, data: dict) -> ApprovalAuditTrail:
        obj = ApprovalAuditTrail(**data)
        self.db.add(obj)
        self.db.commit()
        self.db.refresh(obj)
        return obj

    def get_for_status(self, status_id: int) -> List[ApprovalAuditTrail]:
        return self.db.query(ApprovalAuditTrail).filter(
            ApprovalAuditTrail.status_id == status_id
        ).order_by(desc(ApprovalAuditTrail.performed_dt)).all()


# ─── Evidence ───────────────────────────────────────────────
class EvidenceRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_for_kri_period(self, kri_id: int, year: int, month: int) -> List[EvidenceMetadata]:
        return self.db.query(EvidenceMetadata).filter(
            EvidenceMetadata.kri_id == kri_id,
            EvidenceMetadata.period_year == year,
            EvidenceMetadata.period_month == month
        ).order_by(desc(EvidenceMetadata.uploaded_dt)).all()

    def get_all(self, year: int = None, month: int = None, region_id: int = None,
                page: int = 1, page_size: int = 50):
        q = self.db.query(EvidenceMetadata).join(KriMaster)
        if year:
            q = q.filter(EvidenceMetadata.period_year == year)
        if month:
            q = q.filter(EvidenceMetadata.period_month == month)
        if region_id:
            q = q.filter(KriMaster.region_id == region_id)
        q = q.order_by(desc(EvidenceMetadata.uploaded_dt))
        return paginate(q, page, page_size)

    def create(self, data: dict) -> EvidenceMetadata:
        obj = EvidenceMetadata(**data)
        self.db.add(obj)
        self.db.commit()
        self.db.refresh(obj)
        return obj

    def get_by_id(self, eid: int) -> Optional[EvidenceMetadata]:
        return self.db.query(EvidenceMetadata).filter(EvidenceMetadata.evidence_id == eid).first()

    def lock(self, evidence: EvidenceMetadata, locked_by: str):
        evidence.is_locked = True
        evidence.locked_dt = datetime.utcnow()
        evidence.locked_by = locked_by
        self.db.commit()

    def create_version(self, data: dict) -> EvidenceVersionAudit:
        obj = EvidenceVersionAudit(**data)
        self.db.add(obj)
        self.db.commit()
        return obj

    def get_completeness(self, year: int, month: int) -> dict:
        total_kris = self.db.query(func.count(KriMaster.kri_id)).filter(KriMaster.is_active == True).scalar()
        with_evidence = self.db.query(func.count(func.distinct(EvidenceMetadata.kri_id))).filter(
            EvidenceMetadata.period_year == year,
            EvidenceMetadata.period_month == month
        ).scalar()
        return {"total": total_kris or 0, "with_evidence": with_evidence or 0}


# ─── Maker Checker ──────────────────────────────────────────
class MakerCheckerRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, data: dict) -> MakerCheckerSubmission:
        obj = MakerCheckerSubmission(**data)
        self.db.add(obj)
        self.db.commit()
        self.db.refresh(obj)
        return obj

    def get_by_id(self, sid: int) -> Optional[MakerCheckerSubmission]:
        return self.db.query(MakerCheckerSubmission).filter(
            MakerCheckerSubmission.submission_id == sid
        ).first()

    def get_pending_for_approver(self, user_id: int, level: str = "L1",
                                  page: int = 1, page_size: int = 50):
        """Return pending items for this approver.
        Pool-based: shows submissions assigned to this user OR unassigned (NULL approver_id).
        """
        q = self.db.query(MakerCheckerSubmission).options(
            joinedload(MakerCheckerSubmission.control_status).joinedload(MonthlyControlStatus.kri),
            joinedload(MakerCheckerSubmission.submitter),
        )
        if level == "L1":
            q = q.filter(
                or_(
                    MakerCheckerSubmission.l1_approver_id == user_id,
                    MakerCheckerSubmission.l1_approver_id == None,
                ),
                MakerCheckerSubmission.final_status == "L1_PENDING"
            )
        elif level == "L2":
            q = q.filter(
                or_(
                    MakerCheckerSubmission.l2_approver_id == user_id,
                    MakerCheckerSubmission.l2_approver_id == None,
                ),
                MakerCheckerSubmission.final_status == "L2_PENDING"
            )
        elif level == "L3":
            q = q.filter(
                or_(
                    MakerCheckerSubmission.l3_approver_id == user_id,
                    MakerCheckerSubmission.l3_approver_id == None,
                ),
                MakerCheckerSubmission.final_status == "L3_PENDING"
            )
        return paginate(q, page, page_size)

    def get_all_pending(self, level: str = None, page: int = 1, page_size: int = 50):
        """L3 Admin view: see ALL pending items across all levels."""
        q = self.db.query(MakerCheckerSubmission).options(
            joinedload(MakerCheckerSubmission.control_status).joinedload(MonthlyControlStatus.kri),
            joinedload(MakerCheckerSubmission.submitter),
        ).filter(
            MakerCheckerSubmission.final_status.in_(["L1_PENDING", "L2_PENDING", "L3_PENDING", "PENDING"])
        )
        if level:
            q = q.filter(MakerCheckerSubmission.final_status == f"{level}_PENDING")
        q = q.order_by(desc(MakerCheckerSubmission.submitted_dt))
        return paginate(q, page, page_size)

    def get_queue_summary(self) -> dict:
        """L3 Admin dashboard: count items per approval level."""
        from sqlalchemy import case
        counts = self.db.query(
            MakerCheckerSubmission.final_status,
            func.count(MakerCheckerSubmission.submission_id)
        ).filter(
            MakerCheckerSubmission.final_status.in_(["L1_PENDING", "L2_PENDING", "L3_PENDING"])
        ).group_by(MakerCheckerSubmission.final_status).all()
        return {status: count for status, count in counts}

    def get_history(self, user_id: int, year: int = None, month: int = None,
                    page: int = 1, page_size: int = 50):
        """Return completed/approved/rejected submissions where user was involved."""
        q = self.db.query(MakerCheckerSubmission).options(
            joinedload(MakerCheckerSubmission.control_status).joinedload(MonthlyControlStatus.kri),
            joinedload(MakerCheckerSubmission.submitter),
        ).filter(
            MakerCheckerSubmission.final_status.in_(["APPROVED", "REJECTED", "REWORK"]),
            or_(
                MakerCheckerSubmission.submitted_by == user_id,
                MakerCheckerSubmission.l1_approver_id == user_id,
                MakerCheckerSubmission.l2_approver_id == user_id,
                MakerCheckerSubmission.l3_approver_id == user_id,
            )
        )
        if year and month:
            q = q.filter(
                MakerCheckerSubmission.control_status.has(
                    and_(MonthlyControlStatus.period_year == year,
                         MonthlyControlStatus.period_month == month)
                )
            )
        q = q.order_by(desc(MakerCheckerSubmission.submitted_dt))
        return paginate(q, page, page_size)

    def get_history_admin(self, year: int = None, month: int = None,
                          page: int = 1, page_size: int = 50):
        """Admin view: all completed submissions."""
        q = self.db.query(MakerCheckerSubmission).options(
            joinedload(MakerCheckerSubmission.control_status).joinedload(MonthlyControlStatus.kri),
            joinedload(MakerCheckerSubmission.submitter),
        ).filter(
            MakerCheckerSubmission.final_status.in_(["APPROVED", "REJECTED", "REWORK"])
        )
        if year and month:
            q = q.filter(
                MakerCheckerSubmission.control_status.has(
                    and_(MonthlyControlStatus.period_year == year,
                         MonthlyControlStatus.period_month == month)
                )
            )
        q = q.order_by(desc(MakerCheckerSubmission.submitted_dt))
        return paginate(q, page, page_size)

    def update(self, sub: MakerCheckerSubmission) -> MakerCheckerSubmission:
        sub.updated_dt = datetime.utcnow()
        self.db.commit()
        self.db.refresh(sub)
        return sub


# ─── Variance ───────────────────────────────────────────────
class VarianceRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, data: dict) -> VarianceSubmission:
        obj = VarianceSubmission(**data)
        self.db.add(obj)
        self.db.commit()
        self.db.refresh(obj)
        return obj

    def get_pending(self, page: int = 1, page_size: int = 50):
        q = self.db.query(VarianceSubmission).filter(
            VarianceSubmission.review_status == "PENDING"
        ).order_by(desc(VarianceSubmission.submitted_dt))
        return paginate(q, page, page_size)

    def get_by_id(self, vid: int) -> Optional[VarianceSubmission]:
        return self.db.query(VarianceSubmission).filter(
            VarianceSubmission.variance_id == vid
        ).first()


# ─── Metric Values ──────────────────────────────────────────
class MetricRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_for_kri_period(self, kri_id: int, year: int, month: int) -> List[MetricValues]:
        return self.db.query(MetricValues).filter(
            MetricValues.kri_id == kri_id,
            MetricValues.period_year == year,
            MetricValues.period_month == month
        ).all()

    def create(self, data: dict) -> MetricValues:
        obj = MetricValues(**data)
        self.db.add(obj)
        self.db.commit()
        self.db.refresh(obj)
        return obj


# ─── Escalation Config ──────────────────────────────────────
class EscalationRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_all(self) -> List[EscalationConfig]:
        return self.db.query(EscalationConfig).filter(EscalationConfig.is_active == True).all()

    def get_by_id(self, config_id: int) -> Optional[EscalationConfig]:
        return self.db.query(EscalationConfig).filter(EscalationConfig.config_id == config_id).first()

    def create(self, data: dict) -> EscalationConfig:
        obj = EscalationConfig(**data)
        self.db.add(obj)
        self.db.commit()
        self.db.refresh(obj)
        return obj

    def update(self, config: EscalationConfig, data: dict) -> EscalationConfig:
        for k, v in data.items():
            if v is not None:
                setattr(config, k, v)
        self.db.commit()
        self.db.refresh(config)
        return config


# ─── Notification ───────────────────────────────────────────
class NotificationRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, data: dict) -> Notification:
        obj = Notification(**data)
        self.db.add(obj)
        self.db.commit()
        return obj

    def get_for_user(self, user_id: int, unread_only: bool = False, limit: int = 20):
        q = self.db.query(Notification).filter(Notification.user_id == user_id)
        if unread_only:
            q = q.filter(Notification.is_read == False)
        return q.order_by(desc(Notification.created_dt)).limit(limit).all()

    def mark_read(self, notification_id: int):
        n = self.db.query(Notification).filter(Notification.notification_id == notification_id).first()
        if n:
            n.is_read = True
            self.db.commit()

    def unread_count(self, user_id: int) -> int:
        return self.db.query(func.count(Notification.notification_id)).filter(
            Notification.user_id == user_id,
            Notification.is_read == False
        ).scalar() or 0


# ─── Comment ────────────────────────────────────────────────
class CommentRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, data: dict) -> KriComment:
        obj = KriComment(**data)
        self.db.add(obj)
        self.db.commit()
        self.db.refresh(obj)
        return obj

    def get_for_kri(self, kri_id: int) -> List[KriComment]:
        return self.db.query(KriComment).filter(
            KriComment.kri_id == kri_id
        ).order_by(desc(KriComment.posted_dt)).all()

    def get_for_status(self, status_id: int) -> List[KriComment]:
        return self.db.query(KriComment).filter(
            KriComment.status_id == status_id
        ).order_by(desc(KriComment.posted_dt)).all()


# ─── Data Source ────────────────────────────────────────────
class DataSourceRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_for_kri(self, kri_id: int) -> List[DataSourceMapping]:
        return self.db.query(DataSourceMapping).filter(
            DataSourceMapping.kri_id == kri_id,
            DataSourceMapping.is_active == True
        ).all()

    def create(self, data: dict) -> DataSourceMapping:
        obj = DataSourceMapping(**data)
        self.db.add(obj)
        self.db.commit()
        self.db.refresh(obj)
        return obj


# ─── KRI Assignment ─────────────────────────────────────────
class AssignmentRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_for_kri(self, kri_id: int) -> List[KriAssignment]:
        return self.db.query(KriAssignment).filter(
            KriAssignment.kri_id == kri_id,
            KriAssignment.is_active == True
        ).all()

    def create(self, data: dict) -> KriAssignment:
        obj = KriAssignment(**data)
        self.db.add(obj)
        self.db.commit()
        self.db.refresh(obj)
        return obj


# ─── Approver Assignment Rule ───────────────────────────────
class ApproverRuleRepository:
    """Queries ApprovalAssignmentRule with priority-based resolution.

    Resolution order (lower priority number = higher precedence):
      kri_id match → category_id match → region_id match → global (all None)
    """
    def __init__(self, db: Session):
        self.db = db

    def resolve(self, role_code: str, kri_id: int = None,
                region_id: int = None, category_id: int = None) -> Optional[int]:
        """Return the user_id of the best matching approver rule, or None."""
        rules = self.db.query(ApprovalAssignmentRule).filter(
            ApprovalAssignmentRule.role_code == role_code,
            ApprovalAssignmentRule.is_active == True,
        ).order_by(ApprovalAssignmentRule.priority).all()

        # Specificity tiers: kri > category > region > global
        for tier in [
            lambda r: r.kri_id == kri_id and kri_id is not None,
            lambda r: r.kri_id is None and r.category_id == category_id and category_id is not None,
            lambda r: r.kri_id is None and r.category_id is None and r.region_id == region_id and region_id is not None,
            lambda r: r.kri_id is None and r.category_id is None and r.region_id is None,
        ]:
            match = next((r for r in rules if tier(r) and r.user_id is not None), None)
            if match:
                return match.user_id
        return None

    def get_all(self, active_only: bool = True) -> List[ApprovalAssignmentRule]:
        q = self.db.query(ApprovalAssignmentRule)
        if active_only:
            q = q.filter(ApprovalAssignmentRule.is_active == True)
        return q.order_by(ApprovalAssignmentRule.priority).all()

    def create(self, data: dict) -> ApprovalAssignmentRule:
        obj = ApprovalAssignmentRule(**data)
        self.db.add(obj)
        self.db.commit()
        self.db.refresh(obj)
        return obj

    def update(self, rule: ApprovalAssignmentRule, data: dict) -> ApprovalAssignmentRule:
        for k, v in data.items():
            setattr(rule, k, v)
        rule.updated_dt = datetime.utcnow()
        self.db.commit()
        self.db.refresh(rule)
        return rule

    def get_by_id(self, rule_id: int) -> Optional[ApprovalAssignmentRule]:
        return self.db.query(ApprovalAssignmentRule).filter(
            ApprovalAssignmentRule.rule_id == rule_id
        ).first()

    def deactivate(self, rule: ApprovalAssignmentRule) -> ApprovalAssignmentRule:
        rule.is_active = False
        rule.updated_dt = datetime.utcnow()
        self.db.commit()
        return rule


# ─── Saved View ─────────────────────────────────────────────
class SavedViewRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_for_user(self, user_id: int, view_type: str = None) -> List[SavedView]:
        q = self.db.query(SavedView).filter(SavedView.user_id == user_id)
        if view_type:
            q = q.filter(SavedView.view_type == view_type)
        return q.all()

    def create(self, data: dict) -> SavedView:
        obj = SavedView(**data)
        self.db.add(obj)
        self.db.commit()
        self.db.refresh(obj)
        return obj
