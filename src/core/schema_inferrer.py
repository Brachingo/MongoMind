"""
Schema inferrer — samples N documents from a MongoDB collection and produces
a schema dict in the same format as data/schemas/*.json.

Public API:
    infer(collection, n)          -> dict   (schema in memory)
    infer_and_save(collection, n) -> Path   (saves to data/schemas/)

CLI usage:
    python -m src.core.schema_inferrer movies
    python -m src.core.schema_inferrer movies --n 200 --save
"""
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

SCHEMAS_DIR = Path(__file__).parent.parent.parent / "data" / "schemas"
_DEFAULT_SAMPLE = 100
# String fields with <= this many distinct values get an enum "values" list
_MAX_ENUM_VALUES = 25


# ── Type detection ─────────────────────────────────────────────────────────────

def _py_type(v: Any) -> str:
    """Map a Python / BSON value to a schema type string."""
    if v is None:
        return "null"
    if isinstance(v, bool):
        return "boolean"
    if isinstance(v, int):
        return "integer"
    if isinstance(v, float):
        return "float"
    if isinstance(v, list):
        return "array"
    if isinstance(v, dict):
        return "object"
    # BSON types (optional import — only present when pymongo is installed)
    try:
        from datetime import datetime
        from bson import ObjectId, Decimal128
        if isinstance(v, datetime):
            return "date"
        if isinstance(v, ObjectId):
            return "objectid"
        if isinstance(v, Decimal128):
            return "float"
    except ImportError:
        pass
    return "string"


def _dominant(type_counts: dict[str, int]) -> str:
    type_counts = {t: c for t, c in type_counts.items() if t != "null"}
    if not type_counts:
        return "null"
    return max(type_counts, key=type_counts.get)


# ── Core inference ─────────────────────────────────────────────────────────────

def _infer_fields(docs: list[dict]) -> dict:
    """Infer schema fields from a list of documents (one level, recurses for objects)."""
    all_keys: set[str] = set()
    for doc in docs:
        all_keys.update(doc.keys())
    all_keys.discard("_id")

    fields: dict = {}
    for key in sorted(all_keys):
        values = [doc[key] for doc in docs if key in doc and doc[key] is not None]
        if not values:
            continue
        fields[key] = _infer_field(values, total_docs=len(docs))

    return fields


def _infer_field(values: list, total_docs: int) -> dict:
    """Infer the schema descriptor for a single field given its non-null values."""
    type_counts: dict[str, int] = defaultdict(int)
    for v in values:
        type_counts[_py_type(v)] += 1

    dominant = _dominant(type_counts)
    presence = len(values) / total_docs  # fraction of docs that have this field

    if dominant == "object":
        sub_docs = [v for v in values if isinstance(v, dict)]
        result: dict = {"type": "object", "fields": _infer_fields(sub_docs)}

    elif dominant == "array":
        flat: list = [item for v in values if isinstance(v, list) for item in v if item is not None]
        if flat:
            item_counts: dict[str, int] = defaultdict(int)
            for item in flat:
                item_counts[_py_type(item)] += 1
            dom_item = _dominant(item_counts)
            type_str = f"array<{dom_item}>"
        else:
            type_str = "array"

        result = {"type": type_str}

        non_empty = [v for v in values if isinstance(v, list) and v]
        if non_empty:
            result["example"] = _safe_example(non_empty[0])

        # Enum hint for string arrays (e.g. genres, countries)
        if type_str == "array<string>":
            all_str = sorted({
                item for v in values if isinstance(v, list)
                for item in v if isinstance(item, str)
            })
            if 2 <= len(all_str) <= _MAX_ENUM_VALUES:
                result["values"] = all_str

    else:  # scalar
        result = {"type": dominant}
        result["example"] = _collect_example(values)

        # Enum hint for low-cardinality string fields (e.g. rated, type)
        if dominant == "string":
            unique = sorted({str(v) for v in values if isinstance(v, str)})
            if 2 <= len(unique) <= _MAX_ENUM_VALUES:
                result["values"] = unique

    if presence < 0.95:
        result["optional"] = True

    return result


def _collect_example(values: list) -> Any:
    """Return first non-trivial example value."""
    for v in values:
        if v is not None and v != "" and v != [] and v != {}:
            return _safe_example(v)
    return values[0] if values else None


def _safe_example(v: Any) -> Any:
    """Convert BSON types to JSON-serialisable equivalents."""
    try:
        json.dumps(v)
        return v
    except (TypeError, ValueError):
        return str(v)


# ── Public API ─────────────────────────────────────────────────────────────────

def infer(collection: str, n: int = _DEFAULT_SAMPLE,
          database: str | None = None) -> dict:
    """Sample n documents from *collection* and return an inferred schema dict.

    *database* selects the target MongoDB database (defaults to MONGODB_DB_NAME).

    The output format mirrors data/schemas/*.json:
    {
        "collection": str,
        "description": str,
        "fields": { field_name: { "type": ..., "example": ..., ... }, ... }
    }
    """
    from src.core import db_connector  # local import to keep module import-safe

    docs = db_connector.execute_query(
        collection,
        [{"$sample": {"size": n}}],
        limit=n,
        database=database,
    )
    if not docs:
        raise ValueError(f"No documents returned from collection '{collection}'")

    fields = _infer_fields(docs)
    return {
        "collection": collection,
        "description": f"Schema inferred from {len(docs)} sampled documents.",
        "fields": fields,
    }


def infer_and_save(collection: str, n: int = _DEFAULT_SAMPLE) -> Path:
    """Infer schema and write it to data/schemas/{collection}.json.

    Returns the path of the written file.
    """
    schema = infer(collection, n)
    SCHEMAS_DIR.mkdir(parents=True, exist_ok=True)
    path = SCHEMAS_DIR / f"{collection}.json"
    path.write_text(
        json.dumps(schema, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )
    return path


# ── CLI ────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Infer MongoDB collection schema")
    parser.add_argument("collection", help="Collection name (e.g. movies)")
    parser.add_argument("--n", type=int, default=_DEFAULT_SAMPLE,
                        help="Number of documents to sample (default: 100)")
    parser.add_argument("--save", action="store_true",
                        help="Save result to data/schemas/{collection}.json")
    args = parser.parse_args()

    if args.save:
        path = infer_and_save(args.collection, args.n)
        print(f"Schema saved to {path}")
    else:
        schema = infer(args.collection, args.n)
        print(json.dumps(schema, indent=2, ensure_ascii=False, default=str))
