"""Seed script — Audit Evidence & Email Trail sample data.

Usage (from backend/ directory):
    python scripts/seed_audit_evidence.py

What it creates:
  • Picks the first 3 active KRIs (or all if fewer than 3)
  • Inserts KriEvidenceMetadata rows:
      - 2 manual file evidences per KRI (PDF, XLSX)
      - 1 auto evidence per KRI
      - 2 outbound email evidences (Iter-1, Iter-2)
      - 1 inbound email reply (Iter-1)
  • Inserts KriEmailIteration rows (current_iter = 2)
  • Inserts KriAuditSummary rows
  • Writes matching dummy files to local_evidence_store/ so
    the /local-download endpoint actually serves something.
  • Writes two sample JSON entries to dev_email_log/ so
    GET /api/audit-evidence/dev/email-log returns data.

Safe to run multiple times (skips KRIs that already have evidence).
"""

import os
import sys
import json
import shutil
from datetime import datetime, timedelta
from calendar import month_name

# ── Path setup ────────────────────────────────────────────────────────────────
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, BACKEND_DIR)

# Use whatever database the .env file configures (Oracle or SQLite).
# Do NOT override here — just inherit from the project .env.

from app.database import SessionLocal, Base, engine  # noqa: E402
from app.models import (  # noqa: E402
    KriMaster, KriBluesheet, KriEvidenceMetadata, KriEmailIteration, KriAuditSummary,
)

# ── Constants ─────────────────────────────────────────────────────────────────
LOCAL_STORE = os.path.join(BACKEND_DIR, "local_evidence_store")
EMAIL_LOG_DIR = os.path.join(BACKEND_DIR, "dev_email_log")

SEED_YEAR = 2026
SEED_MONTH = 3   # March
MONTH_LABEL = f"{month_name[SEED_MONTH]} {SEED_YEAR}"


# ── Helpers ───────────────────────────────────────────────────────────────────
def _write_local(s3_key: str, content: bytes) -> None:
    path = os.path.join(LOCAL_STORE, s3_key.replace("/", os.sep))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(content)
    print(f"  [local] wrote {path}")


def _s3_key(region_code: str, year: int, month: int, control_id: str, filename: str) -> str:
    return f"BIC/KRI/{region_code}/{year}/{month:02d}/Evidences/TEMP/{control_id}/COMMON/{filename}"


def _email_key(region_code: str, year: int, month: int, control_id: str,
               task_id: str, iteration: int, ts_str: str, action_slug: str) -> str:
    base = f"BIC/KRI/{region_code}/{year}/{month:02d}/Evidences/TEMP/{control_id}/COMMON"
    return f"{base}/task-{task_id}/iter-{iteration}/email-{ts_str}-{action_slug}.eml"


def _eml(subject: str, from_addr: str, to_addr: str, body: str, dt: datetime) -> bytes:
    date_str = dt.strftime("%a, %d %b %Y %H:%M:%S +0000")
    return (
        f"From: {from_addr}\r\nTo: {to_addr}\r\nSubject: {subject}\r\n"
        f"Date: {date_str}\r\nMIME-Version: 1.0\r\n"
        f"Content-Type: text/plain; charset=utf-8\r\n\r\n{body}\r\n"
    ).encode("utf-8")


def _resolve_ctx(kri: KriMaster, db) -> dict:
    region_code = kri.region.region_code if kri.region else "UK"
    bs = db.query(KriBluesheet).filter(KriBluesheet.kri_id == kri.kri_id).first()
    control_id = "COMMON"
    if bs and bs.control_ids:
        control_id = bs.control_ids.split(",")[0].strip() or "COMMON"
    return {"region_code": region_code, "control_id": control_id}


# ── Main ──────────────────────────────────────────────────────────────────────
def seed():
    # Ensure tables exist
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        kris = db.query(KriMaster).filter(KriMaster.is_active == True).limit(3).all()
        if not kris:
            print("No active KRIs found. Run the main app first to create some, or check seed_users.py.")
            return

        print(f"Seeding evidence for {len(kris)} KRI(s): {[k.kri_code for k in kris]}\n")

        for kri in kris:
            # Skip if already seeded for this period
            existing = (
                db.query(KriEvidenceMetadata)
                .filter(
                    KriEvidenceMetadata.kri_id == kri.kri_id,
                    KriEvidenceMetadata.period_year == SEED_YEAR,
                    KriEvidenceMetadata.period_month == SEED_MONTH,
                )
                .first()
            )
            if existing:
                print(f"  KRI-{kri.kri_id} ({kri.kri_code}): already has evidence for {MONTH_LABEL}, skipping.")
                continue

            print(f"\n>>> KRI-{kri.kri_id} ({kri.kri_code}) - {kri.kri_name}")

            ctx = _resolve_ctx(kri, db)
            rc = ctx["region_code"]
            cid = ctx["control_id"]

            # ── Base timestamps ────────────────────────────────────────────────
            t0 = datetime(SEED_YEAR, SEED_MONTH, 5, 9, 0, 0)   # day 5 = initial upload
            t1 = datetime(SEED_YEAR, SEED_MONTH, 5, 9, 30, 0)  # auto run
            t2 = datetime(SEED_YEAR, SEED_MONTH, 5, 10, 0, 0)  # iter-1 email out
            t3 = datetime(SEED_YEAR, SEED_MONTH, 6, 11, 0, 0)  # iter-1 email reply
            t4 = datetime(SEED_YEAR, SEED_MONTH, 8, 14, 0, 0)  # iter-2 email out (rework)
            t5 = datetime(SEED_YEAR, SEED_MONTH, 10, 9, 0, 0)  # second manual

            # ── 1. Manual file — PDF ───────────────────────────────────────────
            fn1 = f"20260305_090000_{kri.kri_code}_Evidence_Q1.pdf"
            key1 = _s3_key(rc, SEED_YEAR, SEED_MONTH, cid, fn1)
            _write_local(key1, b"%PDF-1.4 sample evidence content for " + kri.kri_code.encode())
            meta1 = KriEvidenceMetadata(
                kri_id=kri.kri_id, control_id=cid, region_code=rc,
                period_year=SEED_YEAR, period_month=SEED_MONTH,
                evidence_type="manual", file_name=fn1, s3_object_path=key1,
                notes="Q1 supporting evidence — threshold validation",
                created_by="SYSTEM", updated_by="SYSTEM",
                created_dt=t0, updated_dt=t0,
            )
            db.add(meta1)
            print(f"  + manual PDF  ->{key1}")

            # ── 2. Manual file — XLSX ──────────────────────────────────────────
            fn2 = f"20260310_090000_{kri.kri_code}_DataExtract.xlsx"
            key2 = _s3_key(rc, SEED_YEAR, SEED_MONTH, cid, fn2)
            _write_local(key2, b"PK\x03\x04" + b"\x00" * 100 + b"XLSX stub " + kri.kri_code.encode())
            meta2 = KriEvidenceMetadata(
                kri_id=kri.kri_id, control_id=cid, region_code=rc,
                period_year=SEED_YEAR, period_month=SEED_MONTH,
                evidence_type="manual", file_name=fn2, s3_object_path=key2,
                notes="Raw data extract from source system",
                created_by="SYSTEM", updated_by="SYSTEM",
                created_dt=t5, updated_dt=t5,
            )
            db.add(meta2)
            print(f"  + manual XLSX ->{key2}")

            # ── 3. Auto evidence ───────────────────────────────────────────────
            fn3 = f"auto_{kri.kri_code}_{SEED_YEAR}{SEED_MONTH:02d}_metrics.csv"
            key3 = _s3_key(rc, SEED_YEAR, SEED_MONTH, cid, fn3)
            csv_content = (
                f"kri_id,period,value,threshold,rag_status\n"
                f"{kri.kri_id},{SEED_YEAR}-{SEED_MONTH:02d},82,75,GREEN\n"
            ).encode()
            _write_local(key3, csv_content)
            meta3 = KriEvidenceMetadata(
                kri_id=kri.kri_id, control_id=cid, region_code=rc,
                period_year=SEED_YEAR, period_month=SEED_MONTH,
                evidence_type="auto", file_name=fn3, s3_object_path=key3,
                notes="Automated metric extraction via scheduler",
                created_by="SYSTEM", updated_by="SYSTEM",
                created_dt=t1, updated_dt=t1,
            )
            db.add(meta3)
            print(f"  + auto   CSV  ->{key3}")

            # ── 4. Outbound email — Iter-1 (L1 Approved) ──────────────────────
            ts2_str = t2.strftime("%Y%m%d%H%M%S")
            subj_iter1 = f"KRI-{kri.kri_id} [{MONTH_LABEL}] | Iter-1 | L1 Approved"
            eml1_key = _email_key(rc, SEED_YEAR, SEED_MONTH, cid, "a1b2c3d4", 1, ts2_str, "l1_approved")
            eml1_body = _eml(
                subject=subj_iter1,
                from_addr="dl.bic.metrics@company.com",
                to_addr="data.provider@company.com",
                body=(
                    f"Dear Data Provider,\n\n"
                    f"KRI {kri.kri_code} — {kri.kri_name} has been approved at L1.\n"
                    f"Period: {MONTH_LABEL} | Iteration: 1\n\n"
                    f"Please review and provide confirmation.\n\n"
                    f"BIC Data Metrics Team"
                ),
                dt=t2,
            )
            _write_local(eml1_key, eml1_body)
            meta4 = KriEvidenceMetadata(
                kri_id=kri.kri_id, control_id=cid, region_code=rc,
                period_year=SEED_YEAR, period_month=SEED_MONTH, iteration=1,
                evidence_type="email", action="L1 Approved",
                sender="dl.bic.metrics@company.com",
                receiver="data.provider@company.com",
                file_name=f"email-{ts2_str}-l1_approved.eml",
                s3_object_path=eml1_key, email_uuid="a1b2c3d4",
                created_by="SYSTEM", updated_by="SYSTEM",
                created_dt=t2, updated_dt=t2,
            )
            db.add(meta4)
            print(f"  + outbound eml Iter-1 ->{eml1_key}")

            # ── 5. Inbound email reply — Iter-1 ───────────────────────────────
            ts3_str = t3.strftime("%Y%m%d%H%M%S")
            eml2_key = _email_key(rc, SEED_YEAR, SEED_MONTH, cid, "e5f6g7h8", 1, ts3_str, "inbound")
            eml2_body = _eml(
                subject=f"Re: {subj_iter1}",
                from_addr="data.provider@company.com",
                to_addr="dl.bic.metrics@company.com",
                body="Acknowledged. Data confirmed as per attached extract.",
                dt=t3,
            )
            _write_local(eml2_key, eml2_body)
            meta5 = KriEvidenceMetadata(
                kri_id=kri.kri_id, control_id=cid, region_code=rc,
                period_year=SEED_YEAR, period_month=SEED_MONTH, iteration=1,
                evidence_type="email", action="INBOUND",
                sender="data.provider@company.com",
                receiver="dl.bic.metrics@company.com",
                file_name=f"email-{ts3_str}-inbound.eml",
                s3_object_path=eml2_key, email_uuid="e5f6g7h8",
                created_by="SYSTEM", updated_by="SYSTEM",
                created_dt=t3, updated_dt=t3,
            )
            db.add(meta5)
            print(f"  + inbound  eml Iter-1 ->{eml2_key}")

            # ── 6. Outbound email — Iter-2 (Rework Required) ──────────────────
            ts4_str = t4.strftime("%Y%m%d%H%M%S")
            subj_iter2 = f"KRI-{kri.kri_id} [{MONTH_LABEL}] | Iter-2 | Rework Required"
            eml3_key = _email_key(rc, SEED_YEAR, SEED_MONTH, cid, "i9j0k1l2", 2, ts4_str, "rework_required")
            eml3_body = _eml(
                subject=subj_iter2,
                from_addr="dl.bic.metrics@company.com",
                to_addr="data.provider@company.com, l2.approver@company.com",
                body=(
                    f"Dear Team,\n\n"
                    f"KRI {kri.kri_code} requires rework for {MONTH_LABEL}.\n"
                    f"Please review the threshold rationale and resubmit.\n\n"
                    f"BIC Data Metrics Team"
                ),
                dt=t4,
            )
            _write_local(eml3_key, eml3_body)
            meta6 = KriEvidenceMetadata(
                kri_id=kri.kri_id, control_id=cid, region_code=rc,
                period_year=SEED_YEAR, period_month=SEED_MONTH, iteration=2,
                evidence_type="email", action="Rework Required",
                sender="dl.bic.metrics@company.com",
                receiver="data.provider@company.com, l2.approver@company.com",
                file_name=f"email-{ts4_str}-rework_required.eml",
                s3_object_path=eml3_key, email_uuid="i9j0k1l2",
                created_by="SYSTEM", updated_by="SYSTEM",
                created_dt=t4, updated_dt=t4,
            )
            db.add(meta6)
            print(f"  + outbound eml Iter-2 ->{eml3_key}")

            # ── Email Iteration record ─────────────────────────────────────────
            iter_row = (
                db.query(KriEmailIteration)
                .filter(
                    KriEmailIteration.kri_id == kri.kri_id,
                    KriEmailIteration.period_year == SEED_YEAR,
                    KriEmailIteration.period_month == SEED_MONTH,
                )
                .first()
            )
            if not iter_row:
                iter_row = KriEmailIteration(
                    kri_id=kri.kri_id,
                    period_year=SEED_YEAR,
                    period_month=SEED_MONTH,
                    current_iter=2,
                )
                db.add(iter_row)
                print(f"  + iteration counter ->current_iter=2")

            # ── Audit Summary record ───────────────────────────────────────────
            existing_summary = (
                db.query(KriAuditSummary)
                .filter(
                    KriAuditSummary.kri_id == kri.kri_id,
                    KriAuditSummary.period_year == SEED_YEAR,
                    KriAuditSummary.period_month == SEED_MONTH,
                )
                .first()
            )
            if not existing_summary:
                summary_key = (
                    f"BIC/KRI/{rc}/{SEED_YEAR}/{SEED_MONTH:02d}"
                    f"/Evidences/TEMP/{cid}/COMMON/summary.html"
                )
                # Write a minimal placeholder HTML
                html_stub = f"""<!DOCTYPE html>
<html><head><title>Audit Summary KRI-{kri.kri_id}</title></head>
<body><h1>KRI-{kri.kri_id} [{MONTH_LABEL}]</h1>
<p>Placeholder summary — regenerate via the UI (L3 button).</p>
</body></html>"""
                _write_local(summary_key, html_stub.encode())
                summary_row = KriAuditSummary(
                    kri_id=kri.kri_id,
                    period_year=SEED_YEAR,
                    period_month=SEED_MONTH,
                    s3_path=summary_key,
                    generated_dt=datetime.utcnow(),
                    l3_approver_name="Seed Script",
                    final_status="APPROVED",
                    total_iterations=2,
                    total_evidences=6,
                    total_emails=3,
                )
                db.add(summary_row)
                print(f"  + audit summary  ->{summary_key}")

        db.commit()
        print("\n[OK] Seed complete.")

    finally:
        db.close()

    # ── Dev email log stubs ───────────────────────────────────────────────────
    os.makedirs(EMAIL_LOG_DIR, exist_ok=True)
    samples = [
        {
            "uuid": "a1b2c3d4-0000-0000-0000-seed000000001",
            "subject": f"KRI-1 [{MONTH_LABEL}] | Iter-1 | L1 Approved",
            "to": ["data.provider@company.com"],
            "from": "dl.bic.metrics@company.com",
            "kri_id": 1, "kri_code": "UK-KRI-001",
            "period": MONTH_LABEL, "iteration": 1, "action": "L1 Approved",
            "sent_at": f"{SEED_YEAR}-{SEED_MONTH:02d}-05T10:00:00",
        },
        {
            "uuid": "i9j0k1l2-0000-0000-0000-seed000000002",
            "subject": f"KRI-1 [{MONTH_LABEL}] | Iter-2 | Rework Required",
            "to": ["data.provider@company.com", "l2.approver@company.com"],
            "from": "dl.bic.metrics@company.com",
            "kri_id": 1, "kri_code": "UK-KRI-001",
            "period": MONTH_LABEL, "iteration": 2, "action": "Rework Required",
            "sent_at": f"{SEED_YEAR}-{SEED_MONTH:02d}-08T14:00:00",
        },
    ]
    for s in samples:
        fname = f"{s['sent_at'].replace(':', '').replace('-', '')[:15]}_KRI-{s['kri_id']}.json"
        fpath = os.path.join(EMAIL_LOG_DIR, fname)
        if not os.path.exists(fpath):
            with open(fpath, "w") as f:
                json.dump(s, f, indent=2)
            print(f"  [email-log] wrote {fname}")

    print(f"\nDev email log: {EMAIL_LOG_DIR}")
    print(f"Local store:   {LOCAL_STORE}")
    print(f"\nValidation endpoints:")
    print(f"  GET  /api/audit-evidence/kris          ->should show seeded KRIs with evidence_count > 0")
    print(f"  GET  /api/audit-evidence?kri_id=<id>   ->list evidence rows")
    print(f"  GET  /api/audit-evidence/dev/email-log ->inspect mocked emails")
    print(f"  GET  /api/audit-evidence/<id>/summary  ->audit summary record")
    print(f"  GET  /api/audit-evidence/local-download?key=<s3_key>  ->download local file")


if __name__ == "__main__":
    seed()
