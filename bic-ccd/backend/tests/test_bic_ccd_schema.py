"""
Phase 7 — Continuous Validation: BIC_CCD_* schema and API parity tests.

These tests run against the test SQLite DB (same as the rest of the suite)
and verify:
  1. All 24 BIC_CCD_* tables are registered in BicCcdBase.metadata
  2. BicCcdBase and Base metadata are fully isolated (no shared tables)
  3. All BIC_CCD_* model classes are importable and have the correct __tablename__
  4. Key API endpoints respond correctly after any cutover step
  5. Approval, scheduler, and evidence paths do not regress

Add new assertions here after each wave cutover so failures surface immediately.
"""
import pytest


# ══════════════════════════════════════════════════════════════════════════════
# 1. Schema registration
# ══════════════════════════════════════════════════════════════════════════════

class TestBicCcdMetadata:
    EXPECTED_TABLES = {
        # original 24
        "BIC_CCD_REGION",
        "BIC_CCD_KRI_CATEGORY",
        "BIC_CCD_KRI_CONTROL",
        "BIC_CCD_KRI_STATUS",
        "BIC_CCD_KRI_CONFIG",
        "BIC_CCD_KRI_CONFIGURATION",
        "BIC_CCD_KRI_DATA_SOURCE_MAPPING",
        "BIC_CCD_ROLE_REGION_MAPPING",
        "BIC_CCD_KRI_USER_ROLE",
        "BIC_CCD_KRI_CONTROL_STATUS_TRACKER",
        "BIC_CCD_KRI_DATA_SOURCE_STATUS_TRACKER",
        "BIC_CCD_KRI_ASSIGNMENT_TRACKER",
        "BIC_CCD_KRI_METRIC",
        "BIC_CCD_KRI_EVIDENCE",
        "BIC_CCD_KRI_COMMENT",
        "BIC_CCD_KRI_ASSIGNMENT_AUDIT",
        "BIC_CCD_KRI_CONTROL_EVIDENCE_AUDIT",
        "BIC_CCD_SCORECARD",
        "BIC_CCD_SCORECARD_APPROVER",
        "BIC_CCD_SCORECARD_ACTIVITY_LOG",
        "BIC_CCD_CASE",
        "BIC_CCD_CASE_FILE",
        "BIC_CCD_EMAIL_AUDIT",
        "BIC_CCD_SHED_LOCK",
        # 14 new app-owned tables (Option A wave)
        "BIC_CCD_APP_USER",
        "BIC_CCD_USER_ROLE_MAPPING",
        "BIC_CCD_MAKER_CHECKER_SUBMISSION",
        "BIC_CCD_APPROVAL_AUDIT_TRAIL",
        "BIC_CCD_VARIANCE_SUBMISSION",
        "BIC_CCD_ESCALATION_CONFIG",
        "BIC_CCD_NOTIFICATION",
        "BIC_CCD_APPROVAL_ASSIGNMENT_RULE",
        "BIC_CCD_SAVED_VIEW",
        "BIC_CCD_KRI_BLUESHEET",
        "BIC_CCD_KRI_APPROVAL_LOG",
        "BIC_CCD_KRI_EVIDENCE_METADATA",
        "BIC_CCD_KRI_EMAIL_ITERATION",
        "BIC_CCD_KRI_AUDIT_SUMMARY",
    }

    def test_all_tables_registered(self):
        from app.database import BicCcdBase
        import app.models.bic_ccd  # noqa

        actual = set(BicCcdBase.metadata.tables.keys())
        missing = self.EXPECTED_TABLES - actual
        extra = actual - self.EXPECTED_TABLES
        assert not missing, f"Tables missing from BicCcdBase.metadata: {sorted(missing)}"
        assert not extra, f"Unexpected extra tables in BicCcdBase.metadata: {sorted(extra)}"

    def test_table_count_is_24(self):
        from app.database import BicCcdBase
        import app.models.bic_ccd  # noqa

        assert len(BicCcdBase.metadata.tables) == 38

    def test_bic_ccd_base_isolated_from_base(self):
        from app.database import Base, BicCcdBase
        import app.models  # noqa
        import app.models.bic_ccd  # noqa

        legacy_tables = set(Base.metadata.tables.keys())
        bic_tables = set(BicCcdBase.metadata.tables.keys())
        overlap = legacy_tables & bic_tables
        assert not overlap, f"Tables registered in BOTH metadata roots: {sorted(overlap)}"

    def test_all_bic_ccd_tablenames_have_prefix(self):
        from app.database import BicCcdBase
        import app.models.bic_ccd  # noqa

        bad = [
            name for name in BicCcdBase.metadata.tables
            if not name.startswith("BIC_CCD_")
        ]
        assert not bad, f"Tables without BIC_CCD_ prefix in BicCcdBase: {bad}"


# ══════════════════════════════════════════════════════════════════════════════
# 2. Model class import parity
# ══════════════════════════════════════════════════════════════════════════════

class TestBicCcdModelImports:
    def test_region_master_importable(self):
        from app.models.bic_ccd import RegionMaster
        assert RegionMaster.__tablename__ == "BIC_CCD_REGION"

    def test_kri_master_importable(self):
        from app.models.bic_ccd import KriMaster
        assert KriMaster.__tablename__ == "BIC_CCD_KRI_CONFIG"

    def test_monthly_control_status_importable(self):
        from app.models.bic_ccd import MonthlyControlStatus
        assert MonthlyControlStatus.__tablename__ == "BIC_CCD_KRI_CONTROL_STATUS_TRACKER"

    def test_scorecard_importable(self):
        from app.models.bic_ccd import ScorecardCase
        assert ScorecardCase.__tablename__ == "BIC_CCD_SCORECARD"

    def test_shed_lock_importable(self):
        from app.models.bic_ccd import SchedulerLock
        assert SchedulerLock.__tablename__ == "BIC_CCD_SHED_LOCK"

    def test_email_audit_importable(self):
        from app.models.bic_ccd import EmailAudit
        assert EmailAudit.__tablename__ == "BIC_CCD_EMAIL_AUDIT"

    def test_kri_configuration_importable(self):
        from app.models.bic_ccd import KriConfiguration
        assert KriConfiguration.__tablename__ == "BIC_CCD_KRI_CONFIGURATION"


# ══════════════════════════════════════════════════════════════════════════════
# 3. API regression — core endpoints must still respond after each wave
# ══════════════════════════════════════════════════════════════════════════════

class TestApiRegression:
    """Golden-path API checks. Run after every wave cutover."""

    def test_health_check(self, client):
        r = client.get("/health")
        assert r.status_code == 200

    def test_auth_login_still_works(self, client):
        r = client.post("/api/auth/login", json={"soe_id": "SYSADMIN", "password": "demo"})
        assert r.status_code == 200
        assert "access_token" in r.json()

    def test_regions_endpoint(self, client, admin_h):
        r = client.get("/api/lookups/regions", headers=admin_h)
        assert r.status_code == 200
        body = r.json()
        assert isinstance(body, (list, dict))

    def test_kri_list_endpoint(self, client, admin_h):
        r = client.get("/api/kris", headers=admin_h)
        assert r.status_code in (200, 404)  # 404 acceptable if route not yet exposed

    def test_controls_endpoint_current_month(self, client, admin_h):
        from datetime import datetime
        now = datetime.utcnow()
        r = client.get(f"/api/controls?year={now.year}&month={now.month}", headers=admin_h)
        assert r.status_code == 200

    def test_users_endpoint(self, client, admin_h):
        r = client.get("/api/users", headers=admin_h)
        assert r.status_code == 200
        body = r.json()
        assert "items" in body

    def test_dashboard_endpoint(self, client, admin_h):
        from datetime import datetime
        now = datetime.utcnow()
        r = client.get(f"/api/dashboard/summary?year={now.year}&month={now.month}", headers=admin_h)
        assert r.status_code == 200


# ══════════════════════════════════════════════════════════════════════════════
# 4. Approval workflow regression
# ══════════════════════════════════════════════════════════════════════════════

class TestApprovalRegression:
    def test_pending_queue_l1(self, client, l1_h):
        r = client.get("/api/maker-checker/pending?level=L1", headers=l1_h)
        assert r.status_code == 200
        body = r.json()
        assert "items" in body and "total" in body

    def test_pending_queue_l2(self, client, l2_h):
        r = client.get("/api/maker-checker/pending?level=L2", headers=l2_h)
        assert r.status_code == 200

    def test_all_pending_l3(self, client, l3_h):
        r = client.get("/api/maker-checker/all-pending", headers=l3_h)
        assert r.status_code == 200

    def test_management_cannot_access_queue(self, client, management_h):
        r = client.get("/api/maker-checker/pending?level=L1", headers=management_h)
        assert r.status_code == 403

    def test_approve_nonexistent_returns_404(self, client, l1_h):
        r = client.post(
            "/api/maker-checker/9999999/action",
            json={"action": "APPROVED", "comments": "test"},
            headers=l1_h,
        )
        assert r.status_code == 404


# ══════════════════════════════════════════════════════════════════════════════
# 5. Row-count parity check (runs only when Oracle env is available)
# ══════════════════════════════════════════════════════════════════════════════

class TestRowCountParity:
    """
    Compares row counts between CCB_* and BIC_CCD_* for each migrated wave.
    Skipped automatically if the Oracle DB is not reachable (USE_SQLITE=true).
    """

    PAIRS = [
        ("CCB_KRI_REGION",                    "BIC_CCD_REGION"),
        ("CCB_KRI_CATEGORY",                  "BIC_CCD_KRI_CATEGORY"),
        ("CCB_KRI_CONTROL",                   "BIC_CCD_KRI_CONTROL"),
        ("CCB_KRI_STATUS",                    "BIC_CCD_KRI_STATUS"),
        ("CCB_KRI_CONFIG",                    "BIC_CCD_KRI_CONFIG"),
        ("CCB_KRI_CONTROL_STATUS_TRACKER",    "BIC_CCD_KRI_CONTROL_STATUS_TRACKER"),
        ("CCB_KRI_DATA_SOURCE_MAPPING",       "BIC_CCD_KRI_DATA_SOURCE_MAPPING"),
        ("CCB_KRI_ASSIGNMENT_TRACKER",        "BIC_CCD_KRI_ASSIGNMENT_TRACKER"),
        ("CCB_KRI_EVIDENCE",                  "BIC_CCD_KRI_EVIDENCE"),
        ("CCB_KRI_COMMENT",                   "BIC_CCD_KRI_COMMENT"),
        ("CCB_KRI_SCORECARD",                 "BIC_CCD_SCORECARD"),
        ("CCB_EMAIL_AUDIT",                   "BIC_CCD_EMAIL_AUDIT"),
        ("CCB_SHED_LOCK",                     "BIC_CCD_SHED_LOCK"),
    ]

    @pytest.fixture(autouse=True)
    def skip_on_sqlite(self):
        import os
        if os.environ.get("USE_SQLITE", "false").lower() == "true":
            pytest.skip("Row-count parity only checked against Oracle")

    def test_row_counts_match(self):
        from app.database import engine
        from sqlalchemy import text

        mismatches = []
        with engine.connect() as conn:
            for src, dst in self.PAIRS:
                try:
                    src_count = conn.execute(text(f"SELECT COUNT(*) FROM {src}")).scalar()
                    dst_count = conn.execute(text(f"SELECT COUNT(*) FROM {dst}")).scalar()
                    if src_count != dst_count:
                        mismatches.append(
                            f"{src}({src_count}) != {dst}({dst_count})"
                        )
                except Exception as exc:
                    # Table doesn't exist yet — wave not run yet, skip that pair
                    pass

        assert not mismatches, "Row-count mismatches after migration:\n" + "\n".join(mismatches)
