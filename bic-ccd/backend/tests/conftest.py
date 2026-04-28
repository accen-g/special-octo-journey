"""
Pytest configuration for BIC-CCD test suite.

CRITICAL: env vars are set at module level BEFORE any app import so that
app/database.py creates its SQLAlchemy engine pointing at the test SQLite
file rather than the Oracle production URL.
"""
import os
import pathlib

# ── Test environment — set BEFORE any app import ───────────────────────────
_TEST_DB = str(pathlib.Path(__file__).parent / "test_bic_ccd.db")
os.environ["USE_SQLITE"]            = "true"
os.environ["SQLITE_URL"]            = f"sqlite:///{_TEST_DB}"
os.environ["USE_BIC_CCD_TABLES"]    = "true"
os.environ["JWT_SECRET"]         = "test-secret-key-bic-ccd"
os.environ["SCHEDULER_ENABLED"]  = "false"   # no background jobs during tests
os.environ["DEBUG"]              = "false"
os.environ["ENV"]                = "test"
os.environ["DEV_MOCK_EMAIL"]     = "true"
os.environ["DEV_MOCK_S3"]        = "true"

# Clear any cached settings from a previous import (lru_cache guard)
from app.config import get_settings
get_settings.cache_clear()

# Remove stale test DB so every session starts from a clean slate
_db_path = pathlib.Path(_TEST_DB)
if _db_path.exists():
    _db_path.unlink()

import pytest
from fastapi.testclient import TestClient


# ── Session fixtures ─────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def client():
    """One TestClient for the whole test session.

    Using it as a context manager triggers the FastAPI lifespan:
      - Base.metadata.create_all(bind=engine)  — creates all SQLite tables
      - seed_database()                         — populates demo data
    """
    from app.main import app
    with TestClient(app, raise_server_exceptions=True) as c:
        yield c


# ── Auth helpers ─────────────────────────────────────────────────────────────

def _login(client: TestClient, soe_id: str) -> str:
    r = client.post("/api/auth/login", json={"soe_id": soe_id, "password": "demo"})
    assert r.status_code == 200, f"Login failed for {soe_id}: {r.text}"
    return r.json()["access_token"]


def _h(client: TestClient, soe_id: str) -> dict:
    return {"Authorization": f"Bearer {_login(client, soe_id)}"}


# ── Role-scoped header fixtures ──────────────────────────────────────────────
# Seed users (from app/main.py seed_database):
#   SYSADMIN  → SYSTEM_ADMIN
#   SA41230   → MANAGEMENT
#   VR31849   → L1_APPROVER
#   HK51214   → L2_APPROVER
#   DH71298   → L3_ADMIN
#   GD24043   → DATA_PROVIDER
#   PT81286   → METRIC_OWNER

@pytest.fixture(scope="session")
def admin_h(client):
    return _h(client, "SYSADMIN")

@pytest.fixture(scope="session")
def management_h(client):
    return _h(client, "SA41230")

@pytest.fixture(scope="session")
def l1_h(client):
    return _h(client, "VR31849")

@pytest.fixture(scope="session")
def l2_h(client):
    return _h(client, "HK51214")

@pytest.fixture(scope="session")
def l3_h(client):
    return _h(client, "DH71298")

@pytest.fixture(scope="session")
def dp_h(client):
    return _h(client, "GD24043")

@pytest.fixture(scope="session")
def mo_h(client):
    return _h(client, "PT81286")
