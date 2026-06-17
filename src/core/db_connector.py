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
            raise ValueError("Falta MONGODB_URI en el entorno")
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
    """Ejecuta una consulta de solo lectura contra MongoDB.

    Un dict se trata como filtro (find); una lista, como pipeline (aggregate).
    Siempre se aplica un $limit como red de seguridad para no barrer la
    colección entera sin querer. Por defecto va contra MONGODB_DB_NAME
    (sample_mflix); pasa *database* para apuntar a otro dataset.
    Devuelve los documentos sin el campo '_id'.
    """
    db_name = database or os.getenv("MONGODB_DB_NAME", "sample_mflix")
    db = _get_client()[db_name]
    col = db[collection]

    try:
        if isinstance(query, list):
            # Pipeline de agregación: añado el $limit al final como tope de seguridad
            pipeline = query + [{"$limit": limit}]
            cursor = col.aggregate(pipeline)
        elif isinstance(query, dict):
            cursor = col.find(query, {"_id": 0}, limit=limit)
        else:
            raise ValueError(f"La query debe ser un dict (find) o una lista (aggregate), no {type(query)}")

        return list(cursor)

    except (OperationFailure, PyMongoError) as exc:
        raise OperationFailure(f"Fallo al ejecutar la query en '{collection}': {exc}") from exc


def close() -> None:
    global _client
    if _client is not None:
        _client.close()
        _client = None
