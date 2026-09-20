"""
Report controller blueprint for Spendwise backend.

Provides REST API endpoints to generate, preview, and send periodic
email summary reports to users.
"""

from flask import Blueprint, request, jsonify, session, Response
from backend.services.email_service import EmailService
from backend.utils.validators import make_error_response

report_bp = Blueprint("report", __name__, url_prefix="/api")


def _get_current_username() -> str:
    """
    Internal helper to resolve session or query username.

    Returns:
        str: Active username or empty string.
    """
    return session.get("username") or request.args.get("username", "") or ""


@report_bp.route("/send-report", methods=["POST"])
def send_report():
    """
    HTTP POST /api/send-report

    Generate and send a financial summary report via email to the logged-in user.

    Request Body:
        {
            "username": "alex"  (optional if logged in via session)
        }

    Returns:
        JSON object with dispatch status and message.
    """
    data = request.get_json(silent=True) or {}
    username = data.get("username") or _get_current_username()

    if not username:
        return make_error_response("Please log in to receive an email report.", status_code=401)

    success, result, err = EmailService.send_report_email(username)
    if not success:
        return make_error_response(err or "Failed to send email report.", status_code=500)

    return jsonify(result), 200


@report_bp.route("/preview-report", methods=["GET"])
def preview_report():
    """
    HTTP GET /api/preview-report

    Preview compiled HTML email summary report in browser.

    Query Parameters:
        username (str): Username to generate report for.

    Returns:
        HTML document response.
    """
    username = request.args.get("username") or _get_current_username()
    if not username:
        return make_error_response("Username is required.", status_code=401)

    success, report, err = EmailService.generate_report_content(username)
    if not success:
        return make_error_response(err or "Failed to generate report preview.", status_code=404)

    return Response(report["html_body"], mimetype="text/html"), 200
