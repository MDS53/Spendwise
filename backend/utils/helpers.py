"""
Helper utilities for Spendwise backend.

Provides currency formatting, datetime arithmetic, period calculations,
and mathematical rounding functions.
"""

import math
from datetime import datetime, timezone


def round_money(amount: float) -> float:
    """
    Round a monetary amount to 2 decimal places safely.

    Args:
        amount (float): Raw monetary value.

    Returns:
        float: Rounded value to 2 decimal places.
    """
    if amount is None:
        return 0.0
    return round(float(amount) + 1e-9, 2)


def format_currency(amount: float, currency_symbol: str = "$") -> str:
    """
    Format a floating-point number into a formatted currency string.

    Args:
        amount (float): Monetary value to format.
        currency_symbol (str): Symbol prefix (default: "$").

    Returns:
        str: Formatted currency string, e.g., "$1,250.50".
    """
    val = round_money(amount)
    return f"{currency_symbol}{val:,.2f}"


def get_period_seconds(period: str) -> int:
    """
    Get the duration of a spending limit period in seconds.

    Args:
        period (str): Spending period ('daily', 'weekly', 'monthly').

    Returns:
        int: Total seconds in the period.
    """
    period_lower = str(period or "daily").lower().strip()
    if period_lower == "daily":
        return 86400  # 24 hours
    elif period_lower == "weekly":
        return 604800  # 7 days
    elif period_lower == "monthly":
        return 2592000  # 30 days (standardized)
    return 86400


def calculate_elapsed_periods(last_renewed_dt: datetime, current_dt: datetime, period: str) -> int:
    """
    Calculate the integer number of full spending limit periods that have elapsed
    between the last renewal timestamp and the current timestamp.

    Args:
        last_renewed_dt (datetime): Datetime when the limit was last renewed.
        current_dt (datetime): Current UTC datetime.
        period (str): Limit period type ('daily', 'weekly', 'monthly').

    Returns:
        int: Number of elapsed periods (0 if not due yet).
    """
    if not last_renewed_dt or not current_dt:
        return 0

    # Ensure tz awareness or naive alignment
    if last_renewed_dt.tzinfo is None:
        last_renewed_dt = last_renewed_dt.replace(tzinfo=timezone.utc)
    if current_dt.tzinfo is None:
        current_dt = current_dt.replace(tzinfo=timezone.utc)

    delta_seconds = (current_dt - last_renewed_dt).total_seconds()
    if delta_seconds <= 0:
        return 0

    period_secs = get_period_seconds(period)
    return math.floor(delta_seconds / period_secs)


def parse_iso_datetime(iso_str: str) -> datetime:
    """
    Parse an ISO 8601 formatted date string into a UTC datetime object.

    Args:
        iso_str (str): ISO formatted date string.

    Returns:
        datetime: Parsed UTC datetime object or current UTC time if invalid.
    """
    if not iso_str:
        return datetime.now(timezone.utc)
    try:
        dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return datetime.now(timezone.utc)


def format_iso_datetime(dt: datetime = None) -> str:
    """
    Format a datetime object into an ISO 8601 string.

    Args:
        dt (datetime, optional): Datetime object. Defaults to current UTC time.

    Returns:
        str: ISO 8601 formatted date string.
    """
    if dt is None:
        dt = datetime.now(timezone.utc)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat()
