"""BIC-CCD FastAPI Application Entry Point."""
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import get_settings
from app.database import engine, Base
from app.middleware import RequestIdMiddleware, AuditLogMiddleware
from app.scheduler import create_scheduler
from app.services.seed_service import seed_database
from app.routers import (
    auth_router, lookup_router, dashboard_router, kri_router,
    config_router, control_router, mc_router, evidence_router,
    variance_router, user_router, escalation_router, escalation_metrics_router,
    notification_router, comment_router, datasource_router, health_router,
    admin_override_router, assignment_rule_router,
)
from app.routers.scorecard import scorecard_router
from app.routers.kri_onboarding import router as kri_onboarding_router
from app.routers.audit_evidence import router as audit_evidence_router

settings = get_settings()

# Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("bic_ccd")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(f"Starting BIC-CCD v{settings.APP_VERSION} ({settings.ENV})")
    Base.metadata.create_all(bind=engine)
    if settings.SEED_MOCK_DATA:
        seed_database()
    else:
        logger.info("SEED_MOCK_DATA=false — skipping demo data insertion")

    scheduler = None
    if settings.SCHEDULER_ENABLED:
        scheduler = create_scheduler()
        scheduler.start()
        logger.info("APScheduler started (%d jobs registered)", len(scheduler.get_jobs()))
    else:
        logger.info("Scheduler disabled via SCHEDULER_ENABLED=False")

    yield

    if scheduler is not None:
        scheduler.shutdown(wait=False)
        logger.info("APScheduler shut down")
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
app.include_router(scorecard_router)
app.include_router(kri_onboarding_router)
app.include_router(audit_evidence_router)

# Serve frontend static build in production
if os.path.exists("static"):
    app.mount("/", StaticFiles(directory="static", html=True), name="frontend")
