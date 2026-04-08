"""Business day utilities for SLA and DCRM schedule calculations.

All functions are pure — no DB access, no side effects.
Weekend definition: Saturday (5) and Sunday (6) only.
Holiday calendar not implemented; extend _is_holiday() if required.
"""
from datetime import date, timedelta
import calendar


def _is_holiday(d: date) -> bool:
    """Placeholder: return True if date is a public holiday.

    Replace with a real calendar source (e.g. pandas_market_calendars
    or a DB-backed holiday table) when needed.
    """
    return False


def is_business_day(d: date) -> bool:
    """Return True if *d* is a weekday and not a holiday."""
    return d.weekday() < 5 and not _is_holiday(d)


def nth_business_day(year: int, month: int, n: int) -> date:
    """Return the n-th business day of the given month (1-indexed).

    Raises ValueError if the month has fewer than n business days.
    """
    if n < 1:
        raise ValueError(f"n must be >= 1, got {n}")

    count = 0
    _, days_in_month = calendar.monthrange(year, month)
    for day in range(1, days_in_month + 1):
        d = date(year, month, day)
        if is_business_day(d):
            count += 1
            if count == n:
                return d

    raise ValueError(
        f"Month {year}-{month:02d} has fewer than {n} business days (found {count})"
    )


def business_day_offset(start_date: date, n: int) -> date:
    """Return the date that is *n* business days after *start_date*.

    *start_date* itself is NOT counted; counting starts from the next day.
    Supports negative *n* for looking backward.
    """
    if n == 0:
        return start_date

    step = 1 if n > 0 else -1
    remaining = abs(n)
    current = start_date
    while remaining > 0:
        current += timedelta(days=step)
        if is_business_day(current):
            remaining -= 1

    return current


def calendar_day_of_month(year: int, month: int, day: int) -> date:
    """Clamp *day* to the last day of the month (handles Feb, etc.)."""
    _, last = calendar.monthrange(year, month)
    return date(year, month, min(day, last))
