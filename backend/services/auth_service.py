"""
Authentication service for Spendwise backend.

Handles user registration, authentication verification, session lookup,
and duplicate credential checks.
"""

from typing import Tuple, Dict, Any, Optional

from backend.models.user_model import UserModel
from backend.models.item_model import ItemModel
from backend.utils.validators import validate_registration_payload, validate_profile_update_payload
from backend.utils.helpers import round_money


class AuthService:
    """
    Service layer providing authentication logic and user management workflows.
    """

    @classmethod
    def register_user(cls, data: dict) -> Tuple[bool, Optional[Dict[str, Any]], Optional[str], Optional[str]]:
        """
        Register a new user account in MongoDB.

        Args:
            data (dict): Registration payload.

        Returns:
            Tuple[bool, Optional[Dict[str, Any]], Optional[str], Optional[str]]:
                (success, public_user_dict, error_message, field_name)
        """
        is_valid, err_msg, err_field = validate_registration_payload(data)
        if not is_valid:
            return False, None, err_msg, err_field

        username = str(data["username"]).strip()
        email = str(data["email"]).strip()

        # Check existing username
        if UserModel.find_by_username(username):
            return False, None, "That username is taken. Try another one.", "username"

        # Check existing email
        if UserModel.find_by_email(email):
            return False, None, "An account with this email already exists.", "email"

        user_doc = UserModel.create_user_document(
            username=username,
            full_name=data["full_name"],
            email=email,
            password=data["password"],
            balance=data["balance"],
            buffer=data["buffer"],
            limit_period=data["limit_period"],
            limit_balance=data["limit_balance"],
        )

        UserModel.save_user(user_doc)
        public_user = UserModel.to_public_dict(user_doc)
        return True, public_user, None, None

    @classmethod
    def authenticate_user(cls, username: str, password: str) -> Tuple[bool, Optional[Dict[str, Any]], Optional[str]]:
        """
        Authenticate a user by username and password.

        Args:
            username (str): Entered username.
            password (str): Entered plaintext password.

        Returns:
            Tuple[bool, Optional[Dict[str, Any]], Optional[str]]:
                (success, public_user_dict, error_message)
        """
        if not username or not password:
            return False, None, "Username and password are required."

        user_doc = UserModel.find_by_username(username)
        if not user_doc:
            return False, None, "Username or password is incorrect."

        if not UserModel.verify_password(user_doc.get("password_hash", ""), password):
            return False, None, "Username or password is incorrect."

        public_user = UserModel.to_public_dict(user_doc)
        return True, public_user, None

    @classmethod
    def get_user_profile(cls, username: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve sanitized public profile for a username.

        Args:
            username (str): Username to query.

        Returns:
            Optional[Dict[str, Any]]: Public user profile dictionary or None.
        """
        if not username:
            return None

        user_doc = UserModel.find_by_username(username)
        if not user_doc:
            return None

        return UserModel.to_public_dict(user_doc)

    @classmethod
    def update_user_profile(
        cls, username: str, update_data: dict
    ) -> Tuple[bool, Optional[Dict[str, Any]], Optional[str], Optional[str]]:
        """
        Update user profile in MongoDB while enforcing uniqueness and financial constraints.

        Args:
            username (str): Username of target account.
            update_data (dict): Dictionary of fields to update.

        Returns:
            Tuple[bool, Optional[Dict[str, Any]], Optional[str], Optional[str]]:
                (success, updated_public_user_dict, error_message, error_field)
        """
        user_doc = UserModel.find_by_username(username)
        if not user_doc:
            return False, None, "User profile not found.", None

        is_valid, err_msg, err_field = validate_profile_update_payload(update_data, user_doc)
        if not is_valid:
            return False, None, err_msg, err_field

        # Check unique email if updating email
        new_email = update_data.get("email")
        if new_email:
            new_email = str(new_email).strip().lower()
            existing = UserModel.find_by_email(new_email)
            if existing and str(existing.get("username", "")).lower() != username.lower():
                return False, None, "An account with this email already exists.", "email"

        fields_to_update = {}
        if "full_name" in update_data and update_data["full_name"]:
            fields_to_update["full_name"] = str(update_data["full_name"]).strip()
        if "email" in update_data and update_data["email"]:
            fields_to_update["email"] = str(update_data["email"]).strip().lower()
        if "balance" in update_data and update_data["balance"] is not None:
            fields_to_update["balance"] = round_money(update_data["balance"])
        if "buffer" in update_data and update_data["buffer"] is not None:
            fields_to_update["buffer"] = round_money(update_data["buffer"])
        if "limit_period" in update_data and update_data["limit_period"]:
            fields_to_update["limit_period"] = str(update_data["limit_period"]).strip().lower()
        if "limit_balance" in update_data and update_data["limit_balance"] is not None:
            new_limit = round_money(update_data["limit_balance"])
            old_limit = round_money(user_doc.get("limit_balance", 0.0))
            diff = new_limit - old_limit
            fields_to_update["limit_balance"] = new_limit
            new_rem = max(0.0, round_money(user_doc.get("limit_remaining", old_limit) + diff))
            fields_to_update["limit_remaining"] = new_rem

        if fields_to_update:
            UserModel.update_user_fields(username, fields_to_update)
            user_doc.update(fields_to_update)

        return True, UserModel.to_public_dict(user_doc), None, None

    @classmethod
    def delete_user_account(cls, username: str) -> Tuple[bool, Optional[str]]:
        """
        Permanently delete user profile and all associated item history from MongoDB.

        Args:
            username (str): Target user's username.

        Returns:
            Tuple[bool, Optional[str]]: (success, error_message)
        """
        if not username:
            return False, "Username is required."

        user_doc = UserModel.find_by_username(username)
        if not user_doc:
            return False, "User account not found."

        UserModel.delete_user(username)
        ItemModel.delete_items_by_username(username)

        return True, None
