"""
Database connection manager for Spendwise Flask Backend.

Manages Cloud MongoDB Atlas or local MongoDB connection lifecycle via PyMongo.
Includes an in-memory database store fallback if MongoDB is unreachable during setup.
"""

import sys
import logging
from typing import Dict, Any, Optional
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError

from backend.config import Config

logger = logging.getLogger("spendwise.database")
logging.basicConfig(level=logging.INFO)


class DatabaseManager:
    """
    Database connection manager singleton.

    Handles connection pooling to Cloud MongoDB Atlas or local MongoDB instance,
    providing access to 'users' and 'items' collections.
    """

    _client: Optional[MongoClient] = None
    _db = None
    _is_mock: bool = False
    _mock_data: Dict[str, Dict[str, Any]] = {"users": {}, "items": []}

    @classmethod
    def initialize(cls) -> None:
        """
        Initialize the MongoDB database connection.

        Attempts connection to MONGO_URI (Cloud Atlas or local).
        If connection times out or fails, falls back to in-memory store
        to guarantee API responsiveness.
        """
        if cls._client is not None:
            return

        mongo_uri = Config.MONGO_URI
        db_name = Config.DB_NAME

        try:
            logger.info(f"Connecting to MongoDB database at URI: {mongo_uri[:30]}...")
            cls._client = MongoClient(mongo_uri, serverSelectionTimeoutMS=2500)
            # Execute quick server ping to test connectivity
            cls._client.admin.command("ping")
            cls._db = cls._client[db_name]
            cls._is_mock = False
            logger.info(f"Successfully connected to MongoDB database: '{db_name}'!")
            cls._create_indexes()
        except (ConnectionFailure, ServerSelectionTimeoutError, Exception) as e:
            logger.warning(
                f"Could not connect to live MongoDB instance ({e}). "
                f"Using fast In-Memory fallback database for development."
            )
            cls._is_mock = True
            cls._db = None

    @classmethod
    def _create_indexes(cls) -> None:
        """
        Create unique indexes on MongoDB collections for optimization.
        """
        if cls._db is not None and not cls._is_mock:
            try:
                cls._db.users.create_index("username", unique=True)
                cls._db.users.create_index("email", unique=True)
                cls._db.items.create_index("username")
                cls._db.items.create_index("created_at")
            except Exception as e:
                logger.warning(f"Error creating database indexes: {e}")

    @classmethod
    def get_db(cls):
        """
        Get the active database instance.

        Returns:
            Database or None: PyMongo Database object or None if using mock mode.
        """
        if cls._client is None and not cls._is_mock:
            cls.initialize()
        return cls._db

    @classmethod
    def is_mock(cls) -> bool:
        """
        Check if the database is running in mock/in-memory fallback mode.

        Returns:
            bool: True if using mock fallback store, False if using real MongoDB.
        """
        return cls._is_mock

    @classmethod
    def get_users_collection(cls):
        """
        Access the 'users' collection or mock accessor.

        Returns:
            Collection or UserMockCollection: Users collection object.
        """
        cls.initialize()
        if not cls._is_mock and cls._db is not None:
            return cls._db.users
        return cls._MockCollection("users", cls._mock_data)

    @classmethod
    def get_items_collection(cls):
        """
        Access the 'items' collection or mock accessor.

        Returns:
            Collection or ItemMockCollection: Items collection object.
        """
        cls.initialize()
        if not cls._is_mock and cls._db is not None:
            return cls._db.items
        return cls._MockCollection("items", cls._mock_data)

    class _MockCollection:
        """
        In-memory MongoDB-like collection wrapper for zero-dependency local testing.
        """

        def __init__(self, name: str, data_store: Dict[str, Any]):
            """
            Initialize mock collection wrapper.

            Args:
                name (str): Collection name ('users' or 'items').
                data_store (dict): Global mock data storage dictionary.
            """
            self.name = name
            self.store = data_store

        def find_one(self, query: dict) -> Optional[dict]:
            """
            Find a single document matching query.

            Args:
                query (dict): Search criteria.

            Returns:
                Optional[dict]: Matching record or None.
            """
            if self.name == "users":
                users_map = self.store["users"]
                if "username" in query:
                    target = str(query["username"]).lower()
                    for k, u in users_map.items():
                        if k.lower() == target:
                            return dict(u)
                if "email" in query:
                    target = str(query["email"]).lower()
                    for k, u in users_map.items():
                        if u.get("email", "").lower() == target:
                            return dict(u)
            return None

        def insert_one(self, document: dict) -> Any:
            """
            Insert a single document into mock store.

            Args:
                document (dict): Document data.

            Returns:
                MockInsertResult: Mock insertion result.
            """
            doc_copy = dict(document)
            if self.name == "users":
                username_key = str(doc_copy["username"]).lower()
                self.store["users"][username_key] = doc_copy
            elif self.name == "items":
                self.store["items"].append(doc_copy)

            class MockInsertResult:
                def __init__(self, inserted_id):
                    self.inserted_id = inserted_id

            return MockInsertResult(doc_copy.get("_id", "mock_id_123"))

        def update_one(self, query: dict, update: dict) -> Any:
            """
            Update a document matching query.

            Args:
                query (dict): Filter query.
                update (dict): Update operations ($set, $inc, etc.).

            Returns:
                dict: Update status summary.
            """
            if self.name == "users" and "username" in query:
                user_key = str(query["username"]).lower()
                user = self.store["users"].get(user_key)
                if user and "$set" in update:
                    user.update(update["$set"])
                    return {"matched_count": 1, "modified_count": 1}
            return {"matched_count": 0, "modified_count": 0}

        def find(self, query: dict) -> list:
            """
            Find all documents matching query.

            Args:
                query (dict): Filter dictionary.

            Returns:
                list: List of matching documents.
            """
            results = []
            if self.name == "items":
                target_user = str(query.get("username", "")).lower()
                for item in self.store["items"]:
                    if str(item.get("username", "")).lower() == target_user:
                        results.append(dict(item))
            # Sort descending by created_at
            results.sort(key=lambda x: x.get("created_at", ""), reverse=True)
            return results
