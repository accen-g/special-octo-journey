"""Middleware: audit logging, request ID, auth dependency."""
import time
import uuid
import logging
from datetime import datetime, timedelta
from typing import Optional, List
from fastapi import Request, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from starlette.middleware.base import BaseHTTPMiddleware
import jwt

from app.config import get_settings
from app.database import get_db
from app.repositories import UserRepository

settings = get_settings()
logger = logging.getLogger("bic_ccd")
security = HTTPBearer(auto_error=False)


# ─── Request ID middleware ──────────────────────────────────
class RequestIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = str(uuid.uuid4())[:8]
        request.state.request_id = request_id
        start = time.time()
        response = await call_next(request)
        duration = round(time.time() - start, 3)
        response.headers["X-Request-Id"] = request_id
        logger.info(
            f"[{request_id}] {request.method} {request.url.path} "
            f"-> {response.status_code} ({duration}s)"
        )
        return response


# ─── Audit log middleware ───────────────────────────────────
class AuditLogMiddleware(BaseHTTPMiddleware):
    """Log state-changing requests (POST/PUT/PATCH/DELETE)."""
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        if request.method in ("POST", "PUT", "PATCH", "DELETE"):
            user = getattr(request.state, "current_user", None)
            user_id = user.get("soe_id") if user else "anonymous"
            logger.info(
                f"AUDIT | {user_id} | {request.method} {request.url.path} "
                f"| status={response.status_code}"
            )
        return response


# ─── JWT helpers ────────────────────────────────────────────
def create_access_token(data: dict) -> str:
    payload = data.copy()
    payload["exp"] = datetime.utcnow() + timedelta(minutes=settings.JWT_EXPIRE_MINUTES)
    payload["iat"] = datetime.utcnow()
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")


# ─── Auth dependency ────────────────────────────────────────
async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db=Depends(get_db)
) -> dict:
    if not credentials:
        raise HTTPException(status_code=401, detail="Not authenticated")
    payload = decode_token(credentials.credentials)
    user_repo = UserRepository(db)
    user = user_repo.get_by_soe_id(payload.get("soe_id", ""))
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="User not found or disabled")
    roles = user_repo.get_roles(user.user_id)
    return {
        "user_id": user.user_id,
        "soe_id": user.soe_id,
        "full_name": user.full_name,
        "email": user.email,
        "roles": [{"role_code": r.role_code, "region_id": r.region_id} for r in roles]
    }


# ─── Role checker ──────────────────────────────────────────
class RoleChecker:
    """Dependency factory that checks if user has one of the allowed roles."""
    def __init__(self, allowed_roles: List[str]):
        self.allowed_roles = allowed_roles

    def __call__(self, current_user: dict = Depends(get_current_user)):
        user_roles = {r["role_code"] for r in current_user.get("roles", [])}
        if not user_roles.intersection(set(self.allowed_roles)):
            raise HTTPException(
                status_code=403,
                detail=f"Insufficient permissions. Required: {self.allowed_roles}"
            )
        return current_user


# ─── Page Access Config ─────────────────────────────────────
# Single source of truth — mirrors frontend PAGE_ACCESS in helpers.ts.
# Update this dict to change any role's page and API access.
#
# Phase 6 additions:
#   UPLOAD / DOWNLOAD          — permission aliases for DATA_PROVIDER
#   SCORECARD_MAKER / _CHECKER — scorecard workflow roles
#   ANC_APPROVER_L1/L2/L3     — UK-region aliases for the L1/L2/L3 approval chain
#   READ                       — view-only across dashboard + data-control
PAGE_ACCESS: dict = {
    "SYSTEM_ADMIN":      ["dashboard", "data-control", "approvals", "evidence", "variance",
                          "scorecard", "kri-wizard", "admin", "escalation-metrics"],
    "L1_APPROVER":       ["dashboard", "data-control", "approvals", "evidence"],
    "L2_APPROVER":       ["dashboard", "data-control", "approvals", "evidence"],
    "L3_ADMIN":          ["dashboard", "data-control", "approvals", "evidence"],
    "MANAGEMENT":        ["dashboard", "data-control", "scorecard", "escalation-metrics"],
    "DATA_PROVIDER":     ["dashboard", "data-control", "evidence"],
    "METRIC_OWNER":      ["dashboard", "data-control"],
    # ── Phase 6 new / alias roles ──────────────────────────────
    "UPLOAD":            ["dashboard", "data-control", "evidence"],   # alias DATA_PROVIDER upload perm
    "DOWNLOAD":          ["dashboard", "evidence"],                   # alias for evidence download
    "SCORECARD_MAKER":   ["dashboard", "scorecard"],
    "SCORECARD_CHECKER": ["dashboard", "scorecard", "approvals"],
    "ANC_APPROVER_L1":   ["dashboard", "data-control", "approvals", "evidence"],  # UK L1 alias
    "ANC_APPROVER_L2":   ["dashboard", "data-control", "approvals", "evidence"],  # UK L2 alias
    "ANC_APPROVER_L3":   ["dashboard", "data-control", "approvals", "evidence", "admin"],  # UK L3 alias
    "READ":              ["dashboard", "data-control"],               # view-only
}


def require_page_access(page: str) -> RoleChecker:
    """
    Return a RoleChecker for the given page, derived from PAGE_ACCESS.
    Usage: user: dict = Depends(require_page_access("variance"))
    Change PAGE_ACCESS above — this function picks up the update automatically.
    """
    allowed_roles = [role for role, pages in PAGE_ACCESS.items() if page in pages]
    return RoleChecker(allowed_roles)


# ─── Pre-computed page-level role checkers ──────────────────
# Derived from PAGE_ACCESS — stay in sync automatically.
require_dashboard          = require_page_access("dashboard")
require_data_control       = require_page_access("data-control")
require_approvals          = require_page_access("approvals")
require_evidence           = require_page_access("evidence")
require_variance           = require_page_access("variance")
require_scorecard          = require_page_access("scorecard")
require_escalation_metrics = require_page_access("escalation-metrics")
require_system_admin       = require_page_access("admin")

# ─── Legacy / operation-level presets (kept for backward compat) ─
require_admin = RoleChecker(["SYSTEM_ADMIN", "L3_ADMIN", "ANC_APPROVER_L3"])
require_management = RoleChecker(["MANAGEMENT", "SYSTEM_ADMIN", "L3_ADMIN"])
require_approver = RoleChecker([
    "L1_APPROVER", "L2_APPROVER", "L3_ADMIN", "SYSTEM_ADMIN",
    "ANC_APPROVER_L1", "ANC_APPROVER_L2", "ANC_APPROVER_L3",
    "SCORECARD_CHECKER",
])
require_l1 = RoleChecker([
    "L1_APPROVER", "L2_APPROVER", "L3_ADMIN", "SYSTEM_ADMIN",
    "ANC_APPROVER_L1", "ANC_APPROVER_L2", "ANC_APPROVER_L3",
])
require_l2 = RoleChecker([
    "L2_APPROVER", "L3_ADMIN", "SYSTEM_ADMIN",
    "ANC_APPROVER_L2", "ANC_APPROVER_L3",
])
require_l3 = RoleChecker(["L3_ADMIN", "SYSTEM_ADMIN", "ANC_APPROVER_L3"])
require_data_provider = RoleChecker([
    "DATA_PROVIDER", "METRIC_OWNER", "L1_APPROVER", "SYSTEM_ADMIN",
    "UPLOAD",   # Phase 6 alias
])
# Evidence download — explicit DOWNLOAD alias + any approver
require_evidence_download = RoleChecker([
    "L1_APPROVER", "L2_APPROVER", "L3_ADMIN", "SYSTEM_ADMIN",
    "MANAGEMENT", "DATA_PROVIDER", "METRIC_OWNER",
    "DOWNLOAD", "ANC_APPROVER_L1", "ANC_APPROVER_L2", "ANC_APPROVER_L3",
])
require_any_authenticated = RoleChecker([
    "MANAGEMENT", "L1_APPROVER", "L2_APPROVER", "L3_ADMIN",
    "DATA_PROVIDER", "METRIC_OWNER", "SYSTEM_ADMIN",
    "UPLOAD", "DOWNLOAD", "SCORECARD_MAKER", "SCORECARD_CHECKER",
    "ANC_APPROVER_L1", "ANC_APPROVER_L2", "ANC_APPROVER_L3",
    "READ",
])
