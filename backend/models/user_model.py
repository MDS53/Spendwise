"""
User model module for Spendwise backend.

Encapsulates user data structure, serialization, database queries,
and sanitized public representation.
"""

from typing import Dict, Any, Optional
from datetime import datetime, timezone
from werkzeug.security import generate_password_hash, check_password_hash

from backend.database import DatabaseManager
from backend.utils.helpers import round_money, format_iso_datetime


class UserModel:
    """
    User Data Model and Database Access Object.

    Manages user profile records stored in the MongoDB 'users' collection.
    """

    @staticmethod
    def create_user_document(
        username: str,
        full_name: str,
        email: str,
        password: str,
        balance: float,
        buffer: float,
        limit_period: str,
        limit_balance: float,
    ) -> Dict[str, Any]:
        """
        Construct a new User document dictionary for MongoDB storage.

        Args:
            username (str): Unique username.
            full_name (str): User's full name.
            email (str): User's email address.
            password (str): Plaintext password (will be hashed).
            balance (float): Initial main account balance.
            buffer (float): Emergency buffer total set by user.
            limit_period (str): Limit frequency ('daily', 'weekly', 'monthly').
            limit_balance (float): Base spending limit amount.

        Returns:
            Dict[str, Any]: Formatted user MongoDB document dictionary.
        """
        now_str = format_iso_datetime(datetime.now(timezone.utc))
        pwd_hash = generate_password_hash(password)

        bal_val = round_money(balance)
        buf_val = round_money(buffer)
        lim_val = round_money(limit_balance)
        bal_hash = generate_password_hash(str(bal_val))

        return {
            "username": username.strip(),
            "username_lower": username.strip().lower(),
            "full_name": full_name.strip(),
            "email": email.strip().lower(),
            "password_hash": pwd_hash,
            "balance": bal_val,
            "balance_hash": bal_hash,
            "buffer": buf_val,
            "buffer_used": 0.0,
            "limit_period": limit_period.lower().strip(),
            "limit_balance": lim_val,
            "limit_remaining": lim_val,
            "leftover_rollover": 0.0,
            "created_at": now_str,
            "last_renewed_at": now_str,
        }

    @classmethod
    def find_by_username(cls, username: str) -> Optional[Dict[str, Any]]:
        """
        Find a user record in MongoDB by username.

        Args:
            username (str): Username to search for.

        Returns:
            Optional[Dict[str, Any]]: User document or None if not found.
        """
        if not username:
            return None
        col = DatabaseManager.get_users_collection()
        target = str(username).strip().lower()
        return col.find_one({"username_lower": target}) or col.find_one({"username": username})

    @classmethod
    def find_by_email(cls, email: str) -> Optional[Dict[str, Any]]:
        """
        Find a user record in MongoDB by email address.

        Args:
            email (str): Email address to search for.

        Returns:
            Optional[Dict[str, Any]]: User document or None if not found.
        """
        if not email:
            return None
        col = DatabaseManager.get_users_collection()
        target = str(email).strip().lower()
        return col.find_one({"email": target})

    @classmethod
    def save_user(cls, user_doc: Dict[str, Any]) -> bool:
        """
        Save a new user document to MongoDB.

        Args:
            user_doc (Dict[str, Any]): User document payload.

        Returns:
            bool: True if insert was successful.
        """
        col = DatabaseManager.get_users_collection()
        col.insert_one(user_doc)
        return True

    @classmethod
    def update_user_fields(cls, username: str, update_fields: Dict[str, Any]) -> bool:
        """
        Update specific fields of a user document in MongoDB. Automatically recomputes balance_hash if balance changes.

        Args:
            username (str): Target user's username.
            update_fields (Dict[str, Any]): Dictionary of fields to set.

        Returns:
            bool: True if update succeeded.
        """
        if "balance" in update_fields:
            update_fields["balance_hash"] = generate_password_hash(str(round_money(update_fields["balance"])))
        col = DatabaseManager.get_users_collection()
        col.update_one({"username": username}, {"$set": update_fields})
        return True

    @classmethod
    def delete_user(cls, username: str) -> bool:
        """
        Delete a user document from MongoDB users collection.

        Args:
            username (str): Target user's username.

        Returns:
            bool: True if deleted successfully.
        """
        if not username:
            return False
        col = DatabaseManager.get_users_collection()
        target = str(username).strip().lower()
        if hasattr(col, "delete_one"):
            col.delete_one({"username_lower": target})
            col.delete_one({"username": username})
        return True

    @classmethod
    def verify_password(cls, stored_hash: str, candidate_password: str) -> bool:
        """
        Verify candidate plaintext password against stored hash.

        Args:
            stored_hash (str): Werkzeug password hash string.
            candidate_password (str): Plaintext password to verify.

        Returns:
            bool: True if password matches hash.
        """
        if not stored_hash or not candidate_password:
            return False
        return check_password_hash(stored_hash, candidate_password)

    @classmethod
    def to_public_dict(cls, user_doc: Dict[str, Any]) -> Dict[str, Any]:
        """
        Convert a user MongoDB document into a sanitized, safe public dictionary
        omitting sensitive data like password hashes.

        Args:
            user_doc (Dict[str, Any]): Raw user document from MongoDB.

        Returns:
            Dict[str, Any]: Sanitized dictionary safe for JSON frontend responses.
        """
        if not user_doc:
            return {}

        balance = round_money(user_doc.get("balance", 0.0))
        buffer_total = round_money(user_doc.get("buffer", 0.0))
        buffer_used = round_money(user_doc.get("buffer_used", 0.0))
        buffer_available = max(0.0, round_money(buffer_total - buffer_used))
        available_spendable = max(0.0, round_money(balance - buffer_total))

        limit_balance = round_money(user_doc.get("limit_balance", 0.0))
        limit_remaining = round_money(user_doc.get("limit_remaining", limit_balance))
        leftover_rollover = round_money(user_doc.get("leftover_rollover", 0.0))

        return {
            "username": user_doc.get("username", ""),
            "full_name": user_doc.get("full_name", ""),
            "email": user_doc.get("email", ""),
            "balance": balance,
            "buffer": buffer_total,
            "buffer_used": buffer_used,
            "buffer_available": buffer_available,
            "limit_period": user_doc.get("limit_period", "daily"),
            "limit_balance": limit_balance,
            "limit_remaining": limit_remaining,
            "leftover_rollover": leftover_rollover,
            "available": available_spendable,
            "created_at": user_doc.get("created_at", ""),
            "last_renewed_at": user_doc.get("last_renewed_at", ""),
        }
