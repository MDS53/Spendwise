"""
Item model module for Spendwise backend.

Manages purchase transactions and item records stored in MongoDB 'items' collection.
"""

import uuid
from typing import Dict, Any, List
from datetime import datetime, timezone

from backend.database import DatabaseManager
from backend.utils.helpers import round_money, format_iso_datetime


class ItemModel:
    """
    Item/Expense Data Model and Database Access Object.

    Handles creation and retrieval of user spending items stored in MongoDB.
    """

    @staticmethod
    def create_item_document(
        username: str,
        item_name: str,
        price: float,
        used_emergency_buffer: bool = False,
        buffer_amount_used: float = 0.0,
    ) -> Dict[str, Any]:
        """
        Construct a new Item document dictionary for MongoDB storage.

        Args:
            username (str): Owner username.
            item_name (str): Name or description of the purchased item.
            price (float): Cost of the item.
            used_emergency_buffer (bool): True if emergency buffer covered any portion.
            buffer_amount_used (float): Emergency buffer amount applied.

        Returns:
            Dict[str, Any]: Formatted item document dictionary.
        """
        now_str = format_iso_datetime(datetime.now(timezone.utc))
        return {
            "item_id": str(uuid.uuid4()),
            "username": username.strip(),
            "username_lower": username.strip().lower(),
            "item": item_name.strip(),
            "price": round_money(price),
            "used_emergency_buffer": bool(used_emergency_buffer),
            "buffer_amount_used": round_money(buffer_amount_used),
            "created_at": now_str,
        }

    @classmethod
    def insert_item(cls, item_doc: Dict[str, Any]) -> bool:
        """
        Insert an item document into the MongoDB 'items' collection.

        Args:
            item_doc (Dict[str, Any]): Item payload document.

        Returns:
            bool: True if insert was successful.
        """
        col = DatabaseManager.get_items_collection()
        col.insert_one(item_doc)
        return True

    @classmethod
    def get_items_by_username(cls, username: str, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Retrieve spending items for a given user ordered by purchase date descending.

        Args:
            username (str): User's username.
            limit (int): Maximum number of recent items to return (default: 50).

        Returns:
            List[Dict[str, Any]]: List of clean item records.
        """
        if not username:
            return []
        col = DatabaseManager.get_items_collection()
        target = str(username).strip().lower()

        raw_items = col.find({"username_lower": target})
        if not raw_items:
            raw_items = col.find({"username": username})

        clean_list = []
        for doc in raw_items:
            clean_list.append(
                {
                    "item_id": doc.get("item_id", ""),
                    "item": doc.get("item", ""),
                    "price": round_money(doc.get("price", 0.0)),
                    "used_emergency_buffer": doc.get("used_emergency_buffer", False),
                    "buffer_amount_used": round_money(doc.get("buffer_amount_used", 0.0)),
                    "created_at": doc.get("created_at", ""),
                }
            )

        # Sort by creation date descending
        clean_list.sort(key=lambda x: x.get("created_at", ""), reverse=True)
        return clean_list[:limit]

    @classmethod
    def delete_items_by_username(cls, username: str) -> bool:
        """
        Delete all items associated with a user from MongoDB items collection.

        Args:
            username (str): Username whose items will be deleted.

        Returns:
            bool: True if deleted.
        """
        if not username:
            return False
        col = DatabaseManager.get_items_collection()
        target = str(username).strip().lower()
        if hasattr(col, "delete_many"):
            col.delete_many({"username_lower": target})
            col.delete_many({"username": username})
        return True
