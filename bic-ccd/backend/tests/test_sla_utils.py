"""
Pure-function unit tests for SLA and business-day utilities.

No DB, no HTTP — all deterministic date arithmetic.
"""
import pytest
from datetime import date

from app.utils.business_days import (
    is_business_day,
    nth_business_day,
    business_day_offset,
    calendar_day_of_month,
)
from app.utils.sla import (
    calculate_sla_dates,
    apply_february_cap,
    is_within_sla,
)


# ═══════════════════════════════════════════════════════
# is_business_day
# ═══════════════════════════════════════════════════════

class TestIsBusinessDay:
    def test_monday_is_business_day(self):
        # 2024-01-08 is a Monday
        assert is_business_day(date(2024, 1, 8)) is True

    def test_friday_is_business_day(self):
        assert is_business_day(date(2024, 1, 12)) is True

    def test_saturday_is_not_business_day(self):
        assert is_business_day(date(2024, 1, 13)) is False

    def test_sunday_is_not_business_day(self):
        assert is_business_day(date(2024, 1, 14)) is False


# ═══════════════════════════════════════════════════════
# nth_business_day
# ═══════════════════════════════════════════════════════

class TestNthBusinessDay:
    def test_bd1_january_2024(self):
        # 2024-01-01 is a Monday
        assert nth_business_day(2024, 1, 1) == date(2024, 1, 1)

    def test_bd2_january_2024(self):
        assert nth_business_day(2024, 1, 2) == date(2024, 1, 2)

    def test_bd1_when_month_starts_on_weekend(self):
        # 2023-07-01 is a Saturday → BD1 is Monday 2023-07-03
        assert nth_business_day(2023, 7, 1) == date(2023, 7, 3)

    def test_bd8_reasonable(self):
        result = nth_business_day(2024, 1, 8)
        assert result.month == 1
        assert result.year == 2024
        assert result.day <= 12  # at most day 12 in Jan (no holidays)

    def test_invalid_n_raises(self):
        with pytest.raises(ValueError):
            nth_business_day(2024, 1, 0)

    def test_too_large_n_raises(self):
        # February has at most 20 business days; 25 should raise
        with pytest.raises(ValueError):
            nth_business_day(2024, 2, 25)


# ═══════════════════════════════════════════════════════
# business_day_offset
# ═══════════════════════════════════════════════════════

class TestBusinessDayOffset:
    def test_zero_offset_returns_same_day(self):
        d = date(2024, 1, 15)
        assert business_day_offset(d, 0) == d

    def test_positive_offset_skips_weekends(self):
        # 2024-01-12 (Friday) + 1 BD = 2024-01-15 (Monday)
        assert business_day_offset(date(2024, 1, 12), 1) == date(2024, 1, 15)

    def test_positive_offset_3(self):
        # 2024-01-15 (Monday) + 3 BD = 2024-01-18 (Thursday)
        assert business_day_offset(date(2024, 1, 15), 3) == date(2024, 1, 18)

    def test_negative_offset(self):
        # 2024-01-15 (Monday) - 1 BD = 2024-01-12 (Friday)
        assert business_day_offset(date(2024, 1, 15), -1) == date(2024, 1, 12)


# ═══════════════════════════════════════════════════════
# calendar_day_of_month
# ═══════════════════════════════════════════════════════

class TestCalendarDayOfMonth:
    def test_normal_day(self):
        assert calendar_day_of_month(2024, 3, 15) == date(2024, 3, 15)

    def test_clamps_to_last_day_of_february(self):
        # Feb 2024 has 29 days (leap year)
        assert calendar_day_of_month(2024, 2, 31) == date(2024, 2, 29)

    def test_clamps_february_non_leap(self):
        assert calendar_day_of_month(2023, 2, 30) == date(2023, 2, 28)

    def test_clamps_april(self):
        # April has 30 days
        assert calendar_day_of_month(2024, 4, 31) == date(2024, 4, 30)


# ═══════════════════════════════════════════════════════
# apply_february_cap
# ═══════════════════════════════════════════════════════

class TestApplyFebruaryCap:
    def test_no_cap_needed_in_march(self):
        assert apply_february_cap(15, 2024, 3) == 15

    def test_cap_in_february_leap(self):
        assert apply_february_cap(30, 2024, 2) == 29

    def test_cap_in_february_non_leap(self):
        assert apply_february_cap(30, 2023, 2) == 28

    def test_cap_in_april(self):
        assert apply_february_cap(31, 2024, 4) == 30


# ═══════════════════════════════════════════════════════
# calculate_sla_dates — standard (non-DCRM) KRI
# ═══════════════════════════════════════════════════════

class TestCalculateSlaDatesStandard:
    def test_returns_three_dates(self):
        result = calculate_sla_dates(
            kri_is_dcrm=False,
            dimension_code="COMPLETENESS_ACCURACY",
            year=2024, month=1,
            sla_start_day=1, sla_end_day=15, sla_days=3,
        )
        assert len(result) == 3

    def test_sla_start_before_sla_end(self):
        sla_start, sla_end, freeze = calculate_sla_dates(
            kri_is_dcrm=False, dimension_code="REVIEWS",
            year=2024, month=3,
            sla_start_day=1, sla_end_day=15, sla_days=3,
        )
        assert sla_start <= sla_end

    def test_freeze_after_sla_end(self):
        sla_start, sla_end, freeze = calculate_sla_dates(
            kri_is_dcrm=False, dimension_code="REVIEWS",
            year=2024, month=3,
            sla_start_day=1, sla_end_day=15, sla_days=3,
        )
        assert freeze >= sla_end

    def test_none_sla_days_uses_defaults(self):
        result = calculate_sla_dates(
            kri_is_dcrm=False, dimension_code="REVIEWS",
            year=2024, month=1,
            sla_start_day=None, sla_end_day=None, sla_days=3,
        )
        assert len(result) == 3

    def test_correct_period(self):
        sla_start, sla_end, freeze = calculate_sla_dates(
            kri_is_dcrm=False, dimension_code="REVIEWS",
            year=2024, month=5,
            sla_start_day=1, sla_end_day=15, sla_days=3,
        )
        assert sla_start.month == 5
        assert sla_end.month == 5


# ═══════════════════════════════════════════════════════
# calculate_sla_dates — DCRM KRI
# ═══════════════════════════════════════════════════════

class TestCalculateSlaDcrmKri:
    def test_timeliness_sla_in_following_month(self):
        # Jan 2024 DCRM timeliness → dates fall in Feb 2024
        sla_start, sla_end, freeze = calculate_sla_dates(
            kri_is_dcrm=True, dimension_code="DATA_PROVIDER_SLA",
            year=2024, month=1,
            sla_start_day=None, sla_end_day=None, sla_days=3,
        )
        assert sla_start.month == 2
        assert sla_end.month == 2
        assert freeze.month == 2

    def test_timeliness_freeze_at_bd8(self):
        sla_start, sla_end, freeze = calculate_sla_dates(
            kri_is_dcrm=True, dimension_code="DATA_PROVIDER_SLA",
            year=2024, month=1,
            sla_start_day=None, sla_end_day=None, sla_days=3,
        )
        bd8 = nth_business_day(2024, 2, 8)
        assert freeze == bd8

    def test_ca_dimension_freeze_at_bd8(self):
        _, _, freeze = calculate_sla_dates(
            kri_is_dcrm=True, dimension_code="COMPLETENESS_ACCURACY",
            year=2024, month=3,
            sla_start_day=None, sla_end_day=None, sla_days=3,
        )
        bd8 = nth_business_day(2024, 4, 8)
        assert freeze == bd8

    def test_december_rolls_to_january(self):
        sla_start, sla_end, freeze = calculate_sla_dates(
            kri_is_dcrm=True, dimension_code="DATA_PROVIDER_SLA",
            year=2024, month=12,
            sla_start_day=None, sla_end_day=None, sla_days=3,
        )
        assert sla_start.year == 2025
        assert sla_start.month == 1


# ═══════════════════════════════════════════════════════
# is_within_sla
# ═══════════════════════════════════════════════════════

class TestIsWithinSla:
    def test_before_sla_end_passes(self):
        assert is_within_sla(date(2024, 1, 14), date(2024, 1, 15)) is True

    def test_on_sla_end_passes(self):
        assert is_within_sla(date(2024, 1, 15), date(2024, 1, 15)) is True

    def test_after_sla_end_fails(self):
        assert is_within_sla(date(2024, 1, 16), date(2024, 1, 15)) is False
