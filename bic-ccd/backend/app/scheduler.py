"""APScheduler integration for BIC-CCD.

Three recurring jobs:

  monthly_init       — CronTrigger: day=1, hour=1, minute=0
  daily_timeliness   — CronTrigger: day_of_week=mon-fri, hour=8, minute=0
  dcrm_processing    — CronTrigger: day_of_week=mon-fri, hour=8, minute=30

Distributed lock (BIC_SHED_LOCK)
---------------------------------
Before each job runs, this module tries to acquire a row-level lock in
BIC_SHED_LOCK.  If another instance already holds the lock (lock_until is
in the future) the job is skipped.  The lock is released (lock_until set
to the past) when the job finishes or raises.

Pattern mirrors ShedLock (Java) / redlock.  Safe for active-active
deployments with a shared Oracle / SQLite DB.

Usage (called from main.py lifespan)
--------------------------------------
    from app.scheduler import create_scheduler
    scheduler = create_scheduler()
    scheduler.start()
    ...
    scheduler.shutdown(wait=False)
"""
import logging
import socket
import os
from datetime import datetime, timedelta, date
from typing import Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from app.database import SessionLocal
from app.config import get_settings

logger = logging.getLogger("bic_ccd.scheduler")
settings = get_settings()

# How long to hold a lock before another instance may steal it (safety valve)
_LOCK_TTL_SECONDS = 300  # 5 minutes

_LOCKED_BY = f"{socket.gethostname()}:{os.getpid()}"


# ─── Distributed lock helpers ────────────────────────────────────────────────

def _try_acquire_lock(db, job_name: str) -> bool:
    """Return True and write lock row if the lock is free; False if held."""
    from app.models import SchedulerLock

    now = datetime.utcnow()
    lock = db.query(SchedulerLock).filter_by(job_name=job_name).with_for_update(skip_locked=True).first()

    if lock is None:
        # First ever run — create the row
        db.add(SchedulerLock(
            job_name=job_name,
            lock_until=now + timedelta(seconds=_LOCK_TTL_SECONDS),
            locked_at=now,
            locked_by=_LOCKED_BY,
        ))
        db.commit()
        return True

    if lock.lock_until <= now:
        # Lock expired — steal it
        lock.lock_until = now + timedelta(seconds=_LOCK_TTL_SECONDS)
        lock.locked_at = now
        lock.locked_by = _LOCKED_BY
        db.commit()
        return True

    # Lock still held by someone else
    logger.debug("Skipping %s — lock held by %s until %s", job_name, lock.locked_by, lock.lock_until)
    return False


def _release_lock(db, job_name: str) -> None:
    """Set lock_until to the past so the next instance can acquire it."""
    from app.models import SchedulerLock

    lock = db.query(SchedulerLock).filter_by(job_name=job_name).first()
    if lock:
        lock.lock_until = datetime.utcnow() - timedelta(seconds=1)
        db.commit()


# ─── Job wrappers ────────────────────────────────────────────────────────────

def _run_monthly_init():
    """Scheduler wrapper for verification.monthly_init."""
    from app.services.verification import monthly_init

    today = date.today()
    year, month = today.year, today.month

    db = SessionLocal()
    try:
        if not _try_acquire_lock(db, "monthly_init"):
            return
        logger.info("Running monthly_init for %d-%02d", year, month)
        result = monthly_init(db, year, month)
        logger.info("monthly_init result: %s", result)
    except Exception:
        logger.exception("monthly_init failed")
        db.rollback()
    finally:
        _release_lock(db, "monthly_init")
        db.close()


def _run_daily_timeliness():
    """Scheduler wrapper for verification.daily_timeliness_check."""
    from app.services.verification import daily_timeliness_check

    db = SessionLocal()
    try:
        if not _try_acquire_lock(db, "daily_timeliness_check"):
            return
        logger.info("Running daily_timeliness_check")
        result = daily_timeliness_check(db)
        logger.info("daily_timeliness_check result: %s", result)
    except Exception:
        logger.exception("daily_timeliness_check failed")
        db.rollback()
    finally:
        _release_lock(db, "daily_timeliness_check")
        db.close()


def _run_dcrm_processing():
    """Scheduler wrapper for verification.dcrm_processing."""
    from app.services.verification import dcrm_processing

    db = SessionLocal()
    try:
        if not _try_acquire_lock(db, "dcrm_processing"):
            return
        logger.info("Running dcrm_processing")
        result = dcrm_processing(db)
        logger.info("dcrm_processing result: %s", result)
    except Exception:
        logger.exception("dcrm_processing failed")
        db.rollback()
    finally:
        _release_lock(db, "dcrm_processing")
        db.close()


def _run_daily_notifications():
    """Scheduler wrapper for email.run_daily_notifications."""
    from app.services.email import run_daily_notifications

    db = SessionLocal()
    try:
        if not _try_acquire_lock(db, "daily_notifications"):
            return
        logger.info("Running daily_notifications")
        result = run_daily_notifications(db)
        logger.info("daily_notifications result: %s", result)
    except Exception:
        logger.exception("daily_notifications failed")
        db.rollback()
    finally:
        _release_lock(db, "daily_notifications")
        db.close()


# ─── Scheduler factory ───────────────────────────────────────────────────────

def create_scheduler() -> AsyncIOScheduler:
    """Build and return a configured AsyncIOScheduler (not yet started)."""
    scheduler = AsyncIOScheduler(timezone="UTC")

    # Job 1 — monthly init: 1st of every month at 01:00 UTC
    scheduler.add_job(
        _run_monthly_init,
        trigger=CronTrigger(day=1, hour=1, minute=0, timezone="UTC"),
        id="monthly_init",
        name="Monthly KRI skeleton init",
        replace_existing=True,
        misfire_grace_time=3600,  # tolerate up to 1 h late startup
    )

    # Job 2 — daily timeliness check: weekdays at 08:00 UTC
    scheduler.add_job(
        _run_daily_timeliness,
        trigger=CronTrigger(day_of_week="mon-fri", hour=8, minute=0, timezone="UTC"),
        id="daily_timeliness_check",
        name="Daily data receipt timeliness check",
        replace_existing=True,
        misfire_grace_time=1800,
    )

    # Job 3 — DCRM processing: weekdays at 08:30 UTC
    scheduler.add_job(
        _run_dcrm_processing,
        trigger=CronTrigger(day_of_week="mon-fri", hour=8, minute=30, timezone="UTC"),
        id="dcrm_processing",
        name="DCRM BD2/BD3/BD8 deadline processing",
        replace_existing=True,
        misfire_grace_time=1800,
    )

    # Job 4 — Daily email notifications: weekdays at 07:30 UTC (before timeliness check)
    scheduler.add_job(
        _run_daily_notifications,
        trigger=CronTrigger(day_of_week="mon-fri", hour=7, minute=30, timezone="UTC"),
        id="daily_notifications",
        name="Daily SLA reminder and escalation emails",
        replace_existing=True,
        misfire_grace_time=1800,
    )

    logger.info(
        "Scheduler configured with %d jobs (SCHEDULER_ENABLED=%s)",
        len(scheduler.get_jobs()),
        settings.SCHEDULER_ENABLED,
    )
    return scheduler


# ─── Manual trigger endpoints (used by admin router) ─────────────────────────

def trigger_monthly_init(year: Optional[int] = None, month: Optional[int] = None) -> dict:
    """Run monthly_init immediately for the given period (or current month).

    Returns the summary dict from verification.monthly_init.
    """
    from app.services.verification import monthly_init

    today = date.today()
    year = year or today.year
    month = month or today.month

    db = SessionLocal()
    try:
        result = monthly_init(db, year, month)
        return result
    finally:
        db.close()


def trigger_daily_timeliness() -> dict:
    """Run daily_timeliness_check immediately."""
    from app.services.verification import daily_timeliness_check

    db = SessionLocal()
    try:
        return daily_timeliness_check(db)
    finally:
        db.close()


def trigger_dcrm_processing() -> dict:
    """Run dcrm_processing immediately."""
    from app.services.verification import dcrm_processing

    db = SessionLocal()
    try:
        return dcrm_processing(db)
    finally:
        db.close()
