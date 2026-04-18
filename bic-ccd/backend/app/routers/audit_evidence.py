"""Unified Audit Evidence & Audit Summary router.

Endpoints:
  GET  /api/audit-evidence/kris                           — KRI list with evidence counts
  GET  /api/audit-evidence                                — evidence metadata list
  POST /api/audit-evidence/upload                         — upload a manual file
  GET  /api/audit-evidence/{kri_id}/presigned-url/{ev_id} — pre-signed URL for download
  POST /api/audit-evidence/email/outbound                 — trigger outbound email (called by approval flow)
  POST /api/audit-evidence/email/inbound                  — webhook for inbound email replies
  GET  /api/audit-evidence/{kri_id}/summary               — get audit summary record
  POST /api/audit-evidence/{kri_id}/generate-summary      — generate summary.html (L3 only)
"""
from __future__ import annotations

import io
import json
import logging
import os
import re
import uuid
from calendar import month_name
from datetime import datetime
from email import message_from_bytes
from email.utils import parsedate_to_datetime
from typing import List, Optional

import requests
from fastapi import (
    APIRouter, BackgroundTasks, Depends, File, Form,
    HTTPException, Query, UploadFile,
)
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.middleware import (
    get_current_user, require_any_authenticated, require_evidence,
    require_l3,
)
from app.models import (
    AppUser, KriApprovalLog, KriAuditSummary, KriBluesheet,
    KriEmailIteration, KriEvidenceMetadata, KriMaster, RegionMaster,
    MonthlyControlStatus, KriConfiguration, ControlDimensionMaster,
)
from app.schemas import (
    AuditEvidenceItem, AuditEvidenceKriRow, AuditSummaryResponse,
    GenerateSummaryRequest, OutboundEmailRequest,
)

logger = logging.getLogger("bic_ccd")
settings = get_settings()

router = APIRouter(prefix="/api/audit-evidence", tags=["Audit Evidence"])

# ─── S3 helper ──────────────────────────────────────────────────────────────

_LOCAL_STORE = os.path.join(os.path.dirname(__file__), "..", "..", "local_evidence_store")
_EMAIL_LOG_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "dev_email_log")


def _mock_email_log(
    email_uuid: str,
    subject: str,
    recipient_emails: List[str],
    kri_id: int,
    kri_code: str,
    month_year_label: str,
    iteration: int,
    action: str,
    performed_dt: datetime,
    comments: Optional[str] = None,
) -> None:
    """Write the email payload JSON to disk for dev inspection."""
    os.makedirs(_EMAIL_LOG_DIR, exist_ok=True)
    ts = performed_dt.strftime("%Y%m%d%H%M%S")
    fname = f"{ts}_{email_uuid[:8]}_KRI-{kri_id}.json"
    payload = {
        "uuid": email_uuid,
        "subject": subject,
        "to": recipient_emails,
        "from": settings.EMAIL_FROM_ADDRESS or "noreply@dev.local",
        "kri_id": kri_id,
        "kri_code": kri_code,
        "period": month_year_label,
        "iteration": iteration,
        "action": action,
        "sent_at": performed_dt.isoformat(),
    }
    if comments:
        payload["comments"] = comments
    with open(os.path.join(_EMAIL_LOG_DIR, fname), "w") as f:
        json.dump(payload, f, indent=2)
    logger.info("DEV email mocked → %s", fname)


def _s3_key(region_code: str, year: int, month: int, control_id: str, filename: str) -> str:
    """Build the canonical S3 object key. control_id is the string identifier."""
    base = (
        f"{settings.EVIDENCE_S3_BASE_PATH}/{region_code}/{year}/{month:02d}"
        f"/Evidences/TEMP/{control_id}/COMMON"
    )
    return f"{base}/{filename}"


def _s3_email_key(
    region_code: str, year: int, month: int, control_id: str,
    task_id: str, iteration: int, timestamp: str, action: str,
) -> str:
    base = (
        f"{settings.EVIDENCE_S3_BASE_PATH}/{region_code}/{year}/{month:02d}"
        f"/Evidences/TEMP/{control_id}/COMMON"
    )
    return f"{base}/task-{task_id}/iter-{iteration}/email-{timestamp}-{action}.eml"


def _s3_summary_key(region_code: str, year: int, month: int, control_id: str) -> str:
    base = (
        f"{settings.EVIDENCE_S3_BASE_PATH}/{region_code}/{year}/{month:02d}"
        f"/Evidences/TEMP/{control_id}/COMMON"
    )
    return f"{base}/summary.html"


def _upload_to_s3(s3_key: str, content: bytes, content_type: str = "application/octet-stream") -> None:
    """Upload bytes to S3 (falls back to local disk when DEV_MOCK_S3=true or S3_ENDPOINT is not set)."""
    if not settings.DEV_MOCK_S3 and settings.S3_ENDPOINT:
        try:
            import boto3
            from botocore.client import Config

            s3 = boto3.client(
                "s3",
                endpoint_url=settings.S3_ENDPOINT,
                aws_access_key_id=settings.S3_ACCESS_KEY,
                aws_secret_access_key=settings.S3_SECRET_KEY,
                config=Config(signature_version="s3v4"),
                region_name=settings.S3_REGION,
            )
            s3.put_object(
                Bucket=settings.S3_BUCKET,
                Key=s3_key,
                Body=content,
                ContentType=content_type,
            )
            logger.info("S3 upload OK: %s", s3_key)
            return
        except Exception as exc:
            logger.warning("S3 upload failed, falling back to local: %s", exc)

    # Local fallback — mirrors the S3 key structure on disk
    local_path = os.path.join(_LOCAL_STORE, s3_key.replace("/", os.sep))
    os.makedirs(os.path.dirname(local_path), exist_ok=True)
    with open(local_path, "wb") as f:
        f.write(content)
    logger.info("Local store write: %s", local_path)


def _generate_presigned_url(s3_key: str) -> str:
    """Return a pre-signed URL (or local /api/... proxy URL when DEV_MOCK_S3=true or S3_ENDPOINT is not set)."""
    if not settings.DEV_MOCK_S3 and settings.S3_ENDPOINT:
        try:
            import boto3
            from botocore.client import Config

            s3 = boto3.client(
                "s3",
                endpoint_url=settings.S3_ENDPOINT,
                aws_access_key_id=settings.S3_ACCESS_KEY,
                aws_secret_access_key=settings.S3_SECRET_KEY,
                config=Config(signature_version="s3v4"),
                region_name=settings.S3_REGION,
            )
            return s3.generate_presigned_url(
                "get_object",
                Params={"Bucket": settings.S3_BUCKET, "Key": s3_key},
                ExpiresIn=settings.S3_PRESIGNED_EXPIRY,
            )
        except Exception as exc:
            logger.warning("Presigned URL generation failed: %s", exc)

    # Dev fallback — return a local download proxy URL
    return f"/api/audit-evidence/local-download?key={s3_key}"


# ─── Email service helper ────────────────────────────────────────────────────

def _send_outbound_email(
    kri_id: int,
    kri_code: str,
    month_year_label: str,
    iteration: int,
    action: str,
    recipient_emails: List[str],
    performed_dt: datetime,
    comments: Optional[str] = None,
    kri_name: str = "",
    region_code: str = "",
) -> str:
    """Send email via the HTTP email service. Returns the generated uuid."""
    email_uuid = str(uuid.uuid4())
    subject = f"KRI-{kri_id} | {month_year_label} | Iteration {iteration} | {action}"

    # ── DEV MOCK: write to disk, skip real HTTP call ──────────────────────────
    if settings.DEV_MOCK_EMAIL or not settings.EMAIL_SERVICE_URL:
        _mock_email_log(email_uuid, subject, recipient_emails, kri_id, kri_code,
                        month_year_label, iteration, action, performed_dt, comments)
        if not settings.EMAIL_SERVICE_URL:
            logger.warning("EMAIL_SERVICE_URL not configured — email mocked for %s", subject)
        else:
            logger.info("DEV_MOCK_EMAIL=True — email mocked (not sent): %s", subject)
        return email_uuid

    headers = {
        "uuid": settings.EMAIL_UUID_HEADER or email_uuid,
        "Content-Type": "application/json",
    }

    mail_payload = {
        "templateDetails": {
            "templateType": settings.EMAIL_TEMPLATE_TYPE,
            "templateName": settings.EMAIL_TEMPLATE_NAME,
        },
        "subject": subject,
        "hasAttachments": False,
        "to": recipient_emails,
        "CC": [],
        "BCC": [],
        "from": settings.EMAIL_FROM_ADDRESS,
        "uuid": email_uuid,
        "body": {
            "commonParams": {
                "module_name": settings.EMAIL_MODULE_NAME,
                "report_date": performed_dt.strftime("%d %B %Y"),
                "environment": settings.EMAIL_ENVIRONMENT,
            },
            "tableData": [
                {
                    "kri_id": str(kri_id),
                    "kri_code": kri_code,
                    "kri_name": kri_name,
                    "region": region_code,
                    "period": month_year_label,
                    "iteration": str(iteration),
                    "action": action,
                    **({"comments": comments} if comments else {}),
                }
            ],
        },
    }

    # Retry up to 3 times
    for attempt in range(1, 4):
        try:
            response = requests.post(
                settings.EMAIL_SERVICE_URL,
                json=mail_payload,
                headers=headers,
                verify=False,
                timeout=30,
            )
            response.raise_for_status()
            logger.info("Email sent OK (attempt %d): %s", attempt, subject)
            return email_uuid
        except Exception as exc:
            logger.warning("Email send attempt %d failed: %s", attempt, exc)
            if attempt == 3:
                logger.error("Email permanently failed after 3 attempts: %s", subject)
    return email_uuid


def _build_eml_content(
    subject: str,
    from_addr: str,
    to_addrs: List[str],
    body: str,
    sent_dt: datetime,
) -> bytes:
    """Build a minimal RFC-2822 .eml file with an HTML body."""
    to_str = ", ".join(to_addrs)
    date_str = sent_dt.strftime("%a, %d %b %Y %H:%M:%S +0000")
    return (
        f"From: {from_addr}\r\n"
        f"To: {to_str}\r\n"
        f"Subject: {subject}\r\n"
        f"Date: {date_str}\r\n"
        f"MIME-Version: 1.0\r\n"
        f"Content-Type: text/html; charset=utf-8\r\n\r\n"
        f"{body}\r\n"
    ).encode("utf-8")


# ─── Structured HTML email body builder ─────────────────────────────────────

_STATUS_COLOURS: dict = {
    "approved": "#2e7d32",
    "final approved": "#1b5e20",
    "rejected": "#c62828",
    "rework required": "#f57c00",
    "rework": "#f57c00",
    "escalated": "#6a1b9a",
    "submission": "#1565c0",
    "submitted": "#1565c0",
}


def _build_email_html_body(
    kri_code: str,
    kri_name: str,
    region_code: str,
    month_year_label: str,
    action: str,
    iteration: int,
    comments: Optional[str],
    iteration_history: list,
) -> str:
    """Return a structured HTML body for approval-workflow notification emails.

    *iteration_history* is a list of dicts with keys ``iteration``, ``action``,
    and ``comments`` representing all **prior** iterations for this KRI/period.
    The current iteration is always appended last so the audit trail is complete
    and in chronological order.
    """
    colour = _STATUS_COLOURS.get(action.lower(), "#1565c0")

    # ── Audit trail rows (prior iterations + current) ────────────────────────
    all_iterations = list(iteration_history) + [
        {"iteration": iteration, "action": action, "comments": comments, "current": True}
    ]

    trail_rows = ""
    for entry in all_iterations:
        entry_iter = entry.get("iteration", "")
        entry_action = entry.get("action") or ""
        entry_comments = entry.get("comments") or "—"
        is_current = entry.get("current", False)
        entry_colour = _STATUS_COLOURS.get(entry_action.lower(), "#555555")
        row_bg = "background:#f8f9fa;" if is_current else ""
        current_label = (
            " <span style=\"font-size:0.72em;color:#888;font-weight:400;\">(current)</span>"
            if is_current else ""
        )
        trail_rows += (
            f"<tr style=\"{row_bg}\">"
            f"<td style=\"padding:8px 12px;border-bottom:1px solid #eee;"
            f"font-weight:700;white-space:nowrap;\">Iteration {entry_iter}{current_label}</td>"
            f"<td style=\"padding:8px 12px;border-bottom:1px solid #eee;\">"
            f"<span style=\"color:{entry_colour};font-weight:600;\">{entry_action}</span></td>"
            f"<td style=\"padding:8px 12px;border-bottom:1px solid #eee;"
            f"color:#444;\">{entry_comments}</td>"
            f"</tr>"
        )

    return (
        "<!DOCTYPE html>"
        "<html><head>"
        "<meta charset=\"utf-8\">"
        "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
        "</head>"
        "<body style=\"margin:0;padding:0;background:#f4f6fa;"
        "font-family:Arial,Helvetica,sans-serif;color:#222;\">"
        "<table width=\"100%\" cellpadding=\"0\" cellspacing=\"0\""
        " style=\"background:#f4f6fa;padding:24px 0;\">"
        "<tr><td align=\"center\">"
        "<table width=\"620\" cellpadding=\"0\" cellspacing=\"0\""
        " style=\"background:#fff;border-radius:6px;"
        "box-shadow:0 2px 8px rgba(0,0,0,0.08);overflow:hidden;max-width:620px;\">"

        # ── Header ──────────────────────────────────────────────────────────
        "<tr>"
        "<td style=\"background:#003366;padding:20px 28px;\">"
        "<p style=\"margin:0;font-size:0.7rem;font-weight:700;text-transform:uppercase;"
        "letter-spacing:1px;color:#a8c4e0;\">B&amp;I Data Metrics and Controls</p>"
        f"<p style=\"margin:6px 0 0;font-size:1.15rem;font-weight:700;color:#fff;\">"
        f"{kri_code} &mdash; {kri_name}</p>"
        f"<p style=\"margin:6px 0 0;font-size:0.82rem;color:#a8c4e0;\">"
        f"Region:&nbsp;<strong style=\"color:#d0e4f7;\">{region_code}</strong>"
        f"&nbsp;&nbsp;|&nbsp;&nbsp;"
        f"Period:&nbsp;<strong style=\"color:#d0e4f7;\">{month_year_label}</strong></p>"
        "</td>"
        "</tr>"

        # ── Status summary block ─────────────────────────────────────────────
        "<tr>"
        "<td style=\"padding:20px 28px 0;\">"
        f"<table width=\"100%\" cellpadding=\"0\" cellspacing=\"0\""
        f" style=\"border-left:4px solid {colour};background:#f8f9fa;"
        f"border-radius:0 4px 4px 0;\">"
        "<tr>"
        "<td style=\"padding:14px 18px;\">"
        "<p style=\"margin:0;font-size:0.7rem;font-weight:700;text-transform:uppercase;"
        "letter-spacing:0.8px;color:#666;\">Current Status</p>"
        f"<p style=\"margin:4px 0 0;font-size:1.05rem;font-weight:700;color:{colour};\">"
        f"{action}</p>"
        "</td>"
        "<td style=\"padding:14px 18px;\">"
        "<p style=\"margin:0;font-size:0.7rem;font-weight:700;text-transform:uppercase;"
        "letter-spacing:0.8px;color:#666;\">Iteration</p>"
        f"<p style=\"margin:4px 0 0;font-size:1.05rem;font-weight:700;color:#333;\">"
        f"{iteration}</p>"
        "</td>"
        "</tr>"
        "</table>"
        "</td>"
        "</tr>"

        # ── Details table ────────────────────────────────────────────────────
        "<tr>"
        "<td style=\"padding:24px 28px 0;\">"
        "<p style=\"margin:0 0 10px;font-size:0.78rem;font-weight:700;"
        "text-transform:uppercase;letter-spacing:0.8px;color:#555;\">Details</p>"
        "<table width=\"100%\" cellpadding=\"0\" cellspacing=\"0\""
        " style=\"border-collapse:collapse;font-size:0.88rem;\">"
        "<tr>"
        "<td style=\"padding:7px 0;color:#666;width:140px;border-bottom:1px solid #eee;\">KRI ID</td>"
        f"<td style=\"padding:7px 0;font-weight:600;border-bottom:1px solid #eee;\">{kri_code}</td>"
        "</tr>"
        "<tr>"
        "<td style=\"padding:7px 0;color:#666;border-bottom:1px solid #eee;\">KRI Name</td>"
        f"<td style=\"padding:7px 0;font-weight:600;border-bottom:1px solid #eee;\">{kri_name}</td>"
        "</tr>"
        "<tr>"
        "<td style=\"padding:7px 0;color:#666;border-bottom:1px solid #eee;\">Region</td>"
        f"<td style=\"padding:7px 0;font-weight:600;border-bottom:1px solid #eee;\">{region_code}</td>"
        "</tr>"
        "<tr>"
        "<td style=\"padding:7px 0;color:#666;border-bottom:1px solid #eee;\">Period</td>"
        f"<td style=\"padding:7px 0;font-weight:600;border-bottom:1px solid #eee;\">{month_year_label}</td>"
        "</tr>"
        "<tr>"
        "<td style=\"padding:7px 0;color:#666;border-bottom:1px solid #eee;\">Action Taken</td>"
        f"<td style=\"padding:7px 0;font-weight:600;color:{colour};"
        f"border-bottom:1px solid #eee;\">{action}</td>"
        "</tr>"
        "<tr>"
        "<td style=\"padding:7px 0;color:#666;\">Iteration</td>"
        f"<td style=\"padding:7px 0;font-weight:600;\">{iteration}</td>"
        "</tr>"
        "</table>"
        "</td>"
        "</tr>"

        # ── Audit trail ──────────────────────────────────────────────────────
        "<tr>"
        "<td style=\"padding:24px 28px 0;\">"
        "<p style=\"margin:0 0 10px;font-size:0.78rem;font-weight:700;"
        "text-transform:uppercase;letter-spacing:0.8px;color:#555;\">"
        "Iteration &amp; Audit Trail</p>"
        "<table width=\"100%\" cellpadding=\"0\" cellspacing=\"0\""
        " style=\"border-collapse:collapse;font-size:0.88rem;\">"
        "<thead>"
        "<tr style=\"background:#e8edf5;\">"
        "<th style=\"padding:8px 12px;text-align:left;border-bottom:2px solid #c5cfe0;"
        "width:160px;\">Iteration</th>"
        "<th style=\"padding:8px 12px;text-align:left;border-bottom:2px solid #c5cfe0;"
        "width:180px;\">Action</th>"
        "<th style=\"padding:8px 12px;text-align:left;border-bottom:2px solid #c5cfe0;\">"
        "Comments</th>"
        "</tr>"
        "</thead>"
        f"<tbody>{trail_rows}</tbody>"
        "</table>"
        "</td>"
        "</tr>"

        # ── Action link ──────────────────────────────────────────────────────
        "<tr>"
        "<td style=\"padding:28px 28px 0;\">"
        "<a href=\"/approvals\""
        " style=\"display:inline-block;background:#003366;color:#fff;"
        "text-decoration:none;padding:11px 22px;border-radius:4px;"
        "font-size:0.88rem;font-weight:600;\">View &amp; Take Action &rarr;</a>"
        "</td>"
        "</tr>"

        # ── Body copy ────────────────────────────────────────────────────────
        "<tr>"
        "<td style=\"padding:20px 28px 0;\">"
        "<p style=\"margin:0;font-size:0.88rem;color:#444;line-height:1.6;\">"
        "Kindly review and take the necessary action at your earliest convenience."
        "</p>"
        "</td>"
        "</tr>"

        # ── Footer ───────────────────────────────────────────────────────────
        "<tr>"
        "<td style=\"padding:24px 28px;\">"
        "<hr style=\"border:none;border-top:1px solid #e0e0e0;margin:0 0 16px;\">"
        "<p style=\"margin:0;font-size:0.75rem;color:#999;line-height:1.5;\">"
        "This is an automated notification from the "
        "<strong>B&amp;I Data Metrics and Controls</strong> platform. "
        "Do not reply to this email."
        "</p>"
        "</td>"
        "</tr>"

        "</table>"
        "</td></tr>"
        "</table>"
        "</body></html>"
    )


# ─── KRI context helpers ─────────────────────────────────────────────────────

def _get_kri_context(kri_id: int, db: Session) -> dict:
    """Resolve region_code, control_id, data_provider_name for a KRI."""
    kri = (
        db.query(KriMaster)
        .filter(KriMaster.kri_id == kri_id)
        .first()
    )
    if not kri:
        raise HTTPException(status_code=404, detail=f"KRI {kri_id} not found")

    region_code = kri.region.region_code if kri.region else "UNKNOWN"

    # control_id from bluesheet control_ids field (first token).
    # Use kri_id-based fallback to avoid the TEMP/COMMON/COMMON path duplication
    # that occurs when the literal "COMMON" is used as a folder name inside
    # a path that already ends with /COMMON/.
    bs = db.query(KriBluesheet).filter(KriBluesheet.kri_id == kri_id).first()
    control_id = f"KRI{kri_id}"   # safe, unique fallback — never "COMMON"
    data_provider_name = None
    if bs:
        if bs.control_ids:
            raw_id = bs.control_ids.split(",")[0].strip()
            control_id = raw_id if raw_id else f"KRI{kri_id}"
        data_provider_name = bs.data_provider_name

    return {
        "kri_id": kri.kri_id,
        "kri_code": kri.kri_code or f"KRI-{kri_id}",
        "kri_name": kri.kri_name,
        "region_code": region_code,
        "control_id": control_id,
        "data_provider_name": data_provider_name,
    }


def _get_or_increment_iteration(
    kri_id: int, year: int, month: int, db: Session
) -> int:
    """Get current iteration, create row if first time."""
    row = (
        db.query(KriEmailIteration)
        .filter(
            KriEmailIteration.kri_id == kri_id,
            KriEmailIteration.period_year == year,
            KriEmailIteration.period_month == month,
        )
        .first()
    )
    if not row:
        row = KriEmailIteration(
            kri_id=kri_id,
            period_year=year,
            period_month=month,
            current_iter=1,
        )
        db.add(row)
        db.flush()
    return row.current_iter


def _increment_iteration(kri_id: int, year: int, month: int, db: Session) -> int:
    row = (
        db.query(KriEmailIteration)
        .filter(
            KriEmailIteration.kri_id == kri_id,
            KriEmailIteration.period_year == year,
            KriEmailIteration.period_month == month,
        )
        .first()
    )
    if not row:
        row = KriEmailIteration(
            kri_id=kri_id,
            period_year=year,
            period_month=month,
            current_iter=1,
        )
        db.add(row)
        db.flush()
        return 1
    row.current_iter += 1
    row.last_updated = datetime.utcnow()
    db.flush()
    return row.current_iter


# ════════════════════════════════════════════════════════════
# ENDPOINTS
# ════════════════════════════════════════════════════════════

# ─── List KRIs with evidence counts ─────────────────────────
@router.get("/kris")
def list_kris_with_evidence(
    year: int = Query(...),
    month: int = Query(...),
    region_id: Optional[int] = Query(None),
    search: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    _user: dict = Depends(require_evidence),
):
    """Return one row per active KRI × Control for the Evidence page table.

    Each row has its own status (from CCB_KRI_CONTROL_STATUS_TRACKER) and
    evidence count (from BIC_KRI_EVIDENCE_METADATA filtered by dimension_code).
    """
    # 1 ── Active KRIs (with optional region / search filters)
    kri_query = db.query(KriMaster).filter(KriMaster.is_active == True)
    if region_id:
        kri_query = kri_query.filter(KriMaster.region_id == region_id)
    if search:
        s = f"%{search.lower()}%"
        kri_query = kri_query.filter(
            KriMaster.kri_code.ilike(s) | KriMaster.kri_name.ilike(s)
        )
    kris = kri_query.all()
    kri_ids = [k.kri_id for k in kris]
    kri_map = {k.kri_id: k for k in kris}

    if not kri_ids:
        return []

    # 2 ── Active KRI × Control configurations (one row per pair)
    configs = (
        db.query(KriConfiguration, ControlDimensionMaster)
        .join(
            ControlDimensionMaster,
            KriConfiguration.dimension_id == ControlDimensionMaster.dimension_id,
        )
        .filter(
            KriConfiguration.kri_id.in_(kri_ids),
            KriConfiguration.is_active == True,
        )
        .order_by(KriConfiguration.kri_id, ControlDimensionMaster.display_order)
        .all()
    )

    # 3 ── Per-control status from CCB_KRI_CONTROL_STATUS_TRACKER
    #       Key: (kri_id, dimension_id)
    status_rows = (
        db.query(
            MonthlyControlStatus.kri_id,
            MonthlyControlStatus.dimension_id,
            MonthlyControlStatus.status,
        )
        .filter(
            MonthlyControlStatus.period_year == year,
            MonthlyControlStatus.period_month == month,
            MonthlyControlStatus.kri_id.in_(kri_ids),
        )
        .all()
    )
    status_map: dict[tuple, str] = {
        (r.kri_id, r.dimension_id): r.status for r in status_rows
    }

    # 4 ── Per-control evidence counts from BIC_KRI_EVIDENCE_METADATA
    #       Grouped by (kri_id, control_id string = dimension_code)
    ev_counts_q = (
        db.query(
            KriEvidenceMetadata.kri_id,
            KriEvidenceMetadata.control_id,
            func.count(KriEvidenceMetadata.evidence_id).label("cnt"),
        )
        .filter(
            KriEvidenceMetadata.period_year == year,
            KriEvidenceMetadata.period_month == month,
            KriEvidenceMetadata.kri_id.in_(kri_ids),
        )
        .group_by(KriEvidenceMetadata.kri_id, KriEvidenceMetadata.control_id)
        .all()
    )
    # Key: (kri_id, dimension_code_string)
    ev_count_map: dict[tuple, int] = {
        (r.kri_id, r.control_id): r.cnt for r in ev_counts_q
    }

    # 5 ── Bluesheet lookup (data_provider_name only)
    bs_map = {
        bs.kri_id: bs
        for bs in db.query(KriBluesheet)
        .filter(KriBluesheet.kri_id.in_(kri_ids))
        .all()
    }

    # 6 ── Build one row per KRI × Control
    rows = []
    for cfg, dim in configs:
        kri = kri_map[cfg.kri_id]
        ctrl_status = status_map.get((cfg.kri_id, cfg.dimension_id), "NOT_STARTED")

        # Apply server-side status filter if requested
        if status and ctrl_status != status:
            continue

        dim_code = dim.dimension_code  # e.g. "TIMELINESS"
        ev_cnt = ev_count_map.get((cfg.kri_id, dim_code), 0)
        bs = bs_map.get(cfg.kri_id)

        rows.append(
            AuditEvidenceKriRow(
                kri_id=kri.kri_id,
                kri_code=kri.kri_code,
                kri_name=kri.kri_name,
                region_name=kri.region.region_name if kri.region else None,
                region_code=kri.region.region_code if kri.region else None,
                dimension_id=cfg.dimension_id,
                control_id=dim_code,
                control_name=dim.dimension_name,
                data_provider_name=bs.data_provider_name if bs else None,
                status=ctrl_status,
                evidence_count=ev_cnt,
                period_year=year,
                period_month=month,
            )
        )

    return rows


# ─── List evidence items ─────────────────────────────────────
@router.get("")
def list_evidence(
    kri_id: Optional[int] = Query(None),
    year: Optional[int] = Query(None),
    month: Optional[int] = Query(None),
    evidence_type: Optional[str] = Query(None),
    region_id: Optional[int] = Query(None),
    control_code: Optional[str] = Query(None),   # filter by dimension_code string
    db: Session = Depends(get_db),
    _user: dict = Depends(require_evidence),
):
    q = db.query(KriEvidenceMetadata)
    if kri_id:
        q = q.filter(KriEvidenceMetadata.kri_id == kri_id)
    if year:
        q = q.filter(KriEvidenceMetadata.period_year == year)
    if month:
        q = q.filter(KriEvidenceMetadata.period_month == month)
    if evidence_type:
        q = q.filter(KriEvidenceMetadata.evidence_type == evidence_type)
    if control_code:
        q = q.filter(KriEvidenceMetadata.control_id == control_code)
    if region_id:
        kri_ids = [
            k.kri_id
            for k in db.query(KriMaster).filter(KriMaster.region_id == region_id).all()
        ]
        q = q.filter(KriEvidenceMetadata.kri_id.in_(kri_ids))

    items = q.order_by(KriEvidenceMetadata.created_dt.desc()).all()

    result = []
    for ev in items:
        kri = ev.kri
        result.append(
            AuditEvidenceItem(
                evidence_id=ev.evidence_id,
                kri_id=ev.kri_id,
                kri_code=kri.kri_code if kri else None,
                kri_name=kri.kri_name if kri else None,
                control_id=ev.control_id,
                region_code=ev.region_code,
                period_year=ev.period_year,
                period_month=ev.period_month,
                iteration=ev.iteration,
                evidence_type=ev.evidence_type,
                action=ev.action,
                sender=ev.sender,
                receiver=ev.receiver,
                file_name=ev.file_name,
                s3_object_path=ev.s3_object_path,
                uploaded_by_name=ev.uploader.full_name if ev.uploader else None,
                notes=ev.notes,
                is_unmapped=ev.is_unmapped,
                email_uuid=ev.email_uuid,
                created_dt=ev.created_dt,
            )
        )
    return result


# ─── Upload file evidence ────────────────────────────────────
@router.post("/upload")
async def upload_evidence(
    file: UploadFile = File(...),
    kri_id: int = Form(...),
    year: int = Form(...),
    month: int = Form(...),
    notes: Optional[str] = Form(None),
    evidence_type: str = Form("manual"),
    dimension_id: Optional[int] = Form(None),   # which control this evidence belongs to
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_evidence),
):
    # Validate file size
    content = await file.read()
    max_bytes = settings.EVIDENCE_MAX_FILE_SIZE_MB * 1024 * 1024
    if len(content) > max_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"File exceeds {settings.EVIDENCE_MAX_FILE_SIZE_MB} MB limit",
        )

    # Allowed extensions
    allowed_ext = {".pdf", ".xlsx", ".png", ".eml", ".msg", ".docx", ".csv", ".pptx"}
    _, ext = os.path.splitext(file.filename or "")
    if ext.lower() not in allowed_ext:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{ext}'. Allowed: {', '.join(allowed_ext)}",
        )

    # Resolve region_code from KRI
    kri = db.query(KriMaster).filter(KriMaster.kri_id == kri_id).first()
    if not kri:
        raise HTTPException(status_code=404, detail=f"KRI {kri_id} not found")
    region_code = kri.region.region_code if kri.region else "UNKNOWN"

    # Resolve control_id string from dimension_id when supplied,
    # otherwise fall back to the old _get_kri_context behaviour.
    if dimension_id is not None:
        dim = (
            db.query(ControlDimensionMaster)
            .filter(ControlDimensionMaster.dimension_id == dimension_id)
            .first()
        )
        control_id = dim.dimension_code if (dim and dim.dimension_code) else f"DIM{dimension_id}"
    else:
        ctx = _get_kri_context(kri_id, db)
        control_id = ctx["control_id"]

    # Unique filename to avoid overwrites
    ts = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    safe_name = f"{ts}_{file.filename}"
    s3_key = _s3_key(region_code, year, month, control_id, safe_name)

    # Upload to S3 (or local)
    _upload_to_s3(s3_key, content)

    # Insert metadata row
    meta = KriEvidenceMetadata(
        kri_id=kri_id,
        control_id=control_id,
        region_code=region_code,
        period_year=year,
        period_month=month,
        evidence_type=evidence_type,
        file_name=file.filename,
        s3_object_path=s3_key,
        uploaded_by=current_user["user_id"],
        notes=notes,
        created_by=current_user["soe_id"],
        updated_by=current_user["soe_id"],
    )
    db.add(meta)
    db.commit()
    db.refresh(meta)

    return {
        "evidence_id": meta.evidence_id,
        "s3_path": s3_key,
        "file_name": file.filename,
        "control_id": control_id,
    }


# ─── Pre-signed URL ──────────────────────────────────────────
@router.get("/{kri_id}/presigned-url/{evidence_id}")
def get_presigned_url(
    kri_id: int,
    evidence_id: int,
    db: Session = Depends(get_db),
    _user: dict = Depends(require_evidence),
):
    ev = (
        db.query(KriEvidenceMetadata)
        .filter(
            KriEvidenceMetadata.evidence_id == evidence_id,
            KriEvidenceMetadata.kri_id == kri_id,
        )
        .first()
    )
    if not ev:
        raise HTTPException(status_code=404, detail="Evidence not found")

    url = _generate_presigned_url(ev.s3_object_path)
    return {"url": url, "file_name": ev.file_name, "expires_in": settings.S3_PRESIGNED_EXPIRY}


# ─── Outbound email ──────────────────────────────────────────
@router.post("/email/outbound")
def send_outbound_email(
    payload: OutboundEmailRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    _user: dict = Depends(require_any_authenticated),
):
    """Trigger an outbound email for an approval workflow event.
    Called internally after L1/L2/L3 actions.
    """
    ctx = _get_kri_context(payload.kri_id, db)
    region_code = ctx["region_code"]
    control_id = ctx["control_id"]
    kri_code = ctx["kri_code"]
    kri_name = ctx["kri_name"]

    month_label = month_name[payload.month]
    month_year_label = f"{month_label} {payload.year}"

    # Query prior email iterations for the audit trail before incrementing
    prior_emails = (
        db.query(KriEvidenceMetadata)
        .filter(
            KriEvidenceMetadata.kri_id == payload.kri_id,
            KriEvidenceMetadata.period_year == payload.year,
            KriEvidenceMetadata.period_month == payload.month,
            KriEvidenceMetadata.evidence_type == "email",
        )
        .order_by(KriEvidenceMetadata.evidence_id)
        .all()
    )
    iter_history = [
        {"iteration": r.iteration, "action": r.action or "", "comments": r.notes}
        for r in prior_emails
    ]

    iteration = _increment_iteration(payload.kri_id, payload.year, payload.month, db)

    task_id = str(uuid.uuid4())[:8]
    ts = datetime.utcnow()
    ts_str = ts.strftime("%Y%m%d%H%M%S")
    action_slug = payload.action.replace(" ", "_").lower()

    eml_key = _s3_email_key(
        region_code, payload.year, payload.month, control_id,
        task_id, iteration, ts_str, action_slug,
    )

    # Build structured HTML .eml content
    subject = f"KRI-{payload.kri_id} | {month_year_label} | Iteration {iteration} | {payload.action}"
    html_body = _build_email_html_body(
        kri_code=kri_code,
        kri_name=kri_name,
        region_code=region_code,
        month_year_label=month_year_label,
        action=payload.action,
        iteration=iteration,
        comments=None,
        iteration_history=iter_history,
    )
    eml_content = _build_eml_content(
        subject=subject,
        from_addr=settings.EMAIL_FROM_ADDRESS or "noreply@company.com",
        to_addrs=payload.recipient_emails,
        body=html_body,
        sent_dt=ts,
    )
    _upload_to_s3(eml_key, eml_content, content_type="message/rfc822")

    # Insert metadata
    uploader_id = payload.performed_by_user_id
    meta = KriEvidenceMetadata(
        kri_id=payload.kri_id,
        control_id=control_id,
        region_code=region_code,
        period_year=payload.year,
        period_month=payload.month,
        iteration=iteration,
        evidence_type="email",
        action=payload.action,
        sender=settings.EMAIL_FROM_ADDRESS,
        receiver=", ".join(payload.recipient_emails),
        file_name=f"email-{ts_str}-{action_slug}.eml",
        s3_object_path=eml_key,
        uploaded_by=uploader_id,
        email_uuid=task_id,
        created_by="SYSTEM",
        updated_by="SYSTEM",
    )
    db.add(meta)
    db.commit()

    # Send actual email in background
    background_tasks.add_task(
        _send_outbound_email,
        payload.kri_id,
        kri_code,
        month_year_label,
        iteration,
        payload.action,
        payload.recipient_emails,
        ts,
        None,
        kri_name,
        region_code,
    )

    return {"iteration": iteration, "email_uuid": task_id, "s3_path": eml_key}


# ─── Inbound email webhook ───────────────────────────────────
@router.post("/email/inbound")
async def receive_inbound_email(
    file: UploadFile = File(None),
    raw_email: Optional[str] = Form(None),
    db: Session = Depends(get_db),
):
    """Webhook for inbound email replies.
    Accepts either a file upload (.eml) or raw email text in form field.
    Parses the subject to extract KRI_ID, month/year, and iteration.
    """
    # Read the raw email bytes
    if file is not None:
        content = await file.read()
    elif raw_email:
        content = raw_email.encode("utf-8")
    else:
        raise HTTPException(status_code=400, detail="Provide either a file or raw_email field")

    # Parse
    msg = message_from_bytes(content)
    subject = msg.get("Subject", "")
    from_addr = msg.get("From", "")
    to_addr = msg.get("To", "")

    # Try new format first: KRI-{id} | {Month Year} | Iteration {n} | {action}
    # Fall back to old format: KRI-{id} [{Month Year}] | Iter-{n} | {action}
    # Both formats keep group(1)=kri_id, group(2)=month_year, group(3)=iteration.
    match = re.search(
        r"KRI-(\d+)\s*\|\s*([A-Za-z]+ \d{4})\s*\|\s*Iteration\s+(\d+)",
        subject,
        re.IGNORECASE,
    )
    if not match:
        match = re.search(
            r"KRI-(\d+)\s*\[([^\]]+)\]\s*\|\s*Iter-(\d+)",
            subject,
            re.IGNORECASE,
        )

    is_unmapped = False
    kri_id = None
    iteration = None
    period_year = None
    period_month = None
    region_code = "UNKNOWN"
    control_id = "COMMON"

    if match:
        kri_id = int(match.group(1))
        month_year_str = match.group(2).strip()
        iteration = int(match.group(3))

        # Parse month/year
        for fmt in ("%B %Y", "%b %Y"):
            try:
                dt = datetime.strptime(month_year_str, fmt)
                period_year = dt.year
                period_month = dt.month
                break
            except ValueError:
                pass

        if period_year is None:
            is_unmapped = True

        if not is_unmapped:
            try:
                ctx = _get_kri_context(kri_id, db)
                region_code = ctx["region_code"]
                control_id = ctx["control_id"]
            except HTTPException:
                is_unmapped = True
    else:
        is_unmapped = True

    if is_unmapped:
        kri_id = kri_id or 0
        period_year = period_year or datetime.utcnow().year
        period_month = period_month or datetime.utcnow().month
        iteration = iteration or 0

    ts_str = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    filename = f"email-{ts_str}-inbound.eml"

    if not is_unmapped and kri_id:
        task_id = str(uuid.uuid4())[:8]
        eml_key = _s3_email_key(
            region_code, period_year, period_month, control_id,
            task_id, iteration, ts_str, "inbound",
        )
    else:
        eml_key = f"{settings.EVIDENCE_S3_BASE_PATH}/UNMAPPED/{ts_str}/{filename}"

    _upload_to_s3(eml_key, content, content_type="message/rfc822")

    meta = KriEvidenceMetadata(
        kri_id=kri_id if kri_id else 0,
        control_id=control_id,
        region_code=region_code,
        period_year=period_year,
        period_month=period_month,
        iteration=iteration,
        evidence_type="email",
        action="INBOUND",
        sender=from_addr,
        receiver=to_addr,
        file_name=filename,
        s3_object_path=eml_key,
        is_unmapped=is_unmapped,
        created_by="SYSTEM",
        updated_by="SYSTEM",
    )
    db.add(meta)
    db.commit()
    db.refresh(meta)

    return {
        "evidence_id": meta.evidence_id,
        "is_unmapped": is_unmapped,
        "kri_id": kri_id,
        "iteration": iteration,
    }


# ─── Get audit summary ───────────────────────────────────────
@router.get("/{kri_id}/summary")
def get_audit_summary(
    kri_id: int,
    year: Optional[int] = Query(None),
    month: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    _user: dict = Depends(require_evidence),
):
    q = db.query(KriAuditSummary).filter(KriAuditSummary.kri_id == kri_id)
    if year:
        q = q.filter(KriAuditSummary.period_year == year)
    if month:
        q = q.filter(KriAuditSummary.period_month == month)

    summary = q.order_by(KriAuditSummary.generated_dt.desc()).first()
    if not summary:
        raise HTTPException(status_code=404, detail="Audit summary not found")

    return AuditSummaryResponse.model_validate(summary)


# ─── Generate audit summary ──────────────────────────────────
@router.post("/{kri_id}/generate-summary")
def generate_audit_summary(
    kri_id: int,
    payload: GenerateSummaryRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_l3),
):
    """Generate summary.html and upload to S3. L3/SYSTEM_ADMIN only."""
    ctx = _get_kri_context(kri_id, db)
    kri = db.query(KriMaster).filter(KriMaster.kri_id == kri_id).first()
    region_code = ctx["region_code"]
    control_id = ctx["control_id"]

    year = payload.year
    month = payload.month
    month_label = month_name[month]

    # Fetch all evidence for this KRI + period
    evidences = (
        db.query(KriEvidenceMetadata)
        .filter(
            KriEvidenceMetadata.kri_id == kri_id,
            KriEvidenceMetadata.period_year == year,
            KriEvidenceMetadata.period_month == month,
        )
        .order_by(KriEvidenceMetadata.created_dt)
        .all()
    )

    # Fetch approval log
    approval_logs = (
        db.query(KriApprovalLog)
        .filter(KriApprovalLog.kri_id == kri_id)
        .order_by(KriApprovalLog.performed_dt)
        .all()
    )

    # Bluesheet
    bs = db.query(KriBluesheet).filter(KriBluesheet.kri_id == kri_id).first()

    # Iteration count
    iter_row = (
        db.query(KriEmailIteration)
        .filter(
            KriEmailIteration.kri_id == kri_id,
            KriEmailIteration.period_year == year,
            KriEmailIteration.period_month == month,
        )
        .first()
    )
    total_iterations = iter_row.current_iter if iter_row else 0

    total_evidences = len(evidences)
    total_emails = sum(1 for e in evidences if e.evidence_type == "email")
    manual_count = sum(1 for e in evidences if e.evidence_type == "manual")
    auto_count = sum(1 for e in evidences if e.evidence_type == "auto")

    l3_approver_name = current_user.get("full_name", current_user["soe_id"])
    generated_dt = datetime.utcnow()

    # ── Generate HTML ──────────────────────────────────────────
    def _ev_link(ev: KriEvidenceMetadata) -> str:
        url = _generate_presigned_url(ev.s3_object_path)
        return f'<a href="{url}" target="_blank">{ev.file_name}</a>'

    def _fmt_dt(dt) -> str:
        if dt is None:
            return "—"
        if isinstance(dt, str):
            return dt
        return dt.strftime("%d %b %Y %H:%M UTC")

    # Group emails by iteration
    email_by_iter: dict[int, list] = {}
    for ev in evidences:
        if ev.evidence_type == "email":
            it = ev.iteration or 0
            email_by_iter.setdefault(it, []).append(ev)

    workflow_rows = ""
    for log in approval_logs:
        actor = log.performer.full_name if log.performer else f"User #{log.performed_by}"
        workflow_rows += f"""
        <tr>
          <td>—</td>
          <td>{log.action}</td>
          <td>{actor}</td>
          <td>{_fmt_dt(log.performed_dt)}</td>
          <td>—</td>
        </tr>"""

    email_trail_html = ""
    for iter_num in sorted(email_by_iter.keys()):
        email_trail_html += f"<h4 style='margin:12px 0 4px'>Iteration {iter_num}</h4><table class='t'><thead><tr><th>Direction</th><th>Subject / File</th><th>From</th><th>To</th><th>Time</th><th>Download</th></tr></thead><tbody>"
        for ev in email_by_iter[iter_num]:
            direction = "↙ Inbound" if ev.action == "INBOUND" else "↗ Outgoing"
            url = _generate_presigned_url(ev.s3_object_path)
            email_trail_html += f"""
            <tr>
              <td>{direction}</td>
              <td>{ev.file_name}</td>
              <td>{ev.sender or '—'}</td>
              <td>{ev.receiver or '—'}</td>
              <td>{_fmt_dt(ev.created_dt)}</td>
              <td><a href="{url}" download>📥 .eml</a></td>
            </tr>"""
        email_trail_html += "</tbody></table>"

    evidence_rows = ""
    for ev in evidences:
        type_badge = {"manual": "Manual", "auto": "Auto", "email": "Email"}.get(ev.evidence_type, ev.evidence_type)
        actor = ev.uploader.full_name if ev.uploader else "SYSTEM"
        evidence_rows += f"""
        <tr>
          <td>{type_badge}</td>
          <td>{ev.file_name}</td>
          <td>{actor}</td>
          <td>{_fmt_dt(ev.created_dt)}</td>
          <td>{_ev_link(ev)}</td>
        </tr>"""

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Audit Summary — KRI-{kri_id} [{month_label} {year}]</title>
<style>
  body {{ font-family: Arial, sans-serif; font-size: 13px; color: #222; margin: 24px; }}
  h1 {{ font-size: 20px; border-bottom: 2px solid #1a56db; padding-bottom: 8px; }}
  h2 {{ font-size: 15px; margin-top: 24px; color: #1a56db; }}
  h3 {{ font-size: 13px; margin: 16px 0 4px; }}
  table.t {{ border-collapse: collapse; width: 100%; margin-bottom: 16px; }}
  table.t th, table.t td {{ border: 1px solid #ccc; padding: 6px 10px; text-align: left; }}
  table.t th {{ background: #eef3fb; font-weight: 700; }}
  table.t tr:nth-child(even) {{ background: #f9f9f9; }}
  .badge {{ display: inline-block; padding: 2px 10px; border-radius: 12px;
            font-weight: 700; font-size: 12px; }}
  .badge-approved {{ background: #d1fae5; color: #065f46; }}
  .badge-rework   {{ background: #fef3c7; color: #92400e; }}
  .badge-rejected {{ background: #fee2e2; color: #991b1b; }}
  .metrics {{ display: flex; gap: 16px; flex-wrap: wrap; margin: 12px 0; }}
  .metric-card {{ border: 1px solid #e5e7eb; border-radius: 8px; padding: 12px 20px; min-width: 120px; }}
  .metric-card .val {{ font-size: 24px; font-weight: 700; color: #1a56db; }}
  .metric-card .lbl {{ font-size: 11px; color: #6b7280; }}
  a {{ color: #1a56db; }}
</style>
</head>
<body>

<h1>Audit Evidence Summary</h1>
<p style="color:#6b7280">Generated: {_fmt_dt(generated_dt)} &nbsp;|&nbsp; L3 Approver: {l3_approver_name}</p>

<!-- A. KRI Details -->
<h2>A. KRI Details</h2>
<table class="t">
  <tr><th>KRI ID</th><td>KRI-{kri_id}</td><th>KRI Code</th><td>{ctx['kri_code']}</td></tr>
  <tr><th>KRI Name</th><td colspan="3">{ctx['kri_name']}</td></tr>
  <tr><th>Region</th><td>{region_code}</td><th>Reporting Period</th><td>{month_label} {year}</td></tr>
  <tr><th>Control ID</th><td>{control_id}</td><th>Final Status</th>
      <td><span class="badge badge-approved">{bs.approval_status if bs else 'APPROVED'}</span></td></tr>
  <tr><th>L3 Approver</th><td>{l3_approver_name}</td><th>Approval Timestamp</th><td>{_fmt_dt(generated_dt)}</td></tr>
</table>

<!-- E. Summary Metrics -->
<h2>E. Summary Metrics</h2>
<div class="metrics">
  <div class="metric-card"><div class="val">{total_iterations}</div><div class="lbl">Total Iterations</div></div>
  <div class="metric-card"><div class="val">{total_evidences}</div><div class="lbl">Total Evidence Files</div></div>
  <div class="metric-card"><div class="val">{manual_count}</div><div class="lbl">Manual</div></div>
  <div class="metric-card"><div class="val">{auto_count}</div><div class="lbl">Auto</div></div>
  <div class="metric-card"><div class="val">{total_emails}</div><div class="lbl">Email Exchanges</div></div>
</div>

<!-- B. Workflow Timeline -->
<h2>B. Full Workflow Timeline</h2>
<table class="t">
  <thead><tr><th>Iteration</th><th>Action</th><th>Actor</th><th>Timestamp</th><th>Email</th></tr></thead>
  <tbody>{workflow_rows or '<tr><td colspan="5">No approval log entries</td></tr>'}</tbody>
</table>

<!-- C. Email Trail -->
<h2>C. Iteration-wise Email Trail</h2>
{email_trail_html or '<p>No email trail recorded.</p>'}

<!-- D. Evidence List -->
<h2>D. Complete Evidence List</h2>
<table class="t">
  <thead><tr><th>Type</th><th>File Name</th><th>Actor</th><th>Timestamp</th><th>Link</th></tr></thead>
  <tbody>{evidence_rows or '<tr><td colspan="5">No evidence recorded.</td></tr>'}</tbody>
</table>

</body>
</html>"""

    # Upload summary.html to S3
    s3_path = _s3_summary_key(region_code, year, month, control_id)
    _upload_to_s3(s3_path, html.encode("utf-8"), content_type="text/html")

    # Upsert KriAuditSummary row
    existing = (
        db.query(KriAuditSummary)
        .filter(
            KriAuditSummary.kri_id == kri_id,
            KriAuditSummary.period_year == year,
            KriAuditSummary.period_month == month,
        )
        .first()
    )
    if existing:
        existing.s3_path = s3_path
        existing.generated_dt = generated_dt
        existing.generated_by = current_user["user_id"]
        existing.l3_approver_name = l3_approver_name
        existing.total_iterations = total_iterations
        existing.total_evidences = total_evidences
        existing.total_emails = total_emails
        db.commit()
        db.refresh(existing)
        return {"s3_path": s3_path, "summary_id": existing.summary_id}

    summary_row = KriAuditSummary(
        kri_id=kri_id,
        period_year=year,
        period_month=month,
        s3_path=s3_path,
        generated_dt=generated_dt,
        generated_by=current_user["user_id"],
        l3_approver_name=l3_approver_name,
        final_status=bs.approval_status if bs else "APPROVED",
        total_iterations=total_iterations,
        total_evidences=total_evidences,
        total_emails=total_emails,
    )
    db.add(summary_row)
    db.commit()
    db.refresh(summary_row)

    return {"s3_path": s3_path, "summary_id": summary_row.summary_id}


# ─── Convenience: background task wrapper for approval hooks ─
def trigger_outbound_email_background(
    kri_id: int,
    year: int,
    month: int,
    action: str,
    recipient_emails: List[str],
    performed_by_user_id: Optional[int],
    db: Session,
    comments: Optional[str] = None,
    dimension_code: Optional[str] = None,
) -> None:
    """Called from maker-checker and kri_onboarding approve endpoints via BackgroundTasks.

    dimension_code — when supplied (approval-flow emails) the email record is stored
    with control_id = dimension_code so it appears under the correct control's
    Email Trail tab.  Falls back to _get_kri_context() for non-dimension-scoped callers.
    """
    try:
        ctx = _get_kri_context(kri_id, db)
        region_code = ctx["region_code"]
        # Use the real dimension_code when available so the DB control_id matches
        # the value the email-trail query filters on (KriEvidenceMetadata.control_id).
        control_id = dimension_code if dimension_code else ctx["control_id"]
        kri_code = ctx["kri_code"]
        kri_name = ctx["kri_name"]

        month_label = month_name[month]
        month_year_label = f"{month_label} {year}"

        # Query prior email iterations for audit trail before incrementing
        prior_emails = (
            db.query(KriEvidenceMetadata)
            .filter(
                KriEvidenceMetadata.kri_id == kri_id,
                KriEvidenceMetadata.period_year == year,
                KriEvidenceMetadata.period_month == month,
                KriEvidenceMetadata.evidence_type == "email",
            )
            .order_by(KriEvidenceMetadata.evidence_id)
            .all()
        )
        iter_history = [
            {"iteration": r.iteration, "action": r.action or "", "comments": r.notes}
            for r in prior_emails
        ]

        iteration = _increment_iteration(kri_id, year, month, db)

        task_id = str(uuid.uuid4())[:8]
        ts = datetime.utcnow()
        ts_str = ts.strftime("%Y%m%d%H%M%S")
        action_slug = action.replace(" ", "_").lower()

        eml_key = _s3_email_key(
            region_code, year, month, control_id,
            task_id, iteration, ts_str, action_slug,
        )
        subject = f"KRI-{kri_id} | {month_year_label} | Iteration {iteration} | {action}"
        html_body = _build_email_html_body(
            kri_code=kri_code,
            kri_name=kri_name,
            region_code=region_code,
            month_year_label=month_year_label,
            action=action,
            iteration=iteration,
            comments=comments,
            iteration_history=iter_history,
        )
        eml_content = _build_eml_content(
            subject=subject,
            from_addr=settings.EMAIL_FROM_ADDRESS or "noreply@company.com",
            to_addrs=recipient_emails,
            body=html_body,
            sent_dt=ts,
        )
        _upload_to_s3(eml_key, eml_content, content_type="message/rfc822")

        meta = KriEvidenceMetadata(
            kri_id=kri_id,
            control_id=control_id,
            region_code=region_code,
            period_year=year,
            period_month=month,
            iteration=iteration,
            evidence_type="email",
            action=action,
            sender=settings.EMAIL_FROM_ADDRESS,
            receiver=", ".join(recipient_emails),
            file_name=f"email-{ts_str}-{action_slug}.eml",
            s3_object_path=eml_key,
            uploaded_by=performed_by_user_id,
            notes=comments,
            email_uuid=task_id,
            created_by="SYSTEM",
            updated_by="SYSTEM",
        )
        db.add(meta)
        db.commit()

        _send_outbound_email(
            kri_id, kri_code, month_year_label, iteration, action,
            recipient_emails, ts, comments, kri_name, region_code,
        )

    except Exception as exc:
        logger.error("trigger_outbound_email_background failed for KRI %d: %s", kri_id, exc)


# ═══════════════════════════════════════════════════════════════════════
# DEV-ONLY ENDPOINTS  (safe in production — just return 403 if not mock)
# ═══════════════════════════════════════════════════════════════════════

@router.get("/dev/email-log")
def dev_email_log(_user: dict = Depends(require_any_authenticated)):
    """Return list of mocked emails written to disk (DEV_MOCK_EMAIL=True only)."""
    if not settings.DEV_MOCK_EMAIL:
        raise HTTPException(status_code=403, detail="DEV_MOCK_EMAIL is not enabled")

    if not os.path.isdir(_EMAIL_LOG_DIR):
        return {"emails": [], "log_dir": _EMAIL_LOG_DIR}

    entries = []
    for fname in sorted(os.listdir(_EMAIL_LOG_DIR), reverse=True):
        if fname.endswith(".json"):
            try:
                with open(os.path.join(_EMAIL_LOG_DIR, fname)) as f:
                    entries.append(json.load(f))
            except Exception:
                pass

    return {"emails": entries, "count": len(entries), "log_dir": _EMAIL_LOG_DIR}


@router.delete("/dev/email-log")
def dev_clear_email_log(_user: dict = Depends(require_any_authenticated)):
    """Wipe the dev email log directory."""
    if not settings.DEV_MOCK_EMAIL:
        raise HTTPException(status_code=403, detail="DEV_MOCK_EMAIL is not enabled")

    import shutil
    if os.path.isdir(_EMAIL_LOG_DIR):
        shutil.rmtree(_EMAIL_LOG_DIR)

    return {"cleared": True}


# ─── Local-store file download proxy ─────────────────────────
# NO authentication — the opaque key path is the access token.
# Only available when DEV_MOCK_S3=true (no real S3 configured).
@router.get("/local-download")
def local_download(key: str = Query(..., description="S3 object key returned by the presigned-url endpoint")):
    """Serve a file directly from the local evidence store.

    This route is the dev-mode replacement for S3 pre-signed URLs.
    The route itself requires no Bearer token so the browser can navigate
    to it directly via window.open().  Path-traversal is prevented by
    resolving the real path and asserting it stays inside _LOCAL_STORE.
    """
    import mimetypes
    from fastapi.responses import FileResponse

    # Reconstruct the on-disk path from the S3-style key
    local_path = os.path.realpath(
        os.path.join(_LOCAL_STORE, key.replace("/", os.sep))
    )
    store_root = os.path.realpath(_LOCAL_STORE)

    # Security: reject any path that escapes the store root (path traversal)
    if not local_path.startswith(store_root + os.sep) and local_path != store_root:
        raise HTTPException(status_code=403, detail="Access denied")

    if not os.path.isfile(local_path):
        raise HTTPException(
            status_code=404,
            detail="File not found in local evidence store. "
                   "Make sure DEV_MOCK_S3=true and the file was uploaded in this session.",
        )

    mime_type, _ = mimetypes.guess_type(local_path)
    return FileResponse(
        local_path,
        media_type=mime_type or "application/octet-stream",
        filename=os.path.basename(local_path),
    )


@router.get("/local-download")
def local_download(
    key: str,
    _user: dict = Depends(require_any_authenticated),
):
    """Serve a file from the local evidence store (dev fallback for pre-signed URLs)."""
    from fastapi.responses import FileResponse

    local_path = os.path.join(_LOCAL_STORE, key.replace("/", os.sep))
    if not os.path.isfile(local_path):
        raise HTTPException(status_code=404, detail="File not found in local store")

    # Basic path traversal guard
    real_store = os.path.realpath(_LOCAL_STORE)
    real_path = os.path.realpath(local_path)
    if not real_path.startswith(real_store):
        raise HTTPException(status_code=400, detail="Invalid path")

    return FileResponse(real_path, filename=os.path.basename(real_path))
