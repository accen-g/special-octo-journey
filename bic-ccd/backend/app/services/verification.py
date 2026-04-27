"""Verification service — scheduler job implementations for BIC-CCD.

Three jobs are called from scheduler.py:

  monthly_init(year, month)
    Run on the 1st of each month (01:00).
    Creates NOT_STARTED rows in BIC_KRI_CONTROL_STATUS_TRACKER and
    NOT_RECEIVED rows in BIC_KRI_DATA_SOURCE_STATUS_TRACKER for every
    active KRI × control-dimension combination that does not already have
    a row for the given period.

  daily_timeliness_check(today)
    Run every weekday at 08:00.
    Looks at each active DataSourceMapping whose tracker row is still
    NOT_RECEIVED.  If the SLA end date has passed → marks the tracker
    NOT_RECEIVED and escalates the parent MonthlyControlStatus to
    SLA_BREACHED.

  dcrm_processing(today)
    Run every weekday at 08:30.
    Applies BD2/BD3/BD8 deadline logic for KRIs flagged is_dcrm=True.
    - BD2 cutoff (Timeliness/DATA_PROVIDER_SLA): mark SLA_BREACHED if
      data still NOT_RECEIVED by BD2 of the following month.
    - BD3 cutoff (C&A/COMPLETENESS_ACCURACY): same rule at BD3.
    - BD8 freeze: freeze the record (no further edits allowed).
"""
import logging
from datetime import datetime, date
from typing import Optional

from sqlalchemy.orm import Session

from app.models import (
    KriMaster, ControlDimensionMaster, KriConfiguration,
    MonthlyControlStatus, DataSourceMapping, DataSourceStatusTracker,
    MakerCheckerSubmission, ApprovalAuditTrail,
)
from app.utils.sla import calculate_sla_dates
from app.utils.business_days import nth_business_day

logger = logging.getLogger("bic_ccd.verification")


# ─── helpers ────────────────────────────────────────────────────────────────

def _get_system_user_id(db: Session) -> Optional[int]:
    """Return user_id for the SCHEDULER system account, or first SYSTEM_ADMIN as fallback.

    Both MakerCheckerSubmission.submitted_by and ApprovalAuditTrail.performed_by
    are NOT NULL FKs, so a real user_id is required for scheduler-added rows.
    """
    from app.models import AppUser, UserRoleMapping
    scheduler = db.query(AppUser).filter(AppUser.soe_id == "SCHEDULER").first()
    if scheduler:
        return scheduler.user_id
    admin = (
        db.query(AppUser)
        .join(UserRoleMapping, UserRoleMapping.user_id == AppUser.user_id)
        .filter(
            UserRoleMapping.role_code == "SYSTEM_ADMIN",
            UserRoleMapping.is_active == True,
            AppUser.is_active == True,
        )
        .first()
    )
    return admin.user_id if admin else None


def _resolve_l1_approver(
    db: Session,
    kri_id: int,
    region_id: Optional[int] = None,
    category_id: Optional[int] = None,
) -> Optional[int]:
    """Resolve L1_APPROVER user_id via assignment rules (mirrors ApproverRuleRepository.resolve)."""
    from app.models import ApprovalAssignmentRule
    rules = (
        db.query(ApprovalAssignmentRule)
        .filter(
            ApprovalAssignmentRule.role_code == "L1_APPROVER",
            ApprovalAssignmentRule.is_active == True,
        )
        .order_by(ApprovalAssignmentRule.priority)
        .all()
    )
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


def _following_month(year: int, month: int):
    """Return (year, month) for the month after the given period."""
    if month == 12:
        return year + 1, 1
    return year, month + 1


def _get_status_fk(db: Session, status_name: str) -> Optional[int]:
    """Look up the BIC_KRI_STATUS PK for *status_name* (cached per call)."""
    from app.models import KriStatusLookup
    row = db.query(KriStatusLookup).filter_by(status_name=status_name).first()
    return row.status_id if row else None


# ─── Job 1 — monthly_init ────────────────────────────────────────────────────

def monthly_init(db: Session, year: int, month: int) -> dict:
    """Create skeleton rows for every active KRI × dimension for *year/month*.

    Idempotent: skips combos that already have a row.
    Dimensions are ordered by display_order (convention ordering — non-blocking).
    For each new tracker row, a MakerCheckerSubmission is added so the L1 queue
    is populated immediately without requiring manual user submissions.
    Returns a summary dict for logging.
    """
    kris = db.query(KriMaster).filter_by(is_active=True).all()
    dims = (
        db.query(ControlDimensionMaster)
        .filter_by(is_active=True)
        .order_by(ControlDimensionMaster.display_order)
        .all()
    )
    sources = db.query(DataSourceMapping).filter_by(is_active=True).all()

    # Pre-fetch existing status-tracker rows for this period
    existing_statuses = {
        (r.kri_id, r.dimension_id)
        for r in db.query(MonthlyControlStatus).filter_by(
            period_year=year, period_month=month
        ).all()
    }

    # Pre-fetch existing data-source tracker rows for this period
    existing_trackers = {
        r.mapping_id
        for r in db.query(DataSourceStatusTracker).filter_by(
            period_year=year, period_month=month
        ).all()
    }

    # Lookup config rows indexed by (kri_id, dimension_id)
    configs = {
        (c.kri_id, c.dimension_id): c
        for c in db.query(KriConfiguration).all()
    }

    pending_fk = _get_status_fk(db, "PENDING_APPROVAL")
    not_received_fk = _get_status_fk(db, "NOT_RECEIVED")
    system_user_id = _get_system_user_id(db)

    if system_user_id is None:
        logger.warning(
            "monthly_init: no SCHEDULER user or SYSTEM_ADMIN found — "
            "submission rows will not be added. Add a system user to the database."
        )

    created_statuses = 0
    created_trackers = 0
    created_submissions = 0
    new_status_rows: list = []  # (kri, MonthlyControlStatus) for submission creation

    for kri in kris:
        for dim in dims:
            if (kri.kri_id, dim.dimension_id) in existing_statuses:
                continue

            cfg = configs.get((kri.kri_id, dim.dimension_id))
            sla_days = cfg.sla_days if cfg else 3
            sla_start_day = cfg.sla_start_day if cfg else None
            sla_end_day = cfg.sla_end_day if cfg else None

            try:
                sla_start, sla_end, freeze_dt = calculate_sla_dates(
                    kri_is_dcrm=kri.is_dcrm,
                    dimension_code=dim.dimension_code or "",
                    year=year,
                    month=month,
                    sla_start_day=sla_start_day,
                    sla_end_day=sla_end_day,
                    sla_days=sla_days,
                )
            except Exception as exc:
                logger.warning(
                    "SLA calc failed for KRI %s / dim %s / %d-%02d: %s",
                    kri.kri_id, dim.dimension_id, year, month, exc,
                )
                sla_start = sla_end = freeze_dt = None

            row = MonthlyControlStatus(
                kri_id=kri.kri_id,
                dimension_id=dim.dimension_id,
                period_year=year,
                period_month=month,
                status="PENDING_APPROVAL",
                status_fk=pending_fk,
                approval_level="L1",
                sla_start=datetime.combine(sla_start, datetime.min.time()) if sla_start else None,
                sla_end=datetime.combine(sla_end, datetime.min.time()) if sla_end else None,
                sla_due_dt=datetime.combine(freeze_dt, datetime.min.time()) if freeze_dt else None,
                created_by="SCHEDULER",
                updated_by="SCHEDULER",
            )
            db.add(row)
            new_status_rows.append((kri, row))
            created_statuses += 1

    # Flush to materialise PKs on new tracker rows before creating submissions
    if new_status_rows:
        db.flush()

    if system_user_id is not None:
        for kri, status_row in new_status_rows:
            l1_approver_id = _resolve_l1_approver(
                db,
                kri_id=kri.kri_id,
                region_id=kri.region_id,
                category_id=kri.category_id,
            )

            if l1_approver_id:
                status_row.current_approver = l1_approver_id

            sub = MakerCheckerSubmission(
                status_id=status_row.status_id,
                submitted_by=system_user_id,
                final_status="L1_PENDING",
                l1_approver_id=l1_approver_id,
                submission_notes=f"Auto-initialised by scheduler for {year}-{month:02d}",
                created_by="SCHEDULER",
                updated_by="SCHEDULER",
            )
            db.add(sub)

            audit = ApprovalAuditTrail(
                status_id=status_row.status_id,
                action="SYSTEM_INIT",
                performed_by=system_user_id,
                previous_status="NOT_STARTED",
                new_status="PENDING_APPROVAL",
                comments=f"Monthly queue initialised by scheduler for {year}-{month:02d}",
                created_by="SCHEDULER",
                updated_by="SCHEDULER",
            )
            db.add(audit)
            created_submissions += 1

    # Data source tracker rows
    for src in sources:
        if src.source_id in existing_trackers:
            continue
        tracker = DataSourceStatusTracker(
            mapping_id=src.source_id,
            period_month=month,
            period_year=year,
            status="NOT_RECEIVED",
            status_id=not_received_fk,
        )
        db.add(tracker)
        created_trackers += 1

    db.commit()
    summary = {
        "job": "monthly_init",
        "period": f"{year}-{month:02d}",
        "created_statuses": created_statuses,
        "created_trackers": created_trackers,
        "created_submissions": created_submissions,
    }
    logger.info("monthly_init complete: %s", summary)
    return summary


# ─── Job 2 — daily_timeliness_check ─────────────────────────────────────────

def daily_timeliness_check(db: Session, today: Optional[date] = None) -> dict:
    """For each open data-source tracker row, check if SLA has elapsed.

    If today > sla_end of the parent MonthlyControlStatus, marks:
      - DataSourceStatusTracker.status = NOT_RECEIVED  (unchanged, but log)
      - MonthlyControlStatus.status    = SLA_BREACHED

    The check is skipped for rows whose parent status is already terminal
    (COMPLETED, APPROVED, SLA_BREACHED, REJECTED).
    """
    if today is None:
        today = date.today()

    terminal = {"COMPLETED", "APPROVED", "SLA_BREACHED", "REJECTED", "CANCELLED"}
    breached_fk = _get_status_fk(db, "SLA_BREACHED")
    not_received_fk = _get_status_fk(db, "NOT_RECEIVED")

    # Fetch all NOT_RECEIVED tracker rows for the current or prior month
    open_trackers = (
        db.query(DataSourceStatusTracker)
        .filter(DataSourceStatusTracker.status == "NOT_RECEIVED")
        .all()
    )

    breached_count = 0
    checked_count = 0

    for tracker in open_trackers:
        checked_count += 1
        mapping = tracker.mapping
        if mapping is None:
            continue

        # Find the MonthlyControlStatus row for this KRI / DATA_PROVIDER_SLA dim
        parent = (
            db.query(MonthlyControlStatus)
            .join(
                ControlDimensionMaster,
                MonthlyControlStatus.dimension_id == ControlDimensionMaster.dimension_id,
            )
            .filter(
                MonthlyControlStatus.kri_id == mapping.kri_id,
                MonthlyControlStatus.period_year == tracker.period_year,
                MonthlyControlStatus.period_month == tracker.period_month,
                ControlDimensionMaster.dimension_code == "DATA_PROVIDER_SLA",
            )
            .first()
        )

        if parent is None or parent.status in terminal:
            continue

        sla_end_dt: Optional[datetime] = parent.sla_end
        if sla_end_dt is None:
            continue

        sla_end_date = sla_end_dt.date() if hasattr(sla_end_dt, "date") else sla_end_dt

        if today > sla_end_date:
            parent.status = "SLA_BREACHED"
            parent.status_fk = breached_fk
            parent.updated_by = "SCHEDULER"
            parent.updated_dt = datetime.utcnow()
            tracker.status_id = not_received_fk
            tracker.updated_dt = datetime.utcnow()
            breached_count += 1
            logger.info(
                "SLA breached: KRI %s / period %d-%02d (SLA end was %s)",
                mapping.kri_id, tracker.period_year, tracker.period_month, sla_end_date,
            )

    db.commit()
    summary = {
        "job": "daily_timeliness_check",
        "date": str(today),
        "checked": checked_count,
        "breached": breached_count,
    }
    logger.info("daily_timeliness_check complete: %s", summary)
    return summary


# ─── Job 3 — dcrm_processing ────────────────────────────────────────────────

def dcrm_processing(db: Session, today: Optional[date] = None) -> dict:
    """Apply BD2/BD3/BD8 deadline rules for DCRM KRIs.

    DCRM SLA dates are in the *following* month (e.g., Jan data → Feb BD2/3/8).

    BD2 (Timeliness / DATA_PROVIDER_SLA dimension):
      If today >= BD2 and tracker still NOT_RECEIVED → mark BREACHED.

    BD3 (C&A / COMPLETENESS_ACCURACY dimension):
      If today >= BD3 and status still NOT_STARTED / IN_PROGRESS → BREACHED.

    BD8 (freeze):
      If today >= BD8 → set a FREEZE flag on MonthlyControlStatus
      (sla_met = False if not yet COMPLETED).
    """
    if today is None:
        today = date.today()

    terminal = {"COMPLETED", "APPROVED", "SLA_BREACHED", "REJECTED"}
    breached_fk = _get_status_fk(db, "SLA_BREACHED")
    not_received_fk = _get_status_fk(db, "NOT_RECEIVED")

    dcrm_kris = db.query(KriMaster).filter_by(is_dcrm=True, is_active=True).all()

    dims_by_code = {
        d.dimension_code: d
        for d in db.query(ControlDimensionMaster).all()
        if d.dimension_code
    }

    timeliness_dim = dims_by_code.get("DATA_PROVIDER_SLA")
    ca_dim = dims_by_code.get("COMPLETENESS_ACCURACY")

    bd2_hits = bd3_hits = bd8_hits = 0

    for kri in dcrm_kris:
        # Determine the reporting month = previous month relative to today
        if today.month == 1:
            rep_year, rep_month = today.year - 1, 12
        else:
            rep_year, rep_month = today.year, today.month - 1

        # DCRM deadlines are in the *following* month (today's month)
        check_year, check_month = today.year, today.month

        bd2 = nth_business_day(check_year, check_month, 2)
        bd3 = nth_business_day(check_year, check_month, 3)
        bd8 = nth_business_day(check_year, check_month, 8)

        # ── BD2 Timeliness ──────────────────────────────────────
        if timeliness_dim and today >= bd2:
            tracker = (
                db.query(DataSourceStatusTracker)
                .join(DataSourceMapping, DataSourceStatusTracker.mapping_id == DataSourceMapping.source_id)
                .filter(
                    DataSourceMapping.kri_id == kri.kri_id,
                    DataSourceStatusTracker.period_year == rep_year,
                    DataSourceStatusTracker.period_month == rep_month,
                    DataSourceStatusTracker.status == "NOT_RECEIVED",
                )
                .first()
            )
            if tracker:
                tracker.status_id = not_received_fk
                tracker.updated_dt = datetime.utcnow()

            parent = (
                db.query(MonthlyControlStatus)
                .filter_by(
                    kri_id=kri.kri_id,
                    dimension_id=timeliness_dim.dimension_id,
                    period_year=rep_year,
                    period_month=rep_month,
                )
                .first()
            )
            if parent and parent.status not in terminal:
                parent.status = "SLA_BREACHED"
                parent.status_fk = breached_fk
                parent.sla_met = False
                parent.updated_by = "SCHEDULER"
                parent.updated_dt = datetime.utcnow()
                bd2_hits += 1
                logger.info("DCRM BD2 breach: KRI %s period %d-%02d", kri.kri_id, rep_year, rep_month)

        # ── BD3 C&A ─────────────────────────────────────────────
        if ca_dim and today >= bd3:
            parent = (
                db.query(MonthlyControlStatus)
                .filter_by(
                    kri_id=kri.kri_id,
                    dimension_id=ca_dim.dimension_id,
                    period_year=rep_year,
                    period_month=rep_month,
                )
                .first()
            )
            if parent and parent.status not in terminal and parent.status in ("NOT_STARTED", "IN_PROGRESS"):
                parent.status = "SLA_BREACHED"
                parent.status_fk = breached_fk
                parent.sla_met = False
                parent.updated_by = "SCHEDULER"
                parent.updated_dt = datetime.utcnow()
                bd3_hits += 1
                logger.info("DCRM BD3 breach: KRI %s period %d-%02d", kri.kri_id, rep_year, rep_month)

        # ── BD8 Freeze ──────────────────────────────────────────
        if today >= bd8:
            frozen = (
                db.query(MonthlyControlStatus)
                .filter(
                    MonthlyControlStatus.kri_id == kri.kri_id,
                    MonthlyControlStatus.period_year == rep_year,
                    MonthlyControlStatus.period_month == rep_month,
                    MonthlyControlStatus.status.notin_({"COMPLETED", "APPROVED"}),
                )
                .all()
            )
            for row in frozen:
                if not row.sla_met:
                    continue  # already marked
                row.sla_met = False
                row.updated_by = "SCHEDULER"
                row.updated_dt = datetime.utcnow()
                bd8_hits += 1

    db.commit()
    summary = {
        "job": "dcrm_processing",
        "date": str(today),
        "bd2_breaches": bd2_hits,
        "bd3_breaches": bd3_hits,
        "bd8_freezes": bd8_hits,
    }
    logger.info("dcrm_processing complete: %s", summary)
    return summary
