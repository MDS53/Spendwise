"""
Authentication controller blueprint for Spendwise backend.

Provides HTTP REST API endpoints for user registration, authentication,
logout, and session verification.
"""

from flask import Blueprint, request, jsonify, session
from backend.services.auth_service import AuthService
from backend.utils.validators import make_error_response

auth_bp = Blueprint("auth", __name__, url_prefix="/api")


@auth_bp.route("/register", methods=["POST"])
def register():
    """
    HTTP POST /api/register

    Register a new user account in MongoDB.

    Request Body:
        {
            "username": "alex",
            "full_name": "Alex Morgan",
            "email": "alex@example.com",
            "password": "secret_password",
            "balance": 2480.00,
            "buffer": 500.00,
            "limit_period": "daily",
            "limit_balance": 60.00
        }

    Returns:
        JSON response containing public user object or field error payload.
    """
    data = request.get_json(silent=True) or {}
    success, public_user, err_msg, err_field = AuthService.register_user(data)

    if not success:
        return make_error_response(err_msg, status_code=400, field=err_field)

    # Store username in Flask session
    session["username"] = public_user["username"]
    return jsonify(public_user), 201


@auth_bp.route("/login", methods=["POST"])
def login():
    """
    HTTP POST /api/login

    Authenticate user with username and password credentials.

    Request Body:
        {
            "username": "alex",
            "password": "secret_password"
        }

    Returns:
        JSON response containing user profile or error payload.
    """
    data = request.get_json(silent=True) or {}
    username = data.get("username", "")
    password = data.get("password", "")

    success, public_user, err_msg = AuthService.authenticate_user(username, password)
    if not success:
        return make_error_response(err_msg, status_code=401)

    session["username"] = public_user["username"]
    return jsonify(public_user), 200


@auth_bp.route("/logout", methods=["POST", "GET"])
def logout():
    """
    HTTP POST /api/logout

    Clear current user session.

    Returns:
        JSON boolean response indicating session clear.
    """
    session.pop("username", None)
    return jsonify(True), 200


@auth_bp.route("/me", methods=["GET"])
def me():
    """
    HTTP GET /api/me

    Retrieve profile of the currently logged-in user session. Accepts username parameter or session cookie.

    Returns:
        JSON public user profile or null if not logged in.
    """
    username = session.get("username") or request.args.get("username")
    if not username:
        return jsonify(None), 200

    public_user = AuthService.get_user_profile(username)
    if not public_user:
        session.pop("username", None)
        return jsonify(None), 200

    return jsonify(public_user), 200


@auth_bp.route("/profile/update", methods=["POST", "PUT"])
def update_profile():
    """
    HTTP POST /api/profile/update or PUT /api/profile/update

    Update profile details for the active user session in MongoDB.

    Returns:
        JSON updated user profile or error details.
    """
    data = request.get_json(silent=True) or {}
    username = session.get("username") or data.get("username") or request.args.get("username")

    if not username:
        return make_error_response("Session ended. Please log in again.", status_code=401)

    success, public_user, err_msg, err_field = AuthService.update_user_profile(username, data)
    if not success:
        return make_error_response(err_msg, status_code=400, field=err_field)

    return jsonify(public_user), 200


@auth_bp.route("/profile/delete", methods=["POST", "DELETE"])
def delete_profile():
    """
    HTTP POST /api/profile/delete or DELETE /api/profile/delete

    Permanently delete current user profile and item history from MongoDB.

    Returns:
        JSON status indicator.
    """
    data = request.get_json(silent=True) or {}
    username = session.get("username") or data.get("username") or request.args.get("username")

    if not username:
        return make_error_response("Session ended. Please log in again.", status_code=401)

    success, err_msg = AuthService.delete_user_account(username)
    if not success:
        return make_error_response(err_msg, status_code=400)

    session.pop("username", None)
    return jsonify({"message": "User profile and all associated data deleted successfully.", "deleted": True}), 200
