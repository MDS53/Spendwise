"""
Finance service for Spendwise backend.

Contains core financial domain logic:
- Purchase checks against remaining limit, main balance, and emergency buffer.
- Purchase execution, inserting item into database and updating user profile.
- Automatic limit renewal with leftover rollover addition.
"""

from typing import Tuple, Dict, Any, Optional, List
from datetime import datetime, timezone

from backend.models.user_model import UserModel
from backend.models.item_model import ItemModel
from backend.utils.helpers import (
    round_money,
    parse_iso_datetime,
    format_iso_datetime,
    calculate_elapsed_periods,
)
from backend.utils.validators import validate_purchase_payload


class FinanceService:
    """
    Finance business logic layer enforcing spending controls,
    emergency buffer rules, and period renewal rollovers.
    """

    @classmethod
    def check_and_renew_limit(cls, user_doc: Dict[str, Any]) -> Dict[str, Any]:
        """
        Check if the user's spending limit period has elapsed, and perform renewal with rollover if due.

        Rollover Rule:
        Leftover limit balance from the previous period is added to the base limit balance
        for the new period. Emergency buffer usage is reset to 0.

        Args:
            user_doc (Dict[str, Any]): User record dictionary from MongoDB.

        Returns:
            Dict[str, Any]: Updated user document dictionary.
        """
        if not user_doc:
            return user_doc

        username = user_doc.get("username", "")
        period = user_doc.get("limit_period", "daily")
        last_renewed_str = user_doc.get("last_renewed_at") or user_doc.get("created_at")

        last_renewed_dt = parse_iso_datetime(last_renewed_str)
        now_dt = datetime.now(timezone.utc)

        elapsed_periods = calculate_elapsed_periods(last_renewed_dt, now_dt, period)

        if elapsed_periods >= 1:
            base_limit = round_money(user_doc.get("limit_balance", 0.0))
            current_limit_remaining = round_money(user_doc.get("limit_remaining", 0.0))

            # Calculate leftover limit balance to rollover
            leftover = max(0.0, current_limit_remaining)

            # New limit balance = base limit + rolled over leftover balance
            new_limit_remaining = round_money(base_limit + leftover)
            accumulated_rollover = round_money(user_doc.get("leftover_rollover", 0.0) + leftover)

            new_renewed_str = format_iso_datetime(now_dt)

            update_payload = {
                "limit_remaining": new_limit_remaining,
                "buffer_used": 0.0,  # Reset buffer usage for the new period
                "leftover_rollover": accumulated_rollover,
                "last_renewed_at": new_renewed_str,
            }

            # Update document in memory and database
            user_doc.update(update_payload)
            UserModel.update_user_fields(username, update_payload)

        return user_doc

    @classmethod
    def evaluate_purchase(
        cls, username: str, item_name: str, price: float
    ) -> Tuple[bool, Dict[str, Any], Optional[str]]:
        """
        Evaluate whether a user can afford a proposed purchase without making database mutations.

        Args:
            username (str): Target user's username.
            item_name (str): Name of item.
            price (float): Price of item.

        Returns:
            Tuple[bool, Dict[str, Any], Optional[str]]:
                (is_affordable, verdict_dictionary, error_message)
        """
        user_doc = UserModel.find_by_username(username)
        if not user_doc:
            return False, {}, "User profile not found."

        # Execute renewal check first
        user_doc = cls.check_and_renew_limit(user_doc)

        price = round_money(price)
        balance = round_money(user_doc.get("balance", 0.0))
        buffer_total = round_money(user_doc.get("buffer", 0.0))
        buffer_used = round_money(user_doc.get("buffer_used", 0.0))
        buffer_available = max(0.0, round_money(buffer_total - buffer_used))
        spendable_without_buffer = max(0.0, round_money(balance - buffer_total))

        limit_remaining = round_money(user_doc.get("limit_remaining", 0.0))
        period = user_doc.get("limit_period", "daily")

        reasons: List[str] = []

        if price > limit_remaining:
            reasons.append("limit")

        if price > balance:
            reasons.append("balance")
        elif price > spendable_without_buffer:
            reasons.append("buffer")

        # Emergency buffer evaluation
        can_use_emergency_buffer = False
        buffer_amount_needed = 0.0

        if price > limit_remaining and price <= balance:
            needed = round_money(price - limit_remaining)
            if needed <= buffer_available:
                can_use_emergency_buffer = True
                buffer_amount_needed = needed

        # Determine decision outcome
        if not reasons:
            decision = "buy"
        elif can_use_emergency_buffer:
            decision = "emergency_buy"
        else:
            decision = "no"

        verdict = {
            "decision": decision,
            "reasons": reasons,
            "item": item_name,
            "price": price,
            "limit_period": period,
            "limit_remaining": limit_remaining,
            "balance": balance,
            "buffer": buffer_total,
            "buffer_used": buffer_used,
            "buffer_available": buffer_available,
            "available": spendable_without_buffer,
            "can_use_emergency_buffer": can_use_emergency_buffer,
            "buffer_amount_needed": buffer_amount_needed,
        }

        return True, verdict, None

    @classmethod
    def execute_purchase(
        cls, username: str, item_name: str, price: float
    ) -> Tuple[bool, Dict[str, Any], Optional[str]]:
        """
        Execute purchase transaction, update user balance & limits in MongoDB,
        and insert item record into the database.

        Args:
            username (str): Target user's username.
            item_name (str): Item description.
            price (float): Item cost.

        Returns:
            Tuple[bool, Dict[str, Any], Optional[str]]:
                (success, purchase_result_dict, error_message)
        """
        user_doc = UserModel.find_by_username(username)
        if not user_doc:
            return False, {}, "User session expired or user not found."

        # Ensure limit renewal state is up to date
        user_doc = cls.check_and_renew_limit(user_doc)

        success, verdict, err = cls.evaluate_purchase(username, item_name, price)
        if not success:
            return False, {}, err

        decision = verdict.get("decision")
        if decision == "no":
            # Reject transaction with explicit reason
            reasons_str = ", ".join(verdict.get("reasons", []))
            return False, verdict, f"Purchase declined. Reasons: {reasons_str}."

        price = verdict["price"]
        balance = verdict["balance"]
        limit_remaining = verdict["limit_remaining"]
        buffer_used = verdict["buffer_used"]

        used_emergency_buffer = False
        buffer_amount_used = 0.0

        if decision == "buy":
            # Normal purchase within spending limit
            new_limit_remaining = round_money(limit_remaining - price)
            new_balance = round_money(balance - price)
            new_buffer_used = buffer_used
        else:  # 'emergency_buy'
            # Purchase exceeds limit but covered by emergency buffer
            used_emergency_buffer = True
            buffer_amount_used = round_money(price - limit_remaining)
            new_limit_remaining = 0.0
            new_balance = round_money(balance - price)
            new_buffer_used = round_money(buffer_used + buffer_amount_used)

        # Update MongoDB User Document
        update_fields = {
            "balance": new_balance,
            "limit_remaining": new_limit_remaining,
            "buffer_used": new_buffer_used,
        }
        UserModel.update_user_fields(username, update_fields)
        user_doc.update(update_fields)

        # Insert item into MongoDB 'items' collection
        item_doc = ItemModel.create_item_document(
            username=username,
            item_name=item_name,
            price=price,
            used_emergency_buffer=used_emergency_buffer,
            buffer_amount_used=buffer_amount_used,
        )
        ItemModel.insert_item(item_doc)

        # Build response result containing fresh public user profile
        public_user = UserModel.to_public_dict(user_doc)
        result = {
            "message": "Item purchased successfully!",
            "purchased_item": ItemModel.to_clean_dict(item_doc),
            "user": public_user,
            "decision": decision,
            "used_emergency_buffer": used_emergency_buffer,
            "buffer_amount_used": buffer_amount_used,
        }

        return True, result, None

    @classmethod
    def get_user_items(cls, username: str, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Retrieve all items added by a user from the database.

        Args:
            username (str): Target user's username.
            limit (int): Max item count to return.

        Returns:
            List[Dict[str, Any]]: List of item documents.
        """
        return ItemModel.get_items_by_username(username, limit=limit)
