"""
Finance controller blueprint for Spendwise backend.

Provides REST API endpoints for purchase evaluation, item purchasing,
items history section retrieval, and user profile sync.
"""

from flask import Blueprint, request, jsonify, session
from backend.services.finance_service import FinanceService
from backend.services.auth_service import AuthService
from backend.utils.validators import validate_purchase_payload, make_error_response

finance_bp = Blueprint("finance", __name__, url_prefix="/api")


def _get_current_username() -> str:
    """
    Internal helper to resolve session or request username.

    Returns:
        str: Username string or empty string if unauthenticated.
    """
    return session.get("username") or request.args.get("username", "") or ""


@finance_bp.route("/check-purchase", methods=["POST"])
def check_purchase():
    """
    HTTP POST /api/check-purchase

    Check whether an item purchase can be afforded under current limit and balance rules.
    Does not modify database records.

    Request Body:
        {
            "username": "alex",  (optional if logged in via session)
            "item": "Running shoes",
            "price": 89.90
        }

    Returns:
        JSON object containing verdict, reasons array, current limit left, balance, and buffer.
    """
    data = request.get_json(silent=True) or {}
    username = data.get("username") or _get_current_username()

    if not username:
        return make_error_response("Your session ended. Please log in again.", status_code=401)

    is_valid, err_msg, err_field = validate_purchase_payload(data)
    if not is_valid:
        return make_error_response(err_msg, status_code=400, field=err_field)

    item_name = str(data["item"]).strip()
    price = float(data["price"])

    success, verdict, err = FinanceService.evaluate_purchase(username, item_name, price)
    if not success:
        return make_error_response(err, status_code=400)

    return jsonify(verdict), 200


@finance_bp.route("/buy", methods=["POST"])
def buy():
    """
    HTTP POST /api/buy

    Add an item to the user's profile and database, deducting cost from limit and balance,
    and applying emergency buffer rules if limit is exceeded.

    Request Body:
        {
            "username": "alex",  (optional if logged in)
            "item": "Running shoes",
            "price": 89.90
        }

    Returns:
        JSON object containing transaction summary, item record, and updated user profile.
    """
    data = request.get_json(silent=True) or {}
    username = data.get("username") or _get_current_username()

    if not username:
        return make_error_response("Your session ended. Please log in again.", status_code=401)

    is_valid, err_msg, err_field = validate_purchase_payload(data)
    if not is_valid:
        return make_error_response(err_msg, status_code=400, field=err_field)

    item_name = str(data["item"]).strip()
    price = float(data["price"])

    success, result, err = FinanceService.execute_purchase(username, item_name, price)
    if not success:
        return make_error_response(err or "Transaction could not be processed.", status_code=400)

    return jsonify(result), 200


@finance_bp.route("/items", methods=["GET"])
def get_items():
    """
    HTTP GET /api/items

    Retrieve items added by the user from the database.

    Query Parameters:
        username (str): Username (optional if logged in via session).
        limit (int): Maximum items to return (default 50).

    Returns:
        JSON list of item documents inserted into database.
    """
    username = request.args.get("username") or _get_current_username()
    if not username:
        return make_error_response("Username is required to view items.", status_code=401)

    limit = int(request.args.get("limit", 50))
    items = FinanceService.get_user_items(username, limit=limit)
    return jsonify({"username": username, "items": items, "count": len(items)}), 200


@finance_bp.route("/profile", methods=["GET"])
def get_profile():
    """
    HTTP GET /api/profile

    Retrieve updated user profile and items history section.

    Returns:
        JSON object with user details, limit rollover status, and items section.
    """
    username = request.args.get("username") or _get_current_username()
    if not username:
        return make_error_response("Session ended.", status_code=401)

    user_profile = AuthService.get_user_profile(username)
    if not user_profile:
        return make_error_response("User profile not found.", status_code=404)

    items = FinanceService.get_user_items(username, limit=20)
    return jsonify({"user": user_profile, "items": items}), 200
