"""
Input validators and request payload sanitizers for Spendwise backend.

Validates user credentials, registration payload, spending requests,
and formats unified JSON error responses.
"""

from typing import Dict, Tuple, Optional
from flask import jsonify


def validate_registration_payload(data: dict) -> Tuple[bool, Optional[str], Optional[str]]:
    """
    Validate incoming user registration payload.

    Args:
        data (dict): Request payload dictionary.

    Returns:
        Tuple[bool, Optional[str], Optional[str]]: (is_valid, error_message, error_field)
    """
    if not isinstance(data, dict):
        return False, "Invalid JSON payload provided.", None

    required_fields = [
        "username",
        "full_name",
        "email",
        "password",
        "balance",
        "buffer",
        "limit_period",
        "limit_balance",
    ]

    for field in required_fields:
        val = data.get(field)
        if val is None or (isinstance(val, str) and not val.strip()):
            return False, f"This field is required: {field}.", field

    username = str(data["username"]).strip()
    if len(username) < 3 or len(username) > 20:
        return False, "Username must be between 3 and 20 characters.", "username"

    email = str(data["email"]).strip()
    if "@" not in email or "." not in email:
        return False, "Please enter a valid email address.", "email"

    password = str(data["password"])
    if len(password) < 6:
        return False, "Password must be at least 6 characters long.", "password"

    try:
        balance = float(data["balance"])
        if balance < 0:
            return False, "Balance cannot be negative.", "balance"
    except (ValueError, TypeError):
        return False, "Balance must be a valid number.", "balance"

    try:
        buffer_val = float(data["buffer"])
        if buffer_val < 0:
            return False, "Buffer cannot be negative.", "buffer"
        if buffer_val > balance:
            return False, "Buffer cannot exceed your current balance.", "buffer"
    except (ValueError, TypeError):
        return False, "Buffer must be a valid number.", "buffer"

    limit_period = str(data["limit_period"]).strip().lower()
    if limit_period not in ["daily", "weekly", "monthly"]:
        return False, "Limit period must be 'daily', 'weekly', or 'monthly'.", "limit_period"

    try:
        limit_balance = float(data["limit_balance"])
        if limit_balance <= 0:
            return False, "Limit balance must be greater than 0.", "limit_balance"
        if limit_balance > balance:
            return False, "Limit balance cannot exceed your current balance.", "limit_balance"
    except (ValueError, TypeError):
        return False, "Limit balance must be a valid positive number.", "limit_balance"

    return True, None, None


def validate_profile_update_payload(data: dict, current_user: dict) -> Tuple[bool, Optional[str], Optional[str]]:
    """
    Validate profile update payload enforcing natural financial & account constraints.

    Args:
        data (dict): Request payload.
        current_user (dict): Active user document.

    Returns:
        Tuple[bool, Optional[str], Optional[str]]: (is_valid, error_message, error_field)
    """
    if not isinstance(data, dict):
        return False, "Invalid JSON payload provided.", None

    full_name = data.get("full_name")
    if full_name is not None:
        full_name = str(full_name).strip()
        if len(full_name) < 2:
            return False, "Full name must be at least 2 characters.", "full_name"

    email = data.get("email")
    if email is not None:
        email = str(email).strip().lower()
        if "@" not in email or "." not in email:
            return False, "Please enter a valid email address.", "email"

    balance = data.get("balance", current_user.get("balance", 0.0))
    buffer_val = data.get("buffer", current_user.get("buffer", 0.0))
    limit_balance = data.get("limit_balance", current_user.get("limit_balance", 0.0))

    try:
        balance = float(balance)
        if balance < 0:
            return False, "Balance cannot be negative.", "balance"
    except (ValueError, TypeError):
        return False, "Balance must be a valid number.", "balance"

    try:
        buffer_val = float(buffer_val)
        if buffer_val < 0:
            return False, "Buffer cannot be negative.", "buffer"
        if buffer_val > balance:
            return False, "Buffer cannot exceed your main balance.", "buffer"
    except (ValueError, TypeError):
        return False, "Buffer must be a valid number.", "buffer"

    try:
        limit_balance = float(limit_balance)
        if limit_balance <= 0:
            return False, "Limit balance must be greater than 0.", "limit_balance"
        if limit_balance > balance:
            return False, "Limit balance cannot exceed your main balance.", "limit_balance"
    except (ValueError, TypeError):
        return False, "Limit balance must be a valid positive number.", "limit_balance"

    limit_period = data.get("limit_period")
    if limit_period is not None:
        limit_period = str(limit_period).strip().lower()
        if limit_period not in ["daily", "weekly", "monthly"]:
            return False, "Limit period must be 'daily', 'weekly', or 'monthly'.", "limit_period"

    return True, None, None


def validate_purchase_payload(data: dict) -> Tuple[bool, Optional[str], Optional[str]]:
    """
    Validate purchase or item checking payload.

    Args:
        data (dict): Request payload dictionary containing 'item' and 'price'.

    Returns:
        Tuple[bool, Optional[str], Optional[str]]: (is_valid, error_message, error_field)
    """
    if not isinstance(data, dict):
        return False, "Invalid JSON payload provided.", None

    item = data.get("item")
    if not item or not str(item).strip():
        return False, "Enter the item you want to buy.", "item"

    price_val = data.get("price")
    if price_val is None:
        return False, "Enter a price above 0.", "price"

    try:
        price = float(price_val)
        if price <= 0:
            return False, "Price must be greater than 0.", "price"
    except (ValueError, TypeError):
        return False, "Enter a valid positive price.", "price"

    return True, None, None


def make_error_response(message: str, status_code: int = 400, field: Optional[str] = None):
    """
    Construct a consistent HTTP JSON error response.

    Args:
        message (str): User-facing error message string.
        status_code (int): HTTP status code (default 400).
        field (Optional[str]): Field name associated with the error.

    Returns:
        Response: Flask JSON response object with HTTP status code.
    """
    payload = {"error": message, "message": message}
    if field:
        payload["field"] = field
    return jsonify(payload), status_code
