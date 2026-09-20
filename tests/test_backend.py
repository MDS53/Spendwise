"""
Test Suite for Spendwise Modular Python Flask Backend.

Tests user registration, authentication, database persistence,
item insertions, spending limit enforcement, emergency buffer rules,
period limit renewal rollovers, and email report generation.
"""

import os
import sys
import unittest

# Ensure backend package is in Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.app import create_app
from backend.models.user_model import UserModel
from backend.models.item_model import ItemModel
from backend.services.auth_service import AuthService
from backend.services.finance_service import FinanceService
from backend.services.email_service import EmailService
from backend.utils.helpers import round_money, calculate_elapsed_periods
from datetime import datetime, timezone, timedelta


class SpendwiseBackendTestCase(unittest.TestCase):
    """
    Test suite testing all modular components of the Spendwise backend.
    """

    def setUp(self):
        """
        Set up Flask test client before each test.
        """
        self.app = create_app()
        self.app.config["TESTING"] = True
        self.client = self.app.test_client()

    def test_01_user_registration_and_auth(self):
        """
        Test user registration and login workflow.
        """
        reg_payload = {
            "username": "testuser",
            "full_name": "Test User",
            "email": "testuser@example.com",
            "password": "password123",
            "balance": 1000.00,
            "buffer": 200.00,
            "limit_period": "daily",
            "limit_balance": 100.00,
        }

        # 1. Register User
        res = self.client.post("/api/register", json=reg_payload)
        self.assertEqual(res.status_code, 201)
        data = res.get_json()
        self.assertEqual(data["username"], "testuser")
        self.assertEqual(data["balance"], 1000.00)
        self.assertEqual(data["limit_remaining"], 100.00)

        # 2. Login User
        login_res = self.client.post(
            "/api/login", json={"username": "testuser", "password": "password123"}
        )
        self.assertEqual(login_res.status_code, 200)
        login_data = login_res.get_json()
        self.assertEqual(login_data["email"], "testuser@example.com")

    def test_02_item_purchase_within_limit(self):
        """
        Test purchasing an item within normal limit.
        """
        # Register user with limit of $100 and balance of $1000
        reg_payload = {
            "username": "shopper1",
            "full_name": "Shopper One",
            "email": "shopper1@example.com",
            "password": "password123",
            "balance": 1000.00,
            "buffer": 200.00,
            "limit_period": "daily",
            "limit_balance": 100.00,
        }
        self.client.post("/api/register", json=reg_payload)

        # Check purchase eligibility
        check_res = self.client.post(
            "/api/check-purchase",
            json={"username": "shopper1", "item": "Coffee & Snack", "price": 25.00},
        )
        self.assertEqual(check_res.status_code, 200)
        self.assertEqual(check_res.get_json()["decision"], "buy")

        # Execute purchase
        buy_res = self.client.post(
            "/api/buy",
            json={"username": "shopper1", "item": "Coffee & Snack", "price": 25.00},
        )
        self.assertEqual(buy_res.status_code, 200)
        user_res = buy_res.get_json()["user"]
        self.assertEqual(user_res["balance"], 975.00)
        self.assertEqual(user_res["limit_remaining"], 75.00)

    def test_03_emergency_buffer_usage(self):
        """
        Test item purchase exceeding remaining limit but covered by emergency buffer.
        """
        # User has limit remaining $30, buffer $200
        reg_payload = {
            "username": "bufferuser",
            "full_name": "Buffer User",
            "email": "buffer@example.com",
            "password": "password123",
            "balance": 1000.00,
            "buffer": 200.00,
            "limit_period": "daily",
            "limit_balance": 30.00,
        }
        self.client.post("/api/register", json=reg_payload)

        # Buy item costing $50 (Exceeds $30 limit by $20, covered by $200 buffer)
        buy_res = self.client.post(
            "/api/buy",
            json={"username": "bufferuser", "item": "Emergency Jacket", "price": 50.00},
        )
        self.assertEqual(buy_res.status_code, 200)
        result = buy_res.get_json()
        self.assertEqual(result["decision"], "emergency_buy")
        self.assertTrue(result["used_emergency_buffer"])
        self.assertEqual(result["buffer_amount_used"], 20.00)

        # Verify updated user state in database
        user = result["user"]
        self.assertEqual(user["limit_remaining"], 0.0)
        self.assertEqual(user["buffer_used"], 20.00)
        self.assertEqual(user["balance"], 950.00)

    def test_04_period_renewal_and_leftover_rollover(self):
        """
        Test limit period renewal adding leftover limit balance to next period.
        """
        user_doc = UserModel.create_user_document(
            username="rolloveruser",
            full_name="Rollover User",
            email="rollover@example.com",
            password="password123",
            balance=1000.00,
            buffer=200.00,
            limit_period="daily",
            limit_balance=100.00,
        )
        # Set limit remaining to $40 leftover, and simulate last renewal 2 days ago
        user_doc["limit_remaining"] = 40.00
        two_days_ago = (datetime.now(timezone.utc) - timedelta(days=2)).isoformat()
        user_doc["last_renewed_at"] = two_days_ago
        UserModel.save_user(user_doc)

        # Execute check and renewal
        updated_user = FinanceService.check_and_renew_limit(user_doc)
        # Base $100 + Leftover $40 = $140 for new period!
        self.assertEqual(updated_user["limit_remaining"], 140.00)
        self.assertEqual(updated_user["leftover_rollover"], 40.00)

    def test_05_email_report_compilation(self):
        """
        Test periodic email report payload generation.
        """
        reg_payload = {
            "username": "reportuser",
            "full_name": "Report User",
            "email": "reportuser@example.com",
            "password": "password123",
            "balance": 1500.00,
            "buffer": 300.00,
            "limit_period": "weekly",
            "limit_balance": 200.00,
        }
        self.client.post("/api/register", json=reg_payload)
        self.client.post(
            "/api/buy",
            json={"username": "reportuser", "item": "Groceries", "price": 45.00},
        )

        success, report, err = EmailService.generate_report_content("reportuser")
        self.assertTrue(success)
        self.assertEqual(report["to_email"], "reportuser@example.com")
        self.assertIn("Spendwise Weekly Report", report["subject"])
        self.assertIn("Groceries", report["html_body"])

        # Test POST /api/send-report endpoint
        send_res = self.client.post("/api/send-report", json={"username": "reportuser"})
        self.assertEqual(send_res.status_code, 200)


if __name__ == "__main__":
    unittest.main()
