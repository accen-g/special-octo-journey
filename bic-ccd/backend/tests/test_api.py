"""
Integration tests — API layer.

Covers: health, auth, lookups, dashboard, KRIs, role-based access,
notifications.  Uses the session-scoped `client` and role header
fixtures from conftest.py.
"""
import os
import pytest

# BIC_CCD_* tables start empty (manual Oracle population); skip data-count tests.
_BIC_CCD_MODE = os.environ.get("USE_BIC_CCD_TABLES", "false").lower() == "true"
_skip_empty = pytest.mark.skipif(
    _BIC_CCD_MODE,
    reason="BIC_CCD_* lookup/KRI tables are empty until manually populated in Oracle",
)


# ═══════════════════════════════════════════════════════
# A. Health / startup
# ═══════════════════════════════════════════════════════

class TestHealth:
    def test_health_ok(self, client):
        r = client.get("/health")
        assert r.status_code == 200
        assert r.json()["status"] == "healthy"

    def test_docs_accessible(self, client):
        r = client.get("/api/docs")
        assert r.status_code == 200


# ═══════════════════════════════════════════════════════
# B. Authentication
# ═══════════════════════════════════════════════════════

class TestAuth:
    def test_login_sysadmin(self, client):
        r = client.post("/api/auth/login", json={"soe_id": "SYSADMIN", "password": "demo"})
        assert r.status_code == 200
        body = r.json()
        assert "access_token" in body
        assert body["user"]["soe_id"] == "SYSADMIN"

    def test_login_data_provider(self, client):
        r = client.post("/api/auth/login", json={"soe_id": "GD24043", "password": "demo"})
        assert r.status_code == 200
        assert "access_token" in r.json()

    def test_login_unknown_user(self, client):
        r = client.post("/api/auth/login", json={"soe_id": "NOBODY", "password": "x"})
        assert r.status_code == 401

    def test_me_without_token(self, client):
        r = client.get("/api/auth/me")
        assert r.status_code == 401

    def test_me_with_token(self, client, admin_h):
        r = client.get("/api/auth/me", headers=admin_h)
        assert r.status_code == 200
        assert r.json()["soe_id"] == "SYSADMIN"

    def test_me_with_bad_token(self, client):
        r = client.get("/api/auth/me", headers={"Authorization": "Bearer totally.invalid.jwt"})
        assert r.status_code == 401


# ═══════════════════════════════════════════════════════
# C. Lookups
# ═══════════════════════════════════════════════════════

@_skip_empty
class TestLookups:
    def test_regions_count(self, client, admin_h):
        r = client.get("/api/lookups/regions", headers=admin_h)
        assert r.status_code == 200
        assert len(r.json()) == 3

    def test_regions_structure(self, client, admin_h):
        r = client.get("/api/lookups/regions", headers=admin_h)
        first = r.json()[0]
        assert "region_id" in first
        assert "region_name" in first

    def test_categories_minimum_count(self, client, admin_h):
        r = client.get("/api/lookups/categories", headers=admin_h)
        assert r.status_code == 200
        assert len(r.json()) >= 5

    def test_dimensions_count(self, client, admin_h):
        r = client.get("/api/lookups/dimensions", headers=admin_h)
        assert r.status_code == 200
        assert len(r.json()) == 7

    def test_statuses_contains_core(self, client, admin_h):
        r = client.get("/api/lookups/statuses", headers=admin_h)
        assert r.status_code == 200
        names = {s["status_name"] for s in r.json()}
        for expected in ("NOT_STARTED", "IN_PROGRESS", "APPROVED", "SLA_BREACHED"):
            assert expected in names


# ═══════════════════════════════════════════════════════
# D. Dashboard
# ═══════════════════════════════════════════════════════

class TestDashboard:
    def test_summary_shape(self, client, admin_h):
        r = client.get("/api/dashboard/summary", headers=admin_h)
        assert r.status_code == 200
        d = r.json()
        for key in ("total_kris", "sla_met", "pending_approvals", "sla_breached"):
            assert key in d, f"Missing key: {key}"

    def test_summary_management_allowed(self, client, management_h):
        r = client.get("/api/dashboard/summary", headers=management_h)
        assert r.status_code == 200

    def test_trend_six_months(self, client, admin_h):
        r = client.get("/api/dashboard/trend?months=6", headers=admin_h)
        assert r.status_code == 200
        assert len(r.json()) == 6

    def test_trend_three_months(self, client, admin_h):
        r = client.get("/api/dashboard/trend?months=3", headers=admin_h)
        assert r.status_code == 200
        assert len(r.json()) == 3

    def test_dimension_breakdown(self, client, admin_h):
        r = client.get("/api/dashboard/dimension-breakdown", headers=admin_h)
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_summary_region_filter(self, client, admin_h):
        r = client.get("/api/dashboard/summary?region_id=1", headers=admin_h)
        assert r.status_code == 200


# ═══════════════════════════════════════════════════════
# E. KRI Master
# ═══════════════════════════════════════════════════════

class TestKRIs:
    @_skip_empty
    def test_list_total(self, client, admin_h):
        r = client.get("/api/kris", headers=admin_h)
        assert r.status_code == 200
        assert r.json()["total"] == 24

    def test_list_pagination(self, client, admin_h):
        r = client.get("/api/kris?page=1&page_size=10", headers=admin_h)
        assert r.status_code == 200
        body = r.json()
        assert len(body["items"]) <= 10

    @_skip_empty
    def test_get_kri_by_id(self, client, admin_h):
        r = client.get("/api/kris/1", headers=admin_h)
        assert r.status_code == 200
        assert r.json()["kri_id"] == 1

    def test_get_nonexistent_kri(self, client, admin_h):
        r = client.get("/api/kris/99999", headers=admin_h)
        assert r.status_code == 404

    def test_kri_requires_auth(self, client):
        r = client.get("/api/kris")
        assert r.status_code == 401


# ═══════════════════════════════════════════════════════
# F. Role-Based Access Control
# ═══════════════════════════════════════════════════════

class TestRBAC:
    def test_user_list_admin_allowed(self, client, admin_h):
        r = client.get("/api/users", headers=admin_h)
        assert r.status_code == 200
        assert r.json()["total"] == 7

    def test_user_list_management_forbidden(self, client, management_h):
        # MANAGEMENT role does not have 'admin' page access
        r = client.get("/api/users", headers=management_h)
        assert r.status_code == 403

    def test_user_list_data_provider_forbidden(self, client, dp_h):
        r = client.get("/api/users", headers=dp_h)
        assert r.status_code == 403

    def test_pending_approvals_l1_approver_allowed(self, client, l1_h):
        r = client.get("/api/maker-checker/pending?level=L1", headers=l1_h)
        assert r.status_code == 200

    def test_pending_approvals_l3_allowed(self, client, l3_h):
        r = client.get("/api/maker-checker/pending?level=L1", headers=l3_h)
        assert r.status_code == 200

    def test_pending_approvals_management_forbidden(self, client, management_h):
        # MANAGEMENT does not have 'approvals' page access
        r = client.get("/api/maker-checker/pending?level=L1", headers=management_h)
        assert r.status_code == 403

    def test_dashboard_data_provider_allowed(self, client, dp_h):
        r = client.get("/api/dashboard/summary", headers=dp_h)
        assert r.status_code == 200

    def test_admin_override_non_admin_forbidden(self, client, l1_h):
        r = client.post("/api/admin/controls/1/override",
                        json={"new_status": "APPROVED", "reason": "test"},
                        headers=l1_h)
        assert r.status_code == 403


# ═══════════════════════════════════════════════════════
# G. Notifications
# ═══════════════════════════════════════════════════════

class TestNotifications:
    def test_list_returns_200(self, client, admin_h):
        r = client.get("/api/notifications", headers=admin_h)
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_count_returns_count_key(self, client, admin_h):
        r = client.get("/api/notifications/count", headers=admin_h)
        assert r.status_code == 200
        assert "count" in r.json()

    def test_notifications_require_auth(self, client):
        r = client.get("/api/notifications")
        assert r.status_code == 401


# ═══════════════════════════════════════════════════════
# H. Monthly Control Status
# ═══════════════════════════════════════════════════════

class TestControlStatus:
    def test_list_controls_ok(self, client, admin_h):
        from datetime import datetime
        now = datetime.utcnow()
        r = client.get(
            f"/api/controls?year={now.year}&month={now.month}",
            headers=admin_h,
        )
        assert r.status_code == 200

    def test_controls_require_auth(self, client):
        r = client.get("/api/controls")
        assert r.status_code == 401


# ═══════════════════════════════════════════════════════
# I. Maker-Checker Queue
# ═══════════════════════════════════════════════════════

class TestMakerCheckerQueue:
    def test_pending_queue_structure(self, client, admin_h):
        r = client.get("/api/maker-checker/pending?level=L1", headers=admin_h)
        assert r.status_code == 200
        body = r.json()
        assert "items" in body
        assert "total" in body

    def test_queue_summary_admin(self, client, admin_h):
        r = client.get("/api/maker-checker/queue-summary", headers=admin_h)
        assert r.status_code == 200

    def test_all_pending_admin(self, client, admin_h):
        r = client.get("/api/maker-checker/all-pending", headers=admin_h)
        assert r.status_code == 200
        body = r.json()
        assert "items" in body and "total" in body

    def test_approval_history_l1(self, client, l1_h):
        r = client.get("/api/maker-checker/history?level=L1", headers=l1_h)
        assert r.status_code == 200
        body = r.json()
        assert "items" in body
