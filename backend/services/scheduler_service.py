"""
Scheduler service for Spendwise backend.

Manages recurring background jobs for automated period limit renewals
and periodic email reports.
"""

import time
import logging
import threading
from typing import Optional

from backend.database import DatabaseManager
from backend.services.finance_service import FinanceService
from backend.services.email_service import EmailService

logger = logging.getLogger("spendwise.scheduler")


class SchedulerService:
    """
    Background job scheduler managing periodic renewals and automated email reporting.
    """

    _thread: Optional[threading.Thread] = None
    _running: bool = False
    _interval_seconds: int = 300  # Run background check every 5 minutes

    @classmethod
    def start_scheduler(cls, interval_seconds: int = 300) -> None:
        """
        Start the background timer thread for periodic renewals and reports.

        Args:
            interval_seconds (int): Check interval in seconds (default: 300s / 5min).
        """
        if cls._running:
            return

        cls._interval_seconds = interval_seconds
        cls._running = True
        cls._thread = threading.Thread(target=cls._run_loop, daemon=True)
        cls._thread.start()
        logger.info(f"Background renewal & report scheduler started (Interval: {interval_seconds}s).")

    @classmethod
    def stop_scheduler(cls) -> None:
        """
        Stop the background scheduler thread gracefully.
        """
        cls._running = False
        logger.info("Background scheduler stopped.")

    @classmethod
    def _run_loop(cls) -> None:
        """
        Internal infinite loop executing periodic checks.
        """
        while cls._running:
            try:
                cls.execute_periodic_renewals()
            except Exception as e:
                logger.error(f"Error during periodic scheduler run: {e}")
            time.sleep(cls._interval_seconds)

    @classmethod
    def execute_periodic_renewals(cls) -> int:
        """
        Scan all active user documents in MongoDB and renew limit balances if due.

        Returns:
            int: Total number of renewed user accounts.
        """
        col = DatabaseManager.get_users_collection()
        renewed_count = 0

        # Fetch users
        if hasattr(col, "find"):
            try:
                raw_users = list(col.find({}))
            except Exception:
                raw_users = []
        else:
            raw_users = []

        for user_doc in raw_users:
            username = user_doc.get("username")
            if username:
                before_renew = user_doc.get("last_renewed_at")
                updated_doc = FinanceService.check_and_renew_limit(user_doc)
                after_renew = updated_doc.get("last_renewed_at")
                if before_renew != after_renew:
                    renewed_count += 1
                    # Dispatch period summary email report upon automatic renewal
                    EmailService.send_report_email(username)

        if renewed_count > 0:
            logger.info(f"Period scheduler successfully renewed limits for {renewed_count} user(s).")
        return renewed_count
