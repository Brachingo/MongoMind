"""
Inferidor de esquema: muestrea N documentos de una colección y devuelve un
esquema con el mismo formato que los ficheros de data/schemas/*.json.

API:
    infer(collection, n)          -> dict   (esquema en memoria)
    infer_and_save(collection, n) -> Path   (lo guarda en data/schemas/)

Desde la CLI:
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
# Los campos de texto con <= estos valores distintos se tratan como enum ("values")
_MAX_ENUM_VALUES = 25


# ── Detección de tipos ─────────────────────────────────────────────────────────

def _py_type(v: Any) -> str:
    """Traduce un valor Python/BSON a la cadena de tipo del esquema."""
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
    # Tipos de BSON (import opcional: solo están si pymongo está instalado)
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


# ── Inferencia ─────────────────────────────────────────────────────────────────

def _infer_fields(docs: list[dict]) -> dict:
    """Infiere los campos a partir de una lista de documentos (un nivel; baja en recursión a los objetos)."""
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
    """Infiere el descriptor de un campo a partir de sus valores no nulos."""
    type_counts: dict[str, int] = defaultdict(int)
    for v in values:
        type_counts[_py_type(v)] += 1

    dominant = _dominant(type_counts)
    presence = len(values) / total_docs  # fracción de documentos que tienen el campo

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

        # Si es un array de strings con pocos valores, lo anoto como enum (p.ej. genres, countries)
        if type_str == "array<string>":
            all_str = sorted({
                item for v in values if isinstance(v, list)
                for item in v if isinstance(item, str)
            })
            if 2 <= len(all_str) <= _MAX_ENUM_VALUES:
                result["values"] = all_str

    else:  # escalar
        result = {"type": dominant}
        result["example"] = _collect_example(values)

        # Igual para strings de baja cardinalidad (p.ej. rated, type)
        if dominant == "string":
            unique = sorted({str(v) for v in values if isinstance(v, str)})
            if 2 <= len(unique) <= _MAX_ENUM_VALUES:
                result["values"] = unique

    if presence < 0.95:
        result["optional"] = True

    return result


def _collect_example(values: list) -> Any:
    """Devuelve el primer valor de ejemplo que no sea trivial (vacío)."""
    for v in values:
        if v is not None and v != "" and v != [] and v != {}:
            return _safe_example(v)
    return values[0] if values else None


def _safe_example(v: Any) -> Any:
    """Convierte tipos BSON a algo serializable a JSON."""
    try:
        json.dumps(v)
        return v
    except (TypeError, ValueError):
        return str(v)


# ── API pública ──────────────────────────────────────────────────────────────

def infer(collection: str, n: int = _DEFAULT_SAMPLE,
          database: str | None = None) -> dict:
    
    from src.core import db_connector  # import local para que el módulo se pueda importar suelto

    docs = db_connector.execute_query(
        collection,
        [{"$sample": {"size": n}}],
        limit=n,
        database=database,
    )
    if not docs:
        raise ValueError(f"La colección '{collection}' no devolvió ningún documento")

    fields = _infer_fields(docs)
    return {
        "collection": collection,
        "description": f"Esquema inferido a partir de {len(docs)} documentos muestreados.",
        "fields": fields,
    }


def infer_and_save(collection: str, n: int = _DEFAULT_SAMPLE) -> Path:
    """Infiere el esquema y lo escribe en data/schemas/{collection}.json.

    Devuelve la ruta del fichero escrito.
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

    parser = argparse.ArgumentParser(description="Infiere el esquema de una colección MongoDB")
    parser.add_argument("collection", help="Nombre de la colección (p.ej. movies)")
    parser.add_argument("--n", type=int, default=_DEFAULT_SAMPLE,
                        help="Número de documentos a muestrear (por defecto: 100)")
    parser.add_argument("--save", action="store_true",
                        help="Guarda el resultado en data/schemas/{collection}.json")
    args = parser.parse_args()

    if args.save:
        path = infer_and_save(args.collection, args.n)
        print(f"Esquema guardado en {path}")
    else:
        schema = infer(args.collection, args.n)
        print(json.dumps(schema, indent=2, ensure_ascii=False, default=str))
