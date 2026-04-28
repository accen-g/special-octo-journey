"""
Find best KRIs for approval flow testing.
Run from backend/ directory:  python scripts/find_test_kris.py
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app.database import SessionLocal
from app.models import (
    MakerCheckerSubmission, MonthlyControlStatus,
    KriMaster, ApprovalAuditTrail, RegionMaster
)
from sqlalchemy import func, and_, desc

def main():
    db = SessionLocal()
    try:
        # Latest submission per status_id
        latest_sub = (
            db.query(
                func.max(MakerCheckerSubmission.submission_id).label("max_id"),
                MakerCheckerSubmission.status_id,
            )
            .group_by(MakerCheckerSubmission.status_id)
            .subquery()
        )

        rows = (
            db.query(
                MakerCheckerSubmission,
                MonthlyControlStatus,
                KriMaster,
                RegionMaster,
            )
            .join(latest_sub, and_(
                MakerCheckerSubmission.submission_id == latest_sub.c.max_id,
                MakerCheckerSubmission.status_id == latest_sub.c.status_id,
            ))
            .join(MonthlyControlStatus, MakerCheckerSubmission.status_id == MonthlyControlStatus.status_id)
            .join(KriMaster, MonthlyControlStatus.kri_id == KriMaster.kri_id)
            .join(RegionMaster, KriMaster.region_id == RegionMaster.region_id)
            .filter(
                MakerCheckerSubmission.final_status.in_(["L1_PENDING", "L2_PENDING", "L3_PENDING"])
            )
            .order_by(MakerCheckerSubmission.final_status, KriMaster.kri_code)
            .all()
        )

        if not rows:
            print("No pending submissions found.")
            return

        # Check audit trail: count all actions per status_id
        status_ids = [mcs.status_id for _, mcs, *_ in rows]

        from sqlalchemy import func as sqlfunc
        audit_counts = (
            db.query(
                ApprovalAuditTrail.status_id,
                ApprovalAuditTrail.action,
                sqlfunc.count(ApprovalAuditTrail.audit_id).label("cnt")
            )
            .filter(ApprovalAuditTrail.status_id.in_(status_ids))
            .group_by(ApprovalAuditTrail.status_id, ApprovalAuditTrail.action)
            .all()
        )

        # Build per-status action summary
        from collections import defaultdict
        status_actions = defaultdict(dict)
        for sid, action, cnt in audit_counts:
            status_actions[sid][action] = cnt

        def classify(sid):
            actions = status_actions.get(sid, {})
            if not actions:
                return "VIRGIN (no audit trail)"
            has_dirty = any(a in actions for a in ["REWORK","REJECTED","L1_REWORK","L2_REWORK","L3_REWORK"])
            if has_dirty:
                return "NO (rework/reject history)"
            submit_count = actions.get("SUBMITTED", 0)
            prior_approvals = {k: v for k, v in actions.items() if k != "SUBMITTED"}
            if submit_count > 1 or prior_approvals:
                detail = ", ".join(f"{k}x{v}" for k, v in actions.items())
                return f"NO (prior history: {detail})"
            return "YES"

        # Print results grouped by level
        current_level = None
        for sub, mcs, kri, region in rows:
            level = sub.final_status.replace("_PENDING", "")

            if level != current_level:
                current_level = level
                print(f"\n{'='*60}")
                print(f"  {level} PENDING")
                print(f"{'='*60}")
                print(f"  {'KRI Code':<16} {'KRI Name':<35} {'Region':<10} {'Period':<10} {'Clean?'}")
                print(f"  {'-'*14} {'-'*33} {'-'*8} {'-'*8} {'-'*6}")

            flag = classify(mcs.status_id)
            print(f"  {kri.kri_code:<16} {kri.kri_name:<35} {region.region_code:<10} {mcs.period_year}-{mcs.period_month:02d}  {flag}")

        print(f"\n{'='*60}")
        print("  RECOMMENDATION")
        print(f"{'='*60}")

        clean_l1 = [(sub, mcs, kri) for sub, mcs, kri, _ in rows
                    if sub.final_status == "L1_PENDING" and classify(mcs.status_id) == "YES"]
        clean_l2 = [(sub, mcs, kri) for sub, mcs, kri, _ in rows
                    if sub.final_status == "L2_PENDING" and classify(mcs.status_id) == "YES"]
        clean_l3 = [(sub, mcs, kri) for sub, mcs, kri, _ in rows
                    if sub.final_status == "L3_PENDING" and classify(mcs.status_id) == "YES"]

        if clean_l1:
            s, m, k = clean_l1[0]
            print(f"  Full flow (L1>L2>L3): {k.kri_code} - {k.kri_name}  [submission_id={s.submission_id}]")
        if clean_l2:
            s, m, k = clean_l2[0]
            print(f"  L2>L3 only:           {k.kri_code} - {k.kri_name}  [submission_id={s.submission_id}]")
        if clean_l3:
            s, m, k = clean_l3[0]
            print(f"  L3 only:              {k.kri_code} - {k.kri_name}  [submission_id={s.submission_id}]")
        print()

    finally:
        db.close()

if __name__ == "__main__":
    main()
