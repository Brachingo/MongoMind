import os
import certifi
from dotenv import load_dotenv
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure, OperationFailure, PyMongoError

load_dotenv()

_client: MongoClient | None = None


def _get_client() -> MongoClient:
    global _client
    if _client is None:
        uri = os.getenv("MONGODB_URI")
        if not uri:
            raise ValueError("MONGODB_URI not set in environment")
        _client = MongoClient(
            uri,
            serverSelectionTimeoutMS=10000,
            tlsCAFile=certifi.where(),
        )
    return _client


def execute_query(
    collection: str,
    query: dict | list,
    limit: int = 100,
    database: str | None = None,
) -> list[dict]:
    """Run a read-only query against MongoDB.

    Args:
        collection: Collection name within the target database.
        query: A filter dict  → runs find(query)
               A pipeline list → runs aggregate(query)
        limit: Max documents returned (guards against accidental full scans).
        database: Target database name. Defaults to MONGODB_DB_NAME (sample_mflix),
            so existing single-dataset callers are unaffected.

    Returns:
        List of documents with '_id' removed.

    Raises:
        ValueError: If query type is invalid.
        ConnectionFailure: If Atlas is unreachable.
        OperationFailure: If the query is rejected by MongoDB (bad syntax, auth, etc.).
    """
    db_name = database or os.getenv("MONGODB_DB_NAME", "sample_mflix")
    db = _get_client()[db_name]
    col = db[collection]

    try:
        if isinstance(query, list):
            # Aggregation pipeline — append $limit as a safety guard
            pipeline = query + [{"$limit": limit}]
            cursor = col.aggregate(pipeline)
        elif isinstance(query, dict):
            cursor = col.find(query, {"_id": 0}, limit=limit)
        else:
            raise ValueError(f"query must be a dict (find) or list (aggregate), got {type(query)}")

        return list(cursor)

    except (OperationFailure, PyMongoError) as exc:
        raise OperationFailure(f"Query execution failed on '{collection}': {exc}") from exc


def close() -> None:
    global _client
    if _client is not None:
        _client.close()
        _client = None
