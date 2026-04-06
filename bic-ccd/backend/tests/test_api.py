"""Backend API tests for BIC-CCD."""
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def _token(soe="SYSADMIN"):
    r = client.post("/api/auth/login", json={"soe_id": soe, "password": "demo"})
    return r.json()["access_token"]

def _auth(soe="SYSADMIN"):
    return {"Authorization": f"Bearer {_token(soe)}"}


class TestHealth:
    def test_health(self):
        r = client.get("/health")
        assert r.status_code == 200
        assert r.json()["status"] == "healthy"


class TestAuth:
    def test_login_valid(self):
        r = client.post("/api/auth/login", json={"soe_id": "RANREDDY", "password": "demo"})
        assert r.status_code == 200
        assert "access_token" in r.json()
        assert r.json()["user"]["soe_id"] == "RANREDDY"

    def test_login_invalid(self):
        r = client.post("/api/auth/login", json={"soe_id": "NOPE", "password": "x"})
        assert r.status_code == 401

    def test_me_no_token(self):
        assert client.get("/api/auth/me").status_code in (401, 403)

    def test_me_with_token(self):
        r = client.get("/api/auth/me", headers=_auth())
        assert r.status_code == 200


class TestLookups:
    def test_regions(self):
        r = client.get("/api/lookups/regions", headers=_auth())
        assert r.status_code == 200
        assert len(r.json()) == 3

    def test_categories(self):
        r = client.get("/api/lookups/categories", headers=_auth())
        assert r.status_code == 200
        assert len(r.json()) >= 5

    def test_dimensions(self):
        r = client.get("/api/lookups/dimensions", headers=_auth())
        assert r.status_code == 200
        assert len(r.json()) == 7


class TestDashboard:
    def test_summary(self):
        r = client.get("/api/dashboard/summary", headers=_auth("RANREDDY"))
        assert r.status_code == 200
        d = r.json()
        assert "total_kris" in d and "sla_met" in d and "pending_approvals" in d

    def test_trend(self):
        r = client.get("/api/dashboard/trend?months=6", headers=_auth("RANREDDY"))
        assert r.status_code == 200
        assert len(r.json()) == 6

    def test_dimension_breakdown(self):
        r = client.get("/api/dashboard/dimension-breakdown", headers=_auth("RANREDDY"))
        assert r.status_code == 200


class TestKRIs:
    def test_list(self):
        r = client.get("/api/kris", headers=_auth())
        assert r.status_code == 200
        assert r.json()["total"] == 24

    def test_get(self):
        r = client.get("/api/kris/1", headers=_auth())
        assert r.status_code == 200
        assert r.json()["kri_id"] == 1


class TestRoleAuthorization:
    def test_admin_required(self):
        r = client.get("/api/users", headers=_auth("RANREDDY"))  # Management, not Admin
        assert r.status_code == 403

    def test_admin_allowed(self):
        r = client.get("/api/users", headers=_auth("SYSADMIN"))
        assert r.status_code == 200
        assert r.json()["total"] == 7

    def test_approver_access(self):
        r = client.get("/api/maker-checker/pending?level=L1", headers=_auth("JSMITH01"))
        assert r.status_code == 200


class TestNotifications:
    def test_list(self):
        r = client.get("/api/notifications", headers=_auth())
        assert r.status_code == 200

    def test_count(self):
        r = client.get("/api/notifications/count", headers=_auth())
        assert r.status_code == 200
        assert "count" in r.json()
