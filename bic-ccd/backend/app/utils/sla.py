"""SLA calculation engine for BIC-CCD.

Replaces the hardcoded ``sla_due_dt = datetime(y, m, 15) + timedelta(days=3)``
in main.py with a proper rule-based engine driven by kri_configuration fields.

Rule summary (BRD §4 / §15):
  Non-DCRM KRIs
    sla_start  = calendar day kri_config.sla_start_day  (default: 1)
    sla_end    = calendar day kri_config.sla_end_day    (default: 15)
    freeze     = business_day_offset(sla_end, kri_config.sla_days)  (default BD+3)

  DCRM KRIs (kri.is_dcrm == True)
    Timeliness dimension  → BD2 of following month
    C&A dimension         → BD3 of following month
    freeze                → BD8 of following month (hard-coded per BRD §15)

All date arithmetic delegates to business_days.py so holiday support can
be added there without touching this module.
"""
from datetime import date
from typing import Tuple, Optional

from app.utils.business_days import (
    nth_business_day,
    business_day_offset,
    calendar_day_of_month,
    is_business_day,
)

# Dimension codes that follow the DCRM timeliness path (BRD §15)
_DCRM_TIMELINESS_CODES = {"DATA_PROVIDER_SLA"}
_DCRM_CA_CODES = {"COMPLETENESS_ACCURACY"}

# Defaults when kri_configuration fields are NULL
_DEFAULT_SLA_START_DAY = 1
_DEFAULT_SLA_END_DAY = 15
_DEFAULT_FREEZE_BD_OFFSET = 3   # business days after sla_end
_DCRM_FREEZE_BD = 8             # BD8 of the reporting month


def apply_february_cap(sla_day: int, year: int, month: int) -> int:
    """Clamp sla_day to the last day of the month (critical for February)."""
    import calendar
    _, last = calendar.monthrange(year, month)
    return min(sla_day, last)


def calculate_sla_dates(
    kri_is_dcrm: bool,
    dimension_code: str,
    year: int,
    month: int,
    sla_start_day: Optional[int],
    sla_end_day: Optional[int],
    sla_days: int,           # BD offset stored in kri_configuration.sla_days
) -> Tuple[date, date, date]:
    """Return (sla_start, sla_end, freeze_date) for a given KRI/dimension/period.

    Parameters
    ----------
    kri_is_dcrm:     value of kri_master.is_dcrm
    dimension_code:  value of control_dimension_master.dimension_code
    year, month:     the reporting period
    sla_start_day:   kri_configuration.sla_start_day  (may be None)
    sla_end_day:     kri_configuration.sla_end_day    (may be None)
    sla_days:        kri_configuration.sla_days  — BD offset for freeze
    """
    if kri_is_dcrm:
        return _dcrm_sla_dates(dimension_code, year, month)
    return _standard_sla_dates(year, month, sla_start_day, sla_end_day, sla_days)


def _standard_sla_dates(
    year: int,
    month: int,
    sla_start_day: Optional[int],
    sla_end_day: Optional[int],
    sla_days: int,
) -> Tuple[date, date, date]:
    start_day = apply_february_cap(sla_start_day or _DEFAULT_SLA_START_DAY, year, month)
    end_day   = apply_february_cap(sla_end_day   or _DEFAULT_SLA_END_DAY,   year, month)

    sla_start  = calendar_day_of_month(year, month, start_day)
    sla_end    = calendar_day_of_month(year, month, end_day)
    freeze_date = business_day_offset(sla_end, sla_days or _DEFAULT_FREEZE_BD_OFFSET)

    return sla_start, sla_end, freeze_date


def _dcrm_sla_dates(
    dimension_code: str,
    year: int,
    month: int,
) -> Tuple[date, date, date]:
    """DCRM SLA dates are expressed in BD-of-month terms per BRD §15."""
    # DCRM reports on the *following* month's business days
    # e.g. January data → February BD2/BD3/BD8
    if month == 12:
        check_year, check_month = year + 1, 1
    else:
        check_year, check_month = year, month + 1

    if dimension_code in _DCRM_TIMELINESS_CODES:
        sla_end_bd = 2
    elif dimension_code in _DCRM_CA_CODES:
        sla_end_bd = 3
    else:
        sla_end_bd = 3   # default for other DCRM dimensions

    sla_start  = nth_business_day(check_year, check_month, 1)
    sla_end    = nth_business_day(check_year, check_month, sla_end_bd)
    freeze_date = nth_business_day(check_year, check_month, _DCRM_FREEZE_BD)

    return sla_start, sla_end, freeze_date


def is_within_sla(check_date: date, sla_end: date) -> bool:
    """Return True if *check_date* is on or before *sla_end*."""
    return check_date <= sla_end
