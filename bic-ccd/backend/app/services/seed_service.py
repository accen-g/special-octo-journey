"""Seed service — inserts demo/mock data on first startup.

Controlled exclusively via SEED_MOCK_DATA env var (see config.py).
Every section is idempotent: checks for existing rows before inserting.
Safe to call multiple times; safe to call on a partially-seeded DB.
"""
import logging
from datetime import datetime, date, timedelta

from app.database import SessionLocal
from app.models import (
    RegionMaster, KriCategoryMaster, ControlDimensionMaster,
    AppUser, UserRoleMapping, KriMaster, KriConfiguration,
    MonthlyControlStatus, MetricValues, KriAssignment,
    MakerCheckerSubmission, ApprovalAuditTrail, KriStatusLookup,
)

logger = logging.getLogger("bic_ccd.seed")


def seed_database() -> None:
    """Insert demo data if the DB is empty (idempotent).

    Oracle-safe: each phase commits independently so FK constraints are
    satisfied even when previous runs left partial data.
    """
    db = SessionLocal()
    try:
        # Guard: if MonthlyControlStatus has rows the full seed already ran.
        if db.query(MonthlyControlStatus).count() > 0:
            logger.info("Database already seeded — skipping.")
            return

        logger.info("Starting BIC_CCD incremental seed...")

        # ── KRI Status lookup ───────────────────────────────
        existing_statuses = {r.status_name for r in db.query(KriStatusLookup).all()}
        for sname in [
            "NOT_STARTED", "IN_PROGRESS", "PENDING_APPROVAL", "APPROVED",
            "REWORK", "SLA_BREACHED", "COMPLETED", "SLA_MET",
            "RECEIVED_POST_BREACH", "REJECTED", "RECEIVED", "NOT_RECEIVED",
            "INSUFFICIENT_MAPPING", "DRAFT", "ACTIVE", "DELETED",
        ]:
            if sname not in existing_statuses:
                db.add(KriStatusLookup(status_name=sname))
        db.flush()

        # ── Regions ─────────────────────────────────────────
        regions = []
        all_existing_regions = db.query(RegionMaster).all()
        existing_by_code = {r.region_code: r for r in all_existing_regions if r.region_code}
        existing_by_name = {r.region_name: r for r in all_existing_regions}
        regions_to_add = []
        for code, name in [("UK", "United Kingdom"), ("SGP", "Singapore"), ("CEP", "Central Europe")]:
            if code in existing_by_code:
                regions.append(existing_by_code[code])
            elif name in existing_by_name:
                r = existing_by_name[name]
                if not r.region_code:
                    r.region_code = code
                regions.append(r)
            else:
                r = RegionMaster(region_code=code, region_name=name, created_by="SYSTEM", updated_by="SYSTEM")
                db.add(r)
                regions_to_add.append(r)
                regions.append(r)
        if regions_to_add:
            db.commit()
            logger.info("Seeded %d new regions.", len(regions_to_add))
            for r in regions_to_add:
                db.refresh(r)
        else:
            db.flush()

        # ── Categories ──────────────────────────────────────
        categories = []
        existing_cats = {c.category_code: c for c in db.query(KriCategoryMaster).all()}
        for code, name in [
            ("MARKET_RISK", "Market Risk"), ("CREDIT_RISK", "Credit Risk"),
            ("OPS_RISK", "Operational Risk"), ("LIQ_RISK", "Liquidity Risk"),
            ("REGULATORY", "Regulatory Compliance"),
        ]:
            if code in existing_cats:
                categories.append(existing_cats[code])
            else:
                c = KriCategoryMaster(category_code=code, category_name=name, created_by="SYSTEM", updated_by="SYSTEM")
                db.add(c)
                categories.append(c)
        db.flush()

        # ── Control Dimensions ──────────────────────────────
        dimensions = []
        existing_dims = {d.dimension_code: d for d in db.query(ControlDimensionMaster).all()}
        for i, (code, name) in enumerate([
            ("DATA_PROVIDER_SLA",    "Data Provider SLA"),
            ("COMPLETENESS_ACCURACY","Completeness & Accuracy"),
            ("MATERIAL_PREPARER",    "Material Preparer"),
            ("VARIANCE_ANALYSIS",    "Variance Analysis"),
            ("REVIEWS",              "Reviews"),
            ("ADJ_TRACKING",         "Adjustments Tracking"),
            ("CHANGE_GOVERNANCE",    "Change Governance"),
        ], 1):
            if code in existing_dims:
                dimensions.append(existing_dims[code])
            else:
                d = ControlDimensionMaster(dimension_code=code, dimension_name=name,
                                           display_order=i, created_by="SYSTEM", updated_by="SYSTEM")
                db.add(d)
                dimensions.append(d)
        db.flush()

        # ── Users ───────────────────────────────────────────
        users_data = [
            ("SA41230",  "Shahzad Alam",         "sa41230@company.com",  "Risk Mgmt",  "MANAGEMENT"),
            ("VR31849",  "Vivek Avireddy",        "vr31849@company.com",  "Controls",   "L1_APPROVER"),
            ("HK51214",  "Hasmukh Katechiya",     "hk51214@company.com",  "Controls",   "L2_APPROVER"),
            ("DH71298",  "Dawn Higgs",            "dh71298@company.com",  "Controls",   "L3_ADMIN"),
            ("GD24043",  "Gayatri Deshmukh",      "gd24043@company.com",  "Data Ops",   "DATA_PROVIDER"),
            ("PT81286",  "Paul Thirtle",          "pt81286@company.com",  "Metrics",    "METRIC_OWNER"),
            ("SYSADMIN", "System Admin",          "admin@company.com",    "IT",         "SYSTEM_ADMIN"),
        ]
        existing_users = {u.soe_id: u for u in db.query(AppUser).all()}
        users = []
        for soe, name, email, dept, role in users_data:
            if soe in existing_users:
                users.append((existing_users[soe], role))
            else:
                u = AppUser(soe_id=soe, full_name=name, email=email, department=dept,
                            created_by="SYSTEM", updated_by="SYSTEM")
                db.add(u)
                users.append((u, role))
        db.flush()

        # ── Role mappings ────────────────────────────────────
        existing_role_keys = {
            (r.user_id, r.role_code, r.region_id)
            for r in db.query(UserRoleMapping).all()
        }
        for user, role in users:
            for region in regions:
                if (user.user_id, role, region.region_id) not in existing_role_keys:
                    db.add(UserRoleMapping(
                        user_id=user.user_id, role_code=role, region_id=region.region_id,
                        effective_from=date(2024, 1, 1), created_by="SYSTEM", updated_by="SYSTEM"
                    ))
        db.flush()

        # ── KRIs — 8 per region ──────────────────────────────
        kri_names = [
            ("VaR Limit",        "MARKET_RISK"),  ("Credit Exposure",  "CREDIT_RISK"),
            ("OpRisk Events",    "OPS_RISK"),      ("Liquidity Buffer", "LIQ_RISK"),
            ("Reg Capital Ratio","REGULATORY"),    ("Stress Test P&L",  "MARKET_RISK"),
            ("Default Rate",     "CREDIT_RISK"),   ("IT Incident Count","OPS_RISK"),
        ]
        existing_kri_codes = {k.kri_code for k in db.query(KriMaster).all()}
        all_kris = list(db.query(KriMaster).all())
        kri_num = 0
        for region in regions:
            for kri_name, cat_code in kri_names:
                kri_num += 1
                kri_code = f"KRI-{region.region_code}-{kri_num:03d}"
                if kri_code in existing_kri_codes:
                    continue
                cat = next(c for c in categories if c.category_code == cat_code)
                risk = ["LOW", "MEDIUM", "HIGH", "CRITICAL"][kri_num % 4]
                k = KriMaster(
                    kri_code=kri_code,
                    kri_name=f"{kri_name} ({region.region_code})",
                    kri_title=kri_name,
                    description=f"Key Risk Indicator for {kri_name} in {region.region_name}",
                    category_id=cat.category_id, region_id=region.region_id,
                    risk_level=risk, framework="Active Framework", is_dcrm=False,
                    onboarded_dt=datetime(2024, 6, 1), created_by="SYSTEM", updated_by="SYSTEM"
                )
                db.add(k)
                all_kris.append(k)
        db.flush()

        # ── KRI Configurations ───────────────────────────────
        existing_cfg_keys = {(c.kri_id, c.dimension_id) for c in db.query(KriConfiguration).all()}
        for kri in all_kris:
            for dim in dimensions:
                if (kri.kri_id, dim.dimension_id) in existing_cfg_keys:
                    continue
                db.add(KriConfiguration(
                    kri_id=kri.kri_id, dimension_id=dim.dimension_id,
                    sla_days=3, variance_threshold=10.0,
                    requires_evidence=True, requires_approval=True,
                    freeze_day=15, created_by="SYSTEM", updated_by="SYSTEM"
                ))
        db.flush()

        # ── Monthly Control Statuses — last 6 months ─────────
        import random
        random.seed(42)
        statuses_pool = ["COMPLETED", "SLA_BREACHED", "NOT_STARTED", "PENDING_APPROVAL", "IN_PROGRESS"]
        rag_map = {
            "COMPLETED": "GREEN", "APPROVED": "GREEN", "SLA_BREACHED": "RED",
            "NOT_STARTED": None, "PENDING_APPROVAL": "AMBER", "IN_PROGRESS": "AMBER", "REWORK": "RED",
        }

        now = datetime.utcnow()
        for months_back in range(6):
            m = now.month - months_back
            y = now.year
            while m <= 0:
                m += 12
                y -= 1
            for kri in all_kris:
                for dim in dimensions:
                    s = random.choice(statuses_pool)
                    sla_due = datetime(y, m, 15) + timedelta(days=3)
                    sla_met_val = completed = None
                    if s in ("COMPLETED", "APPROVED"):
                        sla_met_val = True
                        completed = datetime(y, m, random.randint(10, 20))
                    elif s == "SLA_BREACHED":
                        sla_met_val = False
                    db.add(MonthlyControlStatus(
                        kri_id=kri.kri_id, dimension_id=dim.dimension_id,
                        period_year=y, period_month=m,
                        status=s, rag_status=rag_map.get(s),
                        sla_due_dt=sla_due, sla_met=sla_met_val, completed_dt=completed,
                        created_by="SYSTEM", updated_by="SYSTEM"
                    ))
                    curr = round(random.uniform(50, 200), 2)
                    prev = round(random.uniform(50, 200), 2)
                    var_pct = round((curr - prev) / prev * 100, 2) if prev else 0
                    db.add(MetricValues(
                        kri_id=kri.kri_id, dimension_id=dim.dimension_id,
                        period_year=y, period_month=m,
                        current_value=curr, previous_value=prev,
                        variance_pct=var_pct,
                        variance_status="PASS" if abs(var_pct) <= 10 else "FAIL",
                        created_by="SYSTEM", updated_by="SYSTEM"
                    ))
        db.flush()

        # ── Maker-checker submissions for current-month PENDING_APPROVAL statuses ─
        l1_user = next(u for u, r in users if r == "L1_APPROVER")
        l2_user = next(u for u, r in users if r == "L2_APPROVER")
        l3_user = next(u for u, r in users if r == "L3_ADMIN")
        dp_user = next(u for u, r in users if r == "DATA_PROVIDER")

        current_month_statuses = db.query(MonthlyControlStatus).filter(
            MonthlyControlStatus.period_year == now.year,
            MonthlyControlStatus.period_month == now.month,
            MonthlyControlStatus.status == "PENDING_APPROVAL"
        ).all()

        submission_count = 0
        for i, mcs in enumerate(current_month_statuses):
            if i % 3 == 0:
                mcs.approval_level = "L1"
                mcs.current_approver = l1_user.user_id
                sub = MakerCheckerSubmission(
                    status_id=mcs.status_id, submitted_by=dp_user.user_id,
                    submission_notes=f"Monthly submission for {mcs.kri_id}",
                    l1_approver_id=l1_user.user_id, final_status="L1_PENDING",
                    created_by="SYSTEM", updated_by="SYSTEM"
                )
                audits = [ApprovalAuditTrail(
                    status_id=mcs.status_id, action="SUBMITTED",
                    performed_by=dp_user.user_id,
                    performed_dt=now - timedelta(days=2),
                    comments="Submitted for L1 approval",
                    previous_status="IN_PROGRESS", new_status="PENDING_APPROVAL",
                    created_by="SYSTEM", updated_by="SYSTEM"
                )]
            elif i % 3 == 1:
                mcs.approval_level = "L2"
                mcs.current_approver = l2_user.user_id
                sub = MakerCheckerSubmission(
                    status_id=mcs.status_id, submitted_by=dp_user.user_id,
                    submission_notes=f"Monthly submission for {mcs.kri_id}",
                    l1_approver_id=l1_user.user_id, l1_action="APPROVED",
                    l1_action_dt=now - timedelta(days=1),
                    l2_approver_id=l2_user.user_id, final_status="L2_PENDING",
                    created_by="SYSTEM", updated_by="SYSTEM"
                )
                audits = [
                    ApprovalAuditTrail(
                        status_id=mcs.status_id, action="SUBMITTED",
                        performed_by=dp_user.user_id, performed_dt=now - timedelta(days=3),
                        comments="Submitted for approval",
                        previous_status="IN_PROGRESS", new_status="PENDING_APPROVAL",
                        created_by="SYSTEM", updated_by="SYSTEM"
                    ),
                    ApprovalAuditTrail(
                        status_id=mcs.status_id, action="L1_APPROVED",
                        performed_by=l1_user.user_id, performed_dt=now - timedelta(days=1),
                        comments="Reviewed and approved at L1",
                        previous_status="PENDING_APPROVAL", new_status="PENDING_APPROVAL",
                        created_by="SYSTEM", updated_by="SYSTEM"
                    ),
                ]
            else:
                mcs.approval_level = "L3"
                mcs.current_approver = l3_user.user_id
                sub = MakerCheckerSubmission(
                    status_id=mcs.status_id, submitted_by=dp_user.user_id,
                    submission_notes=f"Monthly submission for {mcs.kri_id}",
                    l1_approver_id=l1_user.user_id, l1_action="APPROVED",
                    l1_action_dt=now - timedelta(days=2),
                    l2_approver_id=l2_user.user_id, l2_action="APPROVED",
                    l2_action_dt=now - timedelta(days=1),
                    l3_approver_id=l3_user.user_id, final_status="L3_PENDING",
                    created_by="SYSTEM", updated_by="SYSTEM"
                )
                audits = [
                    ApprovalAuditTrail(
                        status_id=mcs.status_id, action="SUBMITTED",
                        performed_by=dp_user.user_id, performed_dt=now - timedelta(days=4),
                        comments="Submitted for approval",
                        previous_status="IN_PROGRESS", new_status="PENDING_APPROVAL",
                        created_by="SYSTEM", updated_by="SYSTEM"
                    ),
                    ApprovalAuditTrail(
                        status_id=mcs.status_id, action="L1_APPROVED",
                        performed_by=l1_user.user_id, performed_dt=now - timedelta(days=2),
                        comments="L1 review complete",
                        previous_status="PENDING_APPROVAL", new_status="PENDING_APPROVAL",
                        created_by="SYSTEM", updated_by="SYSTEM"
                    ),
                    ApprovalAuditTrail(
                        status_id=mcs.status_id, action="L2_APPROVED",
                        performed_by=l2_user.user_id, performed_dt=now - timedelta(days=1),
                        comments="L2 sign-off complete",
                        previous_status="PENDING_APPROVAL", new_status="PENDING_APPROVAL",
                        created_by="SYSTEM", updated_by="SYSTEM"
                    ),
                ]
            db.add(sub)
            for a in audits:
                db.add(a)
            submission_count += 1

        db.commit()
        logger.info(
            "Seed complete: 24 KRIs, 7 dimensions, 6 months, %d approval submissions.",
            submission_count,
        )

    except Exception as exc:
        db.rollback()
        logger.error("Seeding failed: %s", exc)
        raise
    finally:
        db.close()
