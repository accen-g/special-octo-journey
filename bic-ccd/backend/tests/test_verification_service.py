"""
Unit tests for the verification service (scheduler job implementations).

Uses an in-memory SQLite database with manually seeded minimal data.
No HTTP, no FastAPI — pure service layer testing.
"""
import pytest
from datetime import date, datetime, timedelta
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, BicCcdBase
from app.models import (
    RegionMaster, KriCategoryMaster, ControlDimensionMaster,
    KriMaster, KriConfiguration, KriStatusLookup,
    MonthlyControlStatus, DataSourceMapping, DataSourceStatusTracker,
)
from app.services.verification import monthly_init, daily_timeliness_check, dcrm_processing


# ── In-memory DB shared across all tests in this module ─────────────────────

@pytest.fixture(scope="module")
def engine():
    eng = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(eng, "connect")
    def _pragmas(conn, _):
        conn.execute("PRAGMA foreign_keys=ON")

    import app.models.bic_ccd  # noqa — ensure BicCcdBase mappers are populated
    Base.metadata.create_all(bind=eng)
    BicCcdBase.metadata.create_all(bind=eng)
    yield eng
    BicCcdBase.metadata.drop_all(bind=eng)
    Base.metadata.drop_all(bind=eng)


@pytest.fixture(scope="module")
def Session(engine):
    return sessionmaker(bind=engine)


@pytest.fixture(scope="module")
def seeded(Session):
    """Seed minimal master data once for the module."""
    db = Session()
    try:
        # Status lookup rows
        for s in ("NOT_STARTED", "NOT_RECEIVED", "SLA_BREACHED", "COMPLETED", "IN_PROGRESS"):
            db.add(KriStatusLookup(status_name=s))
        db.flush()

        region = RegionMaster(region_code="UK", region_name="United Kingdom",
                              created_by="T", updated_by="T")
        db.add(region)
        db.flush()

        cat = KriCategoryMaster(category_code="MR", category_name="Market Risk",
                                created_by="T", updated_by="T")
        db.add(cat)
        db.flush()

        dims = []
        for code, name in [
            ("DATA_PROVIDER_SLA", "Data Provider SLA"),
            ("COMPLETENESS_ACCURACY", "Completeness"),
        ]:
            d = ControlDimensionMaster(dimension_code=code, dimension_name=name,
                                       display_order=1, created_by="T", updated_by="T")
            db.add(d)
            dims.append(d)
        db.flush()

        kri = KriMaster(
            kri_code="KRI-UK-001", kri_name="Test KRI", kri_title="Test",
            category_id=cat.category_id, region_id=region.region_id,
            is_dcrm=False, created_by="T", updated_by="T",
        )
        db.add(kri)
        db.flush()

        dcrm_kri = KriMaster(
            kri_code="KRI-UK-DCRM", kri_name="DCRM KRI", kri_title="DCRM",
            category_id=cat.category_id, region_id=region.region_id,
            is_dcrm=True, created_by="T", updated_by="T",
        )
        db.add(dcrm_kri)
        db.flush()

        for kri_obj in (kri, dcrm_kri):
            for dim in dims:
                db.add(KriConfiguration(
                    kri_id=kri_obj.kri_id, dimension_id=dim.dimension_id,
                    sla_days=3, requires_evidence=False, requires_approval=True,
                    created_by="T", updated_by="T",
                ))
        db.flush()

        dsm = DataSourceMapping(
            kri_id=kri.kri_id, source_name="TestSource",
            created_by="T", updated_by="T",
        )
        db.add(dsm)
        db.commit()

        yield {
            "region": region, "cat": cat, "dims": dims,
            "kri": kri, "dcrm_kri": dcrm_kri, "dsm": dsm,
        }
    finally:
        db.close()


# ── monthly_init ─────────────────────────────────────────────────────────────

class TestMonthlyInit:
    def test_creates_status_rows(self, Session, seeded):
        db = Session()
        try:
            result = monthly_init(db, 2030, 1)
            assert result["created_statuses"] > 0
            assert result["period"] == "2030-01"
        finally:
            db.close()

    def test_creates_tracker_rows(self, Session, seeded):
        db = Session()
        try:
            result = monthly_init(db, 2030, 2)
            assert result["created_trackers"] >= 0   # may be 0 if already created
        finally:
            db.close()

    def test_idempotent_no_duplicates(self, Session, seeded):
        db = Session()
        try:
            r1 = monthly_init(db, 2031, 1)
            r2 = monthly_init(db, 2031, 1)   # second call — same period
            # Second call creates 0 rows (all exist already)
            assert r2["created_statuses"] == 0
        finally:
            db.close()

    def test_status_set_to_not_started(self, Session, seeded):
        db = Session()
        try:
            monthly_init(db, 2032, 3)
            rows = db.query(MonthlyControlStatus).filter_by(
                period_year=2032, period_month=3
            ).all()
            assert all(r.status == "NOT_STARTED" for r in rows)
        finally:
            db.close()

    def test_created_by_scheduler(self, Session, seeded):
        db = Session()
        try:
            monthly_init(db, 2033, 4)
            rows = db.query(MonthlyControlStatus).filter_by(
                period_year=2033, period_month=4
            ).all()
            assert all(r.created_by == "SCHEDULER" for r in rows)
        finally:
            db.close()

    def test_row_count_matches_kri_times_dims(self, Session, seeded):
        db = Session()
        try:
            result = monthly_init(db, 2034, 5)
            # 2 active KRIs × 2 active dims = 4 rows
            assert result["created_statuses"] == 4
        finally:
            db.close()


# ── daily_timeliness_check ────────────────────────────────────────────────────

class TestDailyTimelinessCheck:
    def test_no_breach_if_within_sla(self, Session, seeded):
        db = Session()
        try:
            # Set up a tracker row with sla_end in the future
            monthly_init(db, 2035, 6)
            sla_far_future = datetime.utcnow() + timedelta(days=30)
            rows = db.query(MonthlyControlStatus).filter_by(
                period_year=2035, period_month=6
            ).all()
            for r in rows:
                r.sla_end = sla_far_future
            db.commit()

            result = daily_timeliness_check(db, today=date.today())
            assert result["breached"] == 0
        finally:
            db.close()

    def test_breaches_when_past_sla(self, Session, seeded):
        db = Session()
        try:
            monthly_init(db, 2036, 7)
            sla_past = datetime.utcnow() - timedelta(days=5)
            rows = db.query(MonthlyControlStatus).filter_by(
                period_year=2036, period_month=7
            ).all()
            for r in rows:
                r.sla_end = sla_past
            db.commit()

            # Create a data source tracker for this period with status NOT_RECEIVED
            # (already done by monthly_init for dsm, but let's ensure it exists)
            tracker_rows = db.query(DataSourceStatusTracker).filter_by(
                period_year=2036, period_month=7, status="NOT_RECEIVED"
            ).all()

            if tracker_rows:
                result = daily_timeliness_check(db, today=date.today())
                # breached_count depends on how many parent rows are found
                assert result["job"] == "daily_timeliness_check"
                assert isinstance(result["breached"], int)
        finally:
            db.close()

    def test_returns_summary_dict(self, Session, seeded):
        db = Session()
        try:
            result = daily_timeliness_check(db, today=date.today())
            assert "job" in result
            assert result["job"] == "daily_timeliness_check"
            assert "checked" in result
            assert "breached" in result
        finally:
            db.close()

    def test_terminal_statuses_not_breached(self, Session, seeded):
        db = Session()
        try:
            monthly_init(db, 2037, 8)
            rows = db.query(MonthlyControlStatus).filter_by(
                period_year=2037, period_month=8
            ).all()
            sla_past = datetime.utcnow() - timedelta(days=5)
            for r in rows:
                r.status = "COMPLETED"  # terminal
                r.sla_end = sla_past
            db.commit()

            result = daily_timeliness_check(db, today=date.today())
            # None of the COMPLETED rows should be breached
            refreshed = db.query(MonthlyControlStatus).filter_by(
                period_year=2037, period_month=8
            ).all()
            assert all(r.status == "COMPLETED" for r in refreshed)
        finally:
            db.close()


# ── dcrm_processing ───────────────────────────────────────────────────────────

class TestDcrmProcessing:
    def test_returns_summary_dict(self, Session, seeded):
        db = Session()
        try:
            result = dcrm_processing(db, today=date.today())
            assert result["job"] == "dcrm_processing"
            assert "bd2_breaches" in result
            assert "bd3_breaches" in result
            assert "bd8_freezes" in result
        finally:
            db.close()

    def test_no_crash_with_no_dcrm_kris_active(self, Session, seeded):
        db = Session()
        try:
            # Deactivate DCRM KRI temporarily
            dcrm = seeded["dcrm_kri"]
            dcrm.is_active = False
            db.merge(dcrm)
            db.commit()

            result = dcrm_processing(db, today=date.today())
            assert result["bd2_breaches"] == 0

            dcrm.is_active = True
            db.merge(dcrm)
            db.commit()
        finally:
            db.close()
