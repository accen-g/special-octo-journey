"""Email notification engine for BIC-CCD.

Seven notification types (BRD §6):

  6.1  SLA_REMINDER         — day before SLA end; to data provider/owner
  6.2  SLA_ESCALATION       — SLA breached; to L1 approver
  6.3  DCRM_REMINDER        — BD1 of following month; to DCRM data provider
  6.4  DCRM_TIMELINESS_ESC  — after BD2 deadline; to DCRM team lead
  6.5  DCRM_CA_ESC          — after BD3 deadline; to DCRM approver
  6.6  DCRM_APPROVER_NOTIF  — BD2/BD3 approaching; to scorecard approver
  6.7  SCORECARD_EMAIL      — scorecard submitted or approved; to management

Friday weekend rule (§6.1 / §6.2):
  If the computed send date falls on Saturday (weekday 5) or Sunday
  (weekday 6), the notification is brought forward to the preceding Friday.

Design:
  - send_notification() is the main entry point; it writes a Notification
    row to the DB and — if SMTP is configured — dispatches an email.
  - In dev mode (SMTP_HOST == "localhost" / no credentials) only the DB
    row is written; no actual email is sent.  The log line makes it clear.
  - notify_*() convenience helpers build the context and call send_notification().
  - run_daily_notifications(db, today) is called by the scheduler each
    weekday morning to fire all pending 6.1/6.2 reminders.
"""
import logging
import smtplib
import email as _email_module
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import date, datetime, timedelta
from typing import Optional, List

from sqlalchemy.orm import Session

from app.config import get_settings

logger = logging.getLogger("bic_ccd.email")
settings = get_settings()


# ─── Weekend-shift helper ────────────────────────────────────────────────────

def _apply_friday_rule(d: date) -> date:
    """Move a date that lands on Sat/Sun back to the preceding Friday."""
    if d.weekday() == 5:     # Saturday
        return d - timedelta(days=1)
    if d.weekday() == 6:     # Sunday
        return d - timedelta(days=2)
    return d


# ─── SMTP send ───────────────────────────────────────────────────────────────

def _send_smtp(to_addrs: List[str], subject: str, body_html: str) -> bool:
    """Send an email via SMTP.  Returns True on success, False on error.

    If SMTP is not configured (default dev values) the function logs and
    returns False without attempting a connection.
    """
    if not settings.SMTP_USER or settings.SMTP_HOST == "localhost":
        logger.info(
            "[EMAIL-DEV] Would send '%s' to %s (SMTP not configured)",
            subject, to_addrs,
        )
        return False

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = settings.SMTP_FROM
        msg["To"] = ", ".join(to_addrs)
        msg.attach(MIMEText(body_html, "html", "utf-8"))

        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
            if settings.SMTP_TLS:
                server.starttls()
            if settings.SMTP_USER:
                server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            server.sendmail(settings.SMTP_FROM, to_addrs, msg.as_string())

        logger.info("Email sent: '%s' → %s", subject, to_addrs)
        return True

    except Exception as exc:
        logger.error("SMTP error sending '%s' to %s: %s", subject, to_addrs, exc)
        return False


# ─── DB notification record ──────────────────────────────────────────────────

def _create_notification(
    db: Session,
    user_id: int,
    title: str,
    message: str,
    notification_type: str,
    link_url: Optional[str] = None,
) -> None:
    """Persist a Notification row for the given user."""
    from app.models import Notification
    db.add(Notification(
        user_id=user_id,
        title=title,
        message=message,
        notification_type=notification_type,
        is_read=False,
        link_url=link_url,
        created_by="SCHEDULER",
        updated_by="SCHEDULER",
    ))
    # Caller commits after all notifications for a batch are added.


# ─── Core send_notification ──────────────────────────────────────────────────

def send_notification(
    db: Session,
    user_id: int,
    email_addr: str,
    subject: str,
    body_html: str,
    notification_type: str,
    link_url: Optional[str] = None,
    send_date: Optional[date] = None,
    commit: bool = True,
) -> bool:
    """Create DB notification + dispatch email.

    *send_date* — if provided the Friday rule is applied; if the result is
    not today, the notification is skipped (it will be retried tomorrow).
    Pass None to send immediately regardless of date.
    """
    if send_date is not None:
        effective_date = _apply_friday_rule(send_date)
        if effective_date != date.today():
            return False   # not yet time

    _create_notification(db, user_id, subject, body_html, notification_type, link_url)
    if commit:
        db.commit()

    _send_smtp([email_addr], subject, body_html)
    return True


# ─── HTML template helpers ───────────────────────────────────────────────────

def _html(title: str, body: str) -> str:
    return f"""
<html><body style="font-family:Arial,sans-serif;color:#333">
  <h2 style="color:#1565C0">BIC-CCD — {title}</h2>
  {body}
  <hr><p style="font-size:0.8em;color:#999">
    This is an automated message from the BIC Controls &amp; Compliance Dashboard.
    Do not reply.
  </p>
</body></html>
"""


# ─── 6.1  SLA Reminder ───────────────────────────────────────────────────────

def notify_sla_reminder(
    db: Session,
    user_id: int,
    email_addr: str,
    kri_name: str,
    dimension_name: str,
    period: str,
    sla_end: date,
    commit: bool = True,
) -> bool:
    """Send reminder one calendar day before SLA end (Friday-rule applies)."""
    remind_date = sla_end - timedelta(days=1)
    subject = f"[REMINDER] SLA Due Tomorrow — {kri_name} / {dimension_name} ({period})"
    body = _html("SLA Reminder", f"""
        <p>This is a reminder that your submission for:</p>
        <ul>
          <li><strong>KRI:</strong> {kri_name}</li>
          <li><strong>Control:</strong> {dimension_name}</li>
          <li><strong>Period:</strong> {period}</li>
        </ul>
        <p>is due by <strong>{sla_end.strftime('%d %b %Y')}</strong>.</p>
        <p>Please log in to BIC-CCD and complete your submission before the deadline.</p>
    """)
    return send_notification(
        db, user_id, email_addr, subject, body,
        notification_type="SLA_REMINDER",
        link_url="/data-control",
        send_date=remind_date,
        commit=commit,
    )


# ─── 6.2  SLA Escalation ─────────────────────────────────────────────────────

def notify_sla_escalation(
    db: Session,
    user_id: int,
    email_addr: str,
    kri_name: str,
    dimension_name: str,
    period: str,
    sla_end: date,
    commit: bool = True,
) -> bool:
    """Notify L1 approver that SLA has been breached (send immediately)."""
    subject = f"[ESCALATION] SLA Breached — {kri_name} / {dimension_name} ({period})"
    body = _html("SLA Breach Escalation", f"""
        <p style="color:#c62828"><strong>SLA breach detected.</strong></p>
        <ul>
          <li><strong>KRI:</strong> {kri_name}</li>
          <li><strong>Control:</strong> {dimension_name}</li>
          <li><strong>Period:</strong> {period}</li>
          <li><strong>SLA End:</strong> {sla_end.strftime('%d %b %Y')}</li>
        </ul>
        <p>Immediate action is required.
           Please review and escalate as appropriate in BIC-CCD.</p>
    """)
    return send_notification(
        db, user_id, email_addr, subject, body,
        notification_type="SLA_ESCALATION",
        link_url="/approvals",
        commit=commit,
    )


# ─── 6.3  DCRM Reminder ──────────────────────────────────────────────────────

def notify_dcrm_reminder(
    db: Session,
    user_id: int,
    email_addr: str,
    kri_name: str,
    period: str,
    bd2_date: date,
    commit: bool = True,
) -> bool:
    """Notify DCRM data provider on BD1 of the following month."""
    remind_date = bd2_date - timedelta(days=1)   # BD1 ≈ BD2 - 1 calendar day (approx)
    subject = f"[DCRM REMINDER] Data Due — {kri_name} ({period})"
    body = _html("DCRM Data Reminder", f"""
        <p>DCRM data submission is due:</p>
        <ul>
          <li><strong>KRI:</strong> {kri_name}</li>
          <li><strong>Period:</strong> {period}</li>
          <li><strong>Timeliness Deadline (BD2):</strong> {bd2_date.strftime('%d %b %Y')}</li>
        </ul>
        <p>Please ensure data is received by the BD2 deadline.</p>
    """)
    return send_notification(
        db, user_id, email_addr, subject, body,
        notification_type="DCRM_REMINDER",
        link_url="/data-control",
        send_date=remind_date,
        commit=commit,
    )


# ─── 6.4  DCRM Timeliness Escalation ─────────────────────────────────────────

def notify_dcrm_timeliness_escalation(
    db: Session,
    user_id: int,
    email_addr: str,
    kri_name: str,
    period: str,
    commit: bool = True,
) -> bool:
    """Escalate after BD2 when DCRM timeliness data is still not received."""
    subject = f"[DCRM ESCALATION] Timeliness Breach — {kri_name} ({period})"
    body = _html("DCRM Timeliness Escalation", f"""
        <p style="color:#c62828"><strong>BD2 deadline has passed without data receipt.</strong></p>
        <ul>
          <li><strong>KRI:</strong> {kri_name}</li>
          <li><strong>Period:</strong> {period}</li>
        </ul>
        <p>Immediate escalation required.
           Please investigate and take corrective action in BIC-CCD.</p>
    """)
    return send_notification(
        db, user_id, email_addr, subject, body,
        notification_type="DCRM_TIMELINESS_ESC",
        link_url="/data-control",
        commit=commit,
    )


# ─── 6.5  DCRM C&A Escalation ────────────────────────────────────────────────

def notify_dcrm_ca_escalation(
    db: Session,
    user_id: int,
    email_addr: str,
    kri_name: str,
    period: str,
    commit: bool = True,
) -> bool:
    """Escalate after BD3 when DCRM Completeness & Accuracy is incomplete."""
    subject = f"[DCRM ESCALATION] C&A Breach — {kri_name} ({period})"
    body = _html("DCRM C&A Escalation", f"""
        <p style="color:#c62828"><strong>BD3 C&amp;A deadline has passed.</strong></p>
        <ul>
          <li><strong>KRI:</strong> {kri_name}</li>
          <li><strong>Period:</strong> {period}</li>
        </ul>
        <p>Please review completeness and accuracy status in BIC-CCD
           and initiate remediation.</p>
    """)
    return send_notification(
        db, user_id, email_addr, subject, body,
        notification_type="DCRM_CA_ESC",
        link_url="/data-control",
        commit=commit,
    )


# ─── 6.6  DCRM Approver Notification ─────────────────────────────────────────

def notify_dcrm_approver(
    db: Session,
    user_id: int,
    email_addr: str,
    kri_name: str,
    period: str,
    deadline_label: str,
    deadline_date: date,
    commit: bool = True,
) -> bool:
    """Notify scorecard approver that a DCRM deadline is approaching."""
    subject = f"[DCRM] {deadline_label} Approaching — {kri_name} ({period})"
    body = _html("DCRM Approver Notification", f"""
        <p>A DCRM deadline is approaching for your review:</p>
        <ul>
          <li><strong>KRI:</strong> {kri_name}</li>
          <li><strong>Period:</strong> {period}</li>
          <li><strong>Deadline:</strong> {deadline_label} — {deadline_date.strftime('%d %b %Y')}</li>
        </ul>
        <p>Please log in to BIC-CCD to review the current status.</p>
    """)
    return send_notification(
        db, user_id, email_addr, subject, body,
        notification_type="DCRM_APPROVER_NOTIF",
        link_url="/approvals",
        commit=commit,
    )


# ─── 6.7  Scorecard Email ─────────────────────────────────────────────────────

def notify_scorecard(
    db: Session,
    user_id: int,
    email_addr: str,
    period: str,
    scorecard_action: str,   # "submitted" | "approved" | "rejected"
    submitted_by: str,
    commit: bool = True,
) -> bool:
    """Notify management when a scorecard is submitted or approved."""
    action_label = scorecard_action.title()
    subject = f"[SCORECARD] {action_label} — {period}"
    colour = "#2e7d32" if scorecard_action == "approved" else (
        "#c62828" if scorecard_action == "rejected" else "#1565C0"
    )
    body = _html("Scorecard Notification", f"""
        <p>The monthly scorecard for <strong>{period}</strong>
           has been <span style="color:{colour}"><strong>{action_label}</strong></span>
           by <em>{submitted_by}</em>.</p>
        <p>Please log in to BIC-CCD to view the full scorecard.</p>
    """)
    return send_notification(
        db, user_id, email_addr, subject, body,
        notification_type="SCORECARD_EMAIL",
        link_url="/scorecard",
        commit=commit,
    )


# ─── Batch daily notification sweep ──────────────────────────────────────────

def run_daily_notifications(db: Session, today: Optional[date] = None) -> dict:
    """Called by the scheduler each weekday.

    Sweeps all open MonthlyControlStatus rows and fires 6.1/6.2 reminders
    for non-DCRM KRIs and 6.3/6.4/6.5/6.6 for DCRM KRIs.

    Returns a summary dict for logging.
    """
    from app.models import (
        MonthlyControlStatus, KriMaster, ControlDimensionMaster,
        AppUser, UserRoleMapping,
    )
    from app.utils.business_days import nth_business_day

    if today is None:
        today = date.today()

    # Skip weekends
    if today.weekday() >= 5:
        return {"job": "daily_notifications", "skipped": "weekend"}

    sent = {"6.1": 0, "6.2": 0, "6.3": 0, "6.4": 0, "6.5": 0, "6.6": 0}

    # Fetch open rows for current + prior month
    open_rows = (
        db.query(MonthlyControlStatus)
        .filter(MonthlyControlStatus.status.notin_(["COMPLETED", "APPROVED", "REJECTED"]))
        .all()
    )

    def _data_provider_email(kri_id: int) -> Optional[tuple]:
        """Return (user_id, email) of the DATA_PROVIDER assigned to this KRI."""
        row = (
            db.query(AppUser)
            .join(UserRoleMapping, UserRoleMapping.user_id == AppUser.user_id)
            .filter(
                UserRoleMapping.role_code.in_(["DATA_PROVIDER", "METRIC_OWNER"]),
                UserRoleMapping.is_active == True,
                AppUser.is_active == True,
            )
            .first()
        )
        return (row.user_id, row.email) if row else None

    def _l1_email(region_id: int) -> Optional[tuple]:
        row = (
            db.query(AppUser)
            .join(UserRoleMapping, UserRoleMapping.user_id == AppUser.user_id)
            .filter(
                UserRoleMapping.role_code.in_(["L1_APPROVER", "ANC_APPROVER_L1"]),
                UserRoleMapping.region_id == region_id,
                UserRoleMapping.is_active == True,
                AppUser.is_active == True,
            )
            .first()
        )
        return (row.user_id, row.email) if row else None

    for mcs in open_rows:
        kri: KriMaster = mcs.kri if hasattr(mcs, "kri") else db.get(KriMaster, mcs.kri_id)
        if not kri:
            continue

        period_str = f"{mcs.period_year}-{mcs.period_month:02d}"

        if not kri.is_dcrm:
            # ── Standard KRI: 6.1 reminder + 6.2 escalation ──
            sla_end_dt = mcs.sla_end
            if sla_end_dt is None:
                continue
            sla_end_date = sla_end_dt.date() if hasattr(sla_end_dt, "date") else sla_end_dt
            dp = _data_provider_email(kri.kri_id)
            if not dp:
                continue
            uid, eml = dp

            dim = db.get(ControlDimensionMaster, mcs.dimension_id)
            dim_name = dim.dimension_name if dim else "Control"

            # 6.1: reminder day before SLA
            notify_sla_reminder(
                db, uid, eml, kri.kri_name, dim_name, period_str, sla_end_date, commit=False
            )
            sent["6.1"] += 1

            # 6.2: escalation if already breached
            if today > sla_end_date and mcs.status == "SLA_BREACHED":
                l1 = _l1_email(kri.region_id)
                if l1:
                    notify_sla_escalation(
                        db, l1[0], l1[1], kri.kri_name, dim_name, period_str, sla_end_date, commit=False
                    )
                    sent["6.2"] += 1

        else:
            # ── DCRM KRI: 6.3/6.4/6.5/6.6 ──
            # DCRM deadlines are in the following month relative to the reporting period
            if mcs.period_month == 12:
                chk_y, chk_m = mcs.period_year + 1, 1
            else:
                chk_y, chk_m = mcs.period_year, mcs.period_month + 1

            bd2 = nth_business_day(chk_y, chk_m, 2)
            bd3 = nth_business_day(chk_y, chk_m, 3)

            dp = _data_provider_email(kri.kri_id)
            if not dp:
                continue
            uid, eml = dp

            # 6.3 reminder: day before BD2
            notify_dcrm_reminder(db, uid, eml, kri.kri_name, period_str, bd2, commit=False)
            sent["6.3"] += 1

            # 6.4 timeliness escalation: if today >= BD2 + 1 and still NOT_RECEIVED
            if today >= bd2 and mcs.status in ("NOT_STARTED", "SLA_BREACHED"):
                l1 = _l1_email(kri.region_id)
                if l1:
                    notify_dcrm_timeliness_escalation(
                        db, l1[0], l1[1], kri.kri_name, period_str, commit=False
                    )
                    sent["6.4"] += 1

            # 6.5 C&A escalation: if today >= BD3 and dim is COMPLETENESS_ACCURACY
            dim = db.get(ControlDimensionMaster, mcs.dimension_id)
            if dim and dim.dimension_code == "COMPLETENESS_ACCURACY" and today >= bd3:
                if mcs.status in ("NOT_STARTED", "IN_PROGRESS", "SLA_BREACHED"):
                    l2 = (
                        db.query(AppUser)
                        .join(UserRoleMapping, UserRoleMapping.user_id == AppUser.user_id)
                        .filter(
                            UserRoleMapping.role_code.in_(["L2_APPROVER", "ANC_APPROVER_L2"]),
                            UserRoleMapping.is_active == True,
                        )
                        .first()
                    )
                    if l2:
                        notify_dcrm_ca_escalation(
                            db, l2.user_id, l2.email, kri.kri_name, period_str, commit=False
                        )
                        sent["6.5"] += 1

            # 6.6 approver notification (day before BD2 and BD3)
            for deadline_label, deadline_date in [("BD2 Timeliness", bd2), ("BD3 C&A", bd3)]:
                remind_d = _apply_friday_rule(deadline_date - timedelta(days=1))
                if remind_d == today:
                    l3 = (
                        db.query(AppUser)
                        .join(UserRoleMapping, UserRoleMapping.user_id == AppUser.user_id)
                        .filter(
                            UserRoleMapping.role_code.in_(["L3_ADMIN", "SYSTEM_ADMIN", "ANC_APPROVER_L3"]),
                            UserRoleMapping.is_active == True,
                        )
                        .first()
                    )
                    if l3:
                        notify_dcrm_approver(
                            db, l3.user_id, l3.email,
                            kri.kri_name, period_str, deadline_label, deadline_date,
                            commit=False,
                        )
                        sent["6.6"] += 1

    db.commit()
    summary = {"job": "daily_notifications", "date": str(today), **{f"type_{k}": v for k, v in sent.items()}}
    logger.info("daily_notifications complete: %s", summary)
    return summary
