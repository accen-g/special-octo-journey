"""BIC-CCD FastAPI Application Entry Point."""
import logging
from contextlib import asynccontextmanager
from datetime import datetime, date, timedelta
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import os

from app.config import get_settings
from app.database import engine, Base, SessionLocal
from app.middleware import RequestIdMiddleware, AuditLogMiddleware
from app.routers import (
    auth_router, lookup_router, dashboard_router, kri_router,
    config_router, control_router, mc_router, evidence_router,
    variance_router, user_router, escalation_router, escalation_metrics_router,
    notification_router, comment_router, datasource_router, health_router,
    admin_override_router, assignment_rule_router,
)
from app.models import (
    RegionMaster, KriCategoryMaster, ControlDimensionMaster,
    AppUser, UserRoleMapping, KriMaster, KriConfiguration,
    MonthlyControlStatus, MetricValues, KriAssignment,
    MakerCheckerSubmission, ApprovalAuditTrail,
)

settings = get_settings()

# Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("bic_ccd")


def seed_database():
    """Seed dev database with demo data."""
    db = SessionLocal()
    try:
        if db.query(RegionMaster).count() > 0:
            logger.info("Database already seeded, skipping.")
            return

        logger.info("Seeding database with demo data...")

        # Regions
        regions = []
        for code, name in [("UK", "United Kingdom"), ("SGP", "Singapore"), ("CEP", "Central Europe")]:
            r = RegionMaster(region_code=code, region_name=name, created_by="SYSTEM", updated_by="SYSTEM")
            db.add(r)
            regions.append(r)
        db.flush()

        # Categories
        categories = []
        for code, name in [
            ("MARKET_RISK", "Market Risk"), ("CREDIT_RISK", "Credit Risk"),
            ("OPS_RISK", "Operational Risk"), ("LIQ_RISK", "Liquidity Risk"),
            ("REGULATORY", "Regulatory Compliance"),
        ]:
            c = KriCategoryMaster(category_code=code, category_name=name, created_by="SYSTEM", updated_by="SYSTEM")
            db.add(c)
            categories.append(c)
        db.flush()

        # Control Dimensions (7 tabs)
        dimensions = []
        for i, (code, name) in enumerate([
            ("DATA_PROVIDER_SLA", "Data Provider SLA"),
            ("COMPLETENESS_ACCURACY", "Completeness & Accuracy"),
            ("MATERIAL_PREPARER", "Material Preparer"),
            ("VARIANCE_ANALYSIS", "Variance Analysis"),
            ("REVIEWS", "Reviews"),
            ("ADJ_TRACKING", "Adjustments Tracking"),
            ("CHANGE_GOVERNANCE", "Change Governance"),
        ], 1):
            d = ControlDimensionMaster(dimension_code=code, dimension_name=name,
                                        display_order=i, created_by="SYSTEM", updated_by="SYSTEM")
            db.add(d)
            dimensions.append(d)
        db.flush()

        # Users
        users_data = [
            ("RANREDDY", "Rahul Anreddy", "rahul.anreddy@company.com", "Risk Mgmt", "MANAGEMENT"),
            ("JSMITH01", "John Smith", "john.smith@company.com", "Controls", "L1_APPROVER"),
            ("ALEE02", "Angela Lee", "angela.lee@company.com", "Controls", "L2_APPROVER"),
            ("BWILSON", "Brian Wilson", "brian.wilson@company.com", "Controls", "L3_ADMIN"),
            ("DPATEL", "Deepa Patel", "deepa.patel@company.com", "Data Ops", "DATA_PROVIDER"),
            ("MKUMAR", "Manoj Kumar", "manoj.kumar@company.com", "Metrics", "METRIC_OWNER"),
            ("SYSADMIN", "System Admin", "admin@company.com", "IT", "SYSTEM_ADMIN"),
        ]
        users = []
        for soe, name, email, dept, role in users_data:
            u = AppUser(soe_id=soe, full_name=name, email=email, department=dept,
                        created_by="SYSTEM", updated_by="SYSTEM")
            db.add(u)
            users.append((u, role))
        db.flush()

        # Role mappings
        for user, role in users:
            for region in regions:
                rm = UserRoleMapping(
                    user_id=user.user_id, role_code=role, region_id=region.region_id,
                    effective_from=date(2024, 1, 1), created_by="SYSTEM", updated_by="SYSTEM"
                )
                db.add(rm)
        db.flush()

        # KRIs — 8 per region = 24 total
        kri_names = [
            ("VaR Limit", "MARKET_RISK"), ("Credit Exposure", "CREDIT_RISK"),
            ("OpRisk Events", "OPS_RISK"), ("Liquidity Buffer", "LIQ_RISK"),
            ("Reg Capital Ratio", "REGULATORY"), ("Stress Test P&L", "MARKET_RISK"),
            ("Default Rate", "CREDIT_RISK"), ("IT Incident Count", "OPS_RISK"),
        ]

        all_kris = []
        kri_num = 0
        for region in regions:
            for kri_name, cat_code in kri_names:
                kri_num += 1
                cat = next(c for c in categories if c.category_code == cat_code)
                risk = ["LOW", "MEDIUM", "HIGH", "CRITICAL"][kri_num % 4]
                k = KriMaster(
                    kri_code=f"KRI-{region.region_code}-{kri_num:03d}",
                    kri_name=f"{kri_name} ({region.region_code})",
                    description=f"Key Risk Indicator for {kri_name} in {region.region_name}",
                    category_id=cat.category_id, region_id=region.region_id,
                    risk_level=risk, framework="Active Framework",
                    onboarded_dt=datetime(2024, 6, 1), created_by="SYSTEM", updated_by="SYSTEM"
                )
                db.add(k)
                all_kris.append(k)
        db.flush()

        # KRI Configurations — each KRI × each dimension
        for kri in all_kris:
            for dim in dimensions:
                cfg = KriConfiguration(
                    kri_id=kri.kri_id, dimension_id=dim.dimension_id,
                    sla_days=3, variance_threshold=10.0,
                    requires_evidence=True, requires_approval=True,
                    freeze_day=15, created_by="SYSTEM", updated_by="SYSTEM"
                )
                db.add(cfg)
        db.flush()

        # Monthly Control Statuses — last 6 months
        import random
        random.seed(42)
        statuses_pool = ["COMPLETED", "SLA_BREACHED", "NOT_STARTED", "PENDING_APPROVAL", "IN_PROGRESS"]
        rag_map = {"COMPLETED": "GREEN", "APPROVED": "GREEN", "SLA_BREACHED": "RED",
                    "NOT_STARTED": None, "PENDING_APPROVAL": "AMBER", "IN_PROGRESS": "AMBER", "REWORK": "RED"}

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
                    sla_met_val = None
                    completed = None
                    if s in ("COMPLETED", "APPROVED"):
                        sla_met_val = True
                        completed = datetime(y, m, random.randint(10, 20))
                    elif s == "SLA_BREACHED":
                        sla_met_val = False

                    mcs = MonthlyControlStatus(
                        kri_id=kri.kri_id, dimension_id=dim.dimension_id,
                        period_year=y, period_month=m,
                        status=s, rag_status=rag_map.get(s),
                        sla_due_dt=sla_due, sla_met=sla_met_val,
                        completed_dt=completed,
                        created_by="SYSTEM", updated_by="SYSTEM"
                    )
                    db.add(mcs)

                    # Metric values
                    curr = round(random.uniform(50, 200), 2)
                    prev = round(random.uniform(50, 200), 2)
                    var_pct = round((curr - prev) / prev * 100, 2) if prev else 0
                    mv = MetricValues(
                        kri_id=kri.kri_id, dimension_id=dim.dimension_id,
                        period_year=y, period_month=m,
                        current_value=curr, previous_value=prev,
                        variance_pct=var_pct,
                        variance_status="PASS" if abs(var_pct) <= 10 else "FAIL",
                        created_by="SYSTEM", updated_by="SYSTEM"
                    )
                    db.add(mv)

        db.flush()

        # Create maker_checker_submissions for current month PENDING_APPROVAL statuses
        # This ensures approvals queues have real data
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
            audit_records = []

            # Assign approver to the monthly status
            if i % 3 == 0:
                # L1 pending
                mcs.approval_level = "L1"
                mcs.current_approver = l1_user.user_id
                sub = MakerCheckerSubmission(
                    status_id=mcs.status_id, submitted_by=dp_user.user_id,
                    submission_notes=f"Monthly submission for {mcs.kri_id}",
                    l1_approver_id=l1_user.user_id, final_status="L1_PENDING",
                    created_by="SYSTEM", updated_by="SYSTEM"
                )
                audit_records = [
                    ApprovalAuditTrail(
                        status_id=mcs.status_id, action="SUBMITTED",
                        performed_by=dp_user.user_id,
                        performed_dt=datetime.utcnow() - timedelta(days=2),
                        comments="Submitted for L1 approval",
                        previous_status="IN_PROGRESS", new_status="PENDING_APPROVAL",
                        created_by="SYSTEM", updated_by="SYSTEM"
                    ),
                ]
            elif i % 3 == 1:
                # L2 pending (L1 already approved)
                mcs.approval_level = "L2"
                mcs.current_approver = l2_user.user_id
                sub = MakerCheckerSubmission(
                    status_id=mcs.status_id, submitted_by=dp_user.user_id,
                    submission_notes=f"Monthly submission for {mcs.kri_id}",
                    l1_approver_id=l1_user.user_id, l1_action="APPROVED",
                    l1_action_dt=datetime.utcnow() - timedelta(days=1),
                    l2_approver_id=l2_user.user_id, final_status="L2_PENDING",
                    created_by="SYSTEM", updated_by="SYSTEM"
                )
                audit_records = [
                    ApprovalAuditTrail(
                        status_id=mcs.status_id, action="SUBMITTED",
                        performed_by=dp_user.user_id,
                        performed_dt=datetime.utcnow() - timedelta(days=3),
                        comments="Submitted for approval",
                        previous_status="IN_PROGRESS", new_status="PENDING_APPROVAL",
                        created_by="SYSTEM", updated_by="SYSTEM"
                    ),
                    ApprovalAuditTrail(
                        status_id=mcs.status_id, action="L1_APPROVED",
                        performed_by=l1_user.user_id,
                        performed_dt=datetime.utcnow() - timedelta(days=1),
                        comments="Reviewed and approved at L1",
                        previous_status="PENDING_APPROVAL", new_status="PENDING_APPROVAL",
                        created_by="SYSTEM", updated_by="SYSTEM"
                    ),
                ]
            else:
                # L3 pending (L1+L2 approved)
                mcs.approval_level = "L3"
                mcs.current_approver = l3_user.user_id
                sub = MakerCheckerSubmission(
                    status_id=mcs.status_id, submitted_by=dp_user.user_id,
                    submission_notes=f"Monthly submission for {mcs.kri_id}",
                    l1_approver_id=l1_user.user_id, l1_action="APPROVED",
                    l1_action_dt=datetime.utcnow() - timedelta(days=2),
                    l2_approver_id=l2_user.user_id, l2_action="APPROVED",
                    l2_action_dt=datetime.utcnow() - timedelta(days=1),
                    l3_approver_id=l3_user.user_id, final_status="L3_PENDING",
                    created_by="SYSTEM", updated_by="SYSTEM"
                )
                audit_records = [
                    ApprovalAuditTrail(
                        status_id=mcs.status_id, action="SUBMITTED",
                        performed_by=dp_user.user_id,
                        performed_dt=datetime.utcnow() - timedelta(days=4),
                        comments="Submitted for approval",
                        previous_status="IN_PROGRESS", new_status="PENDING_APPROVAL",
                        created_by="SYSTEM", updated_by="SYSTEM"
                    ),
                    ApprovalAuditTrail(
                        status_id=mcs.status_id, action="L1_APPROVED",
                        performed_by=l1_user.user_id,
                        performed_dt=datetime.utcnow() - timedelta(days=2),
                        comments="L1 review complete",
                        previous_status="PENDING_APPROVAL", new_status="PENDING_APPROVAL",
                        created_by="SYSTEM", updated_by="SYSTEM"
                    ),
                    ApprovalAuditTrail(
                        status_id=mcs.status_id, action="L2_APPROVED",
                        performed_by=l2_user.user_id,
                        performed_dt=datetime.utcnow() - timedelta(days=1),
                        comments="L2 sign-off complete",
                        previous_status="PENDING_APPROVAL", new_status="PENDING_APPROVAL",
                        created_by="SYSTEM", updated_by="SYSTEM"
                    ),
                ]
            db.add(sub)
            for ar in audit_records:
                db.add(ar)
            submission_count += 1

        db.commit()
        logger.info(f"Database seeded: 24 KRIs, 7 dimensions, 6 months, {submission_count} approval submissions.")

    except Exception as e:
        db.rollback()
        logger.error(f"Seeding failed: {e}")
        raise
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(f"Starting BIC-CCD v{settings.APP_VERSION} ({settings.ENV})")
    Base.metadata.create_all(bind=engine)
    seed_database()
    yield
    logger.info("Shutting down BIC-CCD")


app = FastAPI(
    title="BIC-CCD — B&I Data Metrics and Controls",
    description="Enterprise KRI tracking and control management platform",
    version=settings.APP_VERSION,
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
)

# Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(RequestIdMiddleware)
app.add_middleware(AuditLogMiddleware)

# Routers
app.include_router(health_router)
app.include_router(auth_router)
app.include_router(lookup_router)
app.include_router(dashboard_router)
app.include_router(kri_router)
app.include_router(config_router)
app.include_router(control_router)
app.include_router(mc_router)
app.include_router(evidence_router)
app.include_router(variance_router)
app.include_router(user_router)
app.include_router(escalation_router)
app.include_router(escalation_metrics_router)
app.include_router(notification_router)
app.include_router(comment_router)
app.include_router(datasource_router)
app.include_router(admin_override_router)
app.include_router(assignment_rule_router)

# Serve frontend static build in production
if os.path.exists("static"):
    app.mount("/", StaticFiles(directory="static", html=True), name="frontend")
