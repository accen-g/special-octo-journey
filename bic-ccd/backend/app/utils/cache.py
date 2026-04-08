"""Application-level TTL cache for expensive, frequently-read lookups.

Cached items:
  - Control dimensions (ControlDimensionMaster rows)      — 30 min TTL
  - KRI status lookup names (KriStatusLookup rows)        — 30 min TTL
  - Role → page access map (derived from PAGE_ACCESS)     — 60 min TTL
  - Region list (RegionMaster rows)                       — 30 min TTL

Usage:
    from app.utils.cache import get_cached_dimensions, invalidate_all

    dims = get_cached_dimensions(db)   # returns list[dict], cached for 30 min

Cache invalidation:
    Call invalidate_all() (or a specific invalidator) from the
    POST /api/admin/cache/refresh endpoint.

Implementation:
    Uses a simple dict-based TTL store so there is no extra dependency.
    Thread safety: GIL is sufficient for CPython; replace with threading.Lock
    if you switch to a multi-threaded server.
"""
import time
import logging
from typing import Any, Callable, Optional

logger = logging.getLogger("bic_ccd.cache")

# ─── TTL store ───────────────────────────────────────────────────────────────

class _TTLCache:
    """Minimal TTL cache: {key: (value, expires_at)}."""

    def __init__(self):
        self._store: dict[str, tuple[Any, float]] = {}

    def get(self, key: str) -> tuple[bool, Any]:
        """Return (hit, value).  hit=False if missing or expired."""
        entry = self._store.get(key)
        if entry is None:
            return False, None
        value, expires_at = entry
        if time.monotonic() > expires_at:
            del self._store[key]
            return False, None
        return True, value

    def set(self, key: str, value: Any, ttl_seconds: int) -> None:
        self._store[key] = (value, time.monotonic() + ttl_seconds)

    def invalidate(self, key: str) -> None:
        self._store.pop(key, None)

    def invalidate_all(self) -> int:
        count = len(self._store)
        self._store.clear()
        return count

    def stats(self) -> dict:
        now = time.monotonic()
        return {
            "total_keys": len(self._store),
            "keys": [
                {"key": k, "ttl_remaining": round(exp - now, 1)}
                for k, (_, exp) in self._store.items()
            ],
        }


_cache = _TTLCache()

_TTL_DIMENSIONS = 1800   # 30 min
_TTL_STATUSES   = 1800
_TTL_REGIONS    = 1800
_TTL_ROLES      = 3600   # 60 min


# ─── Cached accessors ────────────────────────────────────────────────────────

def get_cached_dimensions(db) -> list:
    """Return all active ControlDimensionMaster rows as dicts."""
    hit, val = _cache.get("dimensions")
    if hit:
        return val
    from app.models import ControlDimensionMaster
    rows = db.query(ControlDimensionMaster).filter_by(is_active=True).order_by(
        ControlDimensionMaster.display_order
    ).all()
    result = [
        {
            "dimension_id": r.dimension_id,
            "dimension_code": r.dimension_code,
            "dimension_name": r.dimension_name,
            "display_order": r.display_order,
            "freeze_business_days": r.freeze_business_days,
        }
        for r in rows
    ]
    _cache.set("dimensions", result, _TTL_DIMENSIONS)
    logger.debug("Cache MISS: dimensions (%d rows loaded)", len(result))
    return result


def get_cached_statuses(db) -> list:
    """Return all KriStatusLookup rows as dicts."""
    hit, val = _cache.get("statuses")
    if hit:
        return val
    from app.models import KriStatusLookup
    rows = db.query(KriStatusLookup).order_by(KriStatusLookup.status_id).all()
    result = [{"status_id": r.status_id, "status_name": r.status_name} for r in rows]
    _cache.set("statuses", result, _TTL_STATUSES)
    logger.debug("Cache MISS: statuses (%d rows loaded)", len(result))
    return result


def get_cached_regions(db) -> list:
    """Return all active RegionMaster rows as dicts."""
    hit, val = _cache.get("regions")
    if hit:
        return val
    from app.models import RegionMaster
    rows = db.query(RegionMaster).filter_by(is_active=True).all()
    result = [
        {
            "region_id": r.region_id,
            "region_code": r.region_code,
            "region_name": r.region_name,
        }
        for r in rows
    ]
    _cache.set("regions", result, _TTL_REGIONS)
    logger.debug("Cache MISS: regions (%d rows loaded)", len(result))
    return result


def get_cached_page_access() -> dict:
    """Return PAGE_ACCESS dict (from middleware), cached."""
    hit, val = _cache.get("page_access")
    if hit:
        return val
    from app.middleware import PAGE_ACCESS
    _cache.set("page_access", PAGE_ACCESS, _TTL_ROLES)
    logger.debug("Cache MISS: page_access")
    return PAGE_ACCESS


# ─── Invalidation ────────────────────────────────────────────────────────────

def invalidate_dimensions() -> None:
    _cache.invalidate("dimensions")
    logger.info("Cache invalidated: dimensions")


def invalidate_statuses() -> None:
    _cache.invalidate("statuses")
    logger.info("Cache invalidated: statuses")


def invalidate_regions() -> None:
    _cache.invalidate("regions")
    logger.info("Cache invalidated: regions")


def invalidate_page_access() -> None:
    _cache.invalidate("page_access")
    logger.info("Cache invalidated: page_access")


def invalidate_all() -> dict:
    count = _cache.invalidate_all()
    logger.info("Cache fully invalidated: %d keys cleared", count)
    return {"cleared_keys": count}


def cache_stats() -> dict:
    return _cache.stats()
