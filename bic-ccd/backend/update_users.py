"""
One-time script: replace old demo user records with the new user details.

Mapping applied:
  RANREDDY  → SA41230  | Shahzad Alam          | sa41230@company.com
  JSMITH01  → VR31849  | Vivek Avireddy        | vr31849@company.com
  ALEE02    → HK51214  | Hasmukh Katechiya     | hk51214@company.com
  BWILSON   → DH71298  | Dawn Higgs            | dh71298@company.com
  DPATEL    → GD24043  | Gayatri Deshmukh      | gd24043@company.com
  MKUMAR    → PT81286  | Paul Thirtle          | pt81286@company.com
  SYSADMIN  → SYSADMIN | System Admin          | admin@company.com

Only soe_id, full_name, and email are changed.  All other columns
(user_id, department, is_active, last_login_dt, etc.) and every
related table that references user_id (FK) are untouched.

Usage (from the backend/ directory):
    python update_users.py
    python update_users.py --dry-run     # preview without committing
"""

import argparse
import logging
import sys

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger(__name__)

# Mapping: old_soe_id → (new_soe_id, new_full_name, new_email)
USER_MAPPING = [
    ("RANREDDY", "SA41230",  "Shahzad Alam",       "sa41230@company.com"),
    ("JSMITH01", "VR31849",  "Vivek Avireddy",      "vr31849@company.com"),
    ("ALEE02",   "HK51214",  "Hasmukh Katechiya",   "hk51214@company.com"),
    ("BWILSON",  "DH71298",  "Dawn Higgs",          "dh71298@company.com"),
    ("DPATEL",   "GD24043",  "Gayatri Deshmukh",    "gd24043@company.com"),
    ("MKUMAR",   "PT81286",  "Paul Thirtle",        "pt81286@company.com"),
    ("SYSADMIN", "SYSADMIN", "System Admin",        "admin@company.com"),
]


def run_update(dry_run: bool = False) -> None:
    # Import inside function so the script can be run from any working directory
    # as long as the Python path includes the backend package.
    from app.database import SessionLocal
    from app.models import AppUser

    db = SessionLocal()
    try:
        updated = []
        skipped = []

        for old_soe, new_soe, new_name, new_email in USER_MAPPING:
            user = db.query(AppUser).filter(AppUser.soe_id == old_soe).first()
            if user is None:
                log.warning("User '%s' not found — skipping.", old_soe)
                skipped.append(old_soe)
                continue

            # Detect if anything actually needs changing
            changed_fields = {}
            if user.soe_id != new_soe:
                changed_fields["soe_id"] = (user.soe_id, new_soe)
            if user.full_name != new_name:
                changed_fields["full_name"] = (user.full_name, new_name)
            if user.email != new_email:
                changed_fields["email"] = (user.email, new_email)

            if not changed_fields:
                log.info("User '%s' already up-to-date — skipping.", old_soe)
                skipped.append(old_soe)
                continue

            log.info(
                "[%s] user_id=%d — changes: %s",
                "DRY-RUN" if dry_run else "UPDATE",
                user.user_id,
                {k: f"{v[0]!r} → {v[1]!r}" for k, v in changed_fields.items()},
            )

            if not dry_run:
                user.soe_id    = new_soe
                user.full_name = new_name
                user.email     = new_email

            updated.append(old_soe)

        if dry_run:
            log.info("DRY-RUN complete — no changes committed (%d to update, %d skipped).", len(updated), len(skipped))
            db.rollback()
        else:
            db.commit()
            log.info("Committed — %d user(s) updated, %d skipped.", len(updated), len(skipped))

    except Exception as exc:
        db.rollback()
        log.error("Update failed, transaction rolled back: %s", exc)
        raise
    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Update BIC-CCD demo user records.")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview changes without writing to the database.",
    )
    args = parser.parse_args()

    # Ensure the app package is importable when running from backend/
    import os
    sys.path.insert(0, os.path.dirname(__file__))

    run_update(dry_run=args.dry_run)
    sys.exit(0)
