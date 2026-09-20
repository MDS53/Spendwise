"""
Spendwise Backend Application Entrypoint.

Flask REST API application for user profile management, MongoDB Atlas storage,
spending limit enforcement, emergency buffer rules, period rollover renewals,
and periodic email reports.
"""

import sys
import os
import logging
from flask import Flask, jsonify, request
from flask_cors import CORS

# Add root directory to sys.path for clean package imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.config import Config
from backend.database import DatabaseManager
from backend.controllers.auth_controller import auth_bp
from backend.controllers.finance_controller import finance_bp
from backend.controllers.report_controller import report_bp
from backend.services.scheduler_service import SchedulerService

# Set up logger
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("spendwise.app")


def create_app() -> Flask:
    """
    Application Factory constructing Flask app instance.

    Configures CORS, session secret key, database initialization,
    blueprints registration, and error handlers.

    Returns:
        Flask: Initialized Flask application instance.
    """
    app = Flask(__name__, static_folder="../", static_url_path="")
    app.config["SECRET_KEY"] = Config.SECRET_KEY

    # Enable CORS for all cross-origin requests from frontend
    CORS(app, supports_credentials=True)

    @app.after_request
    def handle_cors(response):
        origin = request.headers.get("Origin")
        if origin:
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Access-Control-Allow-Credentials"] = "true"
            response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization, X-Requested-With"
            response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
        return response

    # Initialize Database connection
    DatabaseManager.initialize()

    # Register Blueprints
    app.register_blueprint(auth_bp)
    app.register_blueprint(finance_bp)
    app.register_blueprint(report_bp)

    @app.route("/api/health", methods=["GET"])
    def health_check():
        """
        HTTP GET /api/health

        Health check endpoint for server and database connectivity monitoring.

        Returns:
            JSON object status indicator.
        """
        return jsonify(
            {
                "status": "online",
                "app": "Spendwise Modular Backend",
                "database_mode": "mock" if DatabaseManager.is_mock() else "live_mongodb",
                "smtp_configured": Config.is_smtp_configured(),
            }
        ), 200

    @app.errorhandler(404)
    def not_found_handler(e):
        """
        Custom 404 handler for undefined API routes.
        """
        return jsonify({"error": "Endpoint not found."}), 404

    @app.errorhandler(500)
    def internal_server_error_handler(e):
        """
        Custom 500 handler for unexpected server errors.
        """
        logger.error(f"Internal server error: {e}")
        return jsonify({"error": "An unexpected server error occurred."}), 500

    return app


# Construct app instance
app = create_app()

if __name__ == "__main__":
    # Start background scheduler for automated limit renewals & emails
    SchedulerService.start_scheduler(interval_seconds=300)

    logger.info(f"Starting Spendwise Flask Server on http://{Config.FLASK_HOST}:{Config.FLASK_PORT}")
    app.run(host=Config.FLASK_HOST, port=Config.FLASK_PORT, debug=True)
