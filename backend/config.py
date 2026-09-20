"""
Config module for the Spendwise Flask Backend.

Handles environment variable loading, database settings, secret keys,
and SMTP configurations.
"""

import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


class Config:
    """
    Central Configuration class for Spendwise backend.

    Attributes:
        SECRET_KEY (str): Secret key for signing sessions and tokens.
        MONGO_URI (str): Cloud or local MongoDB connection URI.
        DB_NAME (str): Name of the MongoDB database.
        FLASK_PORT (int): Port to run the Flask application.
        FLASK_HOST (str): Host IP to bind the Flask application.
        SMTP_SERVER (str): Outgoing SMTP server address.
        SMTP_PORT (int): SMTP server port.
        SMTP_USER (str): Username for SMTP authentication.
        SMTP_PASSWORD (str): Password for SMTP authentication.
        EMAIL_FROM (str): Sender email address string.
    """

    SECRET_KEY = os.getenv("SECRET_KEY", "spendwise_default_secret_key_2026")
    MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017/spendwise")
    DB_NAME = os.getenv("DB_NAME", "spendwise")
    FLASK_PORT = int(os.getenv("FLASK_PORT", 5001))
    FLASK_HOST = os.getenv("FLASK_HOST", "0.0.0.0")

    # Email Settings
    MAILTRAP_TOKEN = os.getenv("MAILTRAP_TOKEN", "")
    MAILJET_API_KEY = os.getenv("MAILJET_API_KEY", "")
    MAILJET_SECRET_KEY = os.getenv("MAILJET_SECRET_KEY", "")
    SENDGRID_API_KEY = os.getenv("SENDGRID_API_KEY", "")
    BREVO_API_KEY = os.getenv("BREVO_API_KEY", "")
    RESEND_API_KEY = os.getenv("RESEND_API_KEY", "")
    SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
    SMTP_PORT = int(os.getenv("SMTP_PORT", 587))
    SMTP_USER = os.getenv("SMTP_USER", "")
    SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
    EMAIL_FROM = os.getenv("EMAIL_FROM", "Spendwise <onboarding@resend.dev>")

    @classmethod
    def is_smtp_configured(cls) -> bool:
        """
        Check if email service credentials (Mailtrap, Mailjet, SendGrid, Brevo, Resend, or SMTP) are provided.

        Returns:
            bool: True if any email provider credential is set.
        """
        return bool(
            cls.MAILTRAP_TOKEN
            or cls.MAILJET_API_KEY
            or cls.SENDGRID_API_KEY
            or cls.BREVO_API_KEY
            or cls.RESEND_API_KEY
            or (cls.SMTP_USER and cls.SMTP_PASSWORD)
        )
