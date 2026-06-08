import json
import os
import re
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

TEMPLATES_DIR = Path(__file__).parent.parent / "prompts" / "templates"
SCHEMAS_DIR = Path(__file__).parent.parent.parent / "data" / "schemas"

_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2")

_WRITE_OPS = {
    "$out", "$merge",
    "insertOne", "insertMany",
    "updateOne", "updateMany", "replaceOne",
    "deleteOne", "deleteMany", "drop",
}

_template_cache: dict[str, str] = {}
_schema_cache: dict[str, dict] = {}


def _get_schema(collection: str) -> dict:
    """Return schema dict for *collection*, loading from file or inferring live."""
    if collection in _schema_cache:
        return _schema_cache[collection]

    schema_path = SCHEMAS_DIR / f"{collection}.json"
    if schema_path.exists():
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
    else:
        from src.core import schema_inferrer  # avoid circular import at module level
        schema = schema_inferrer.infer(collection)

    _schema_cache[collection] = schema
    return schema


def _schema_fields_to_lines(fields: dict, prefix: str = "") -> list[str]:
    """Render schema fields dict into human-readable bullet lines."""
    lines = []
    for name, meta in fields.items():
        full_name = f"{prefix}.{name}" if prefix else name
        ftype = meta.get("type", "unknown")
        parts = [f"- {full_name}: {ftype}"]

        if "values" in meta:
            vals = ", ".join(str(v) for v in meta["values"][:15])
            parts.append(f"Valores: {vals}")
        elif "example" in meta:
            ex = meta["example"]
            ex_str = f'"{ex}"' if isinstance(ex, str) else str(ex)
            parts.append(f"Ejemplo: {ex_str}")

        if meta.get("optional"):
            parts.append("(opcional)")

        lines.append(" — ".join(parts))

        if ftype == "object" and "fields" in meta:
            lines.extend(_schema_fields_to_lines(meta["fields"], prefix=full_name))

    return lines


def _build_dynamic_template(collection: str, schema: dict) -> str:
    """Build a prompt template from an inferred schema when no .txt template exists."""
    schema_lines = "\n".join(_schema_fields_to_lines(schema.get("fields", {})))

    return (
        f'Eres un experto en MongoDB Query Language (MQL). Tu única tarea es convertir'
        f' preguntas en lenguaje natural (español o inglés) en una query MQL válida'
        f' para la colección "{collection}".\n'
        "\n"
        "REGLAS ESTRICTAS:\n"
        "- Responde ÚNICAMENTE con el bloque JSON de la query, sin explicaciones ni texto adicional.\n"
        "- El JSON debe ser parseable directamente. Sin comentarios dentro del JSON.\n"
        "- Para consultas simples usa un objeto JSON (filter para find). Para consultas con"
        " agrupación, ordenación, lookup o múltiples etapas usa un array JSON (pipeline para aggregate).\n"
        "- NUNCA uses operadores de escritura: insertOne, updateMany, deleteMany, drop, $out, $merge.\n"
        "- Si la pregunta es ambigua, genera la query más razonable posible.\n"
        "\n"
        f"ESQUEMA DE LA COLECCIÓN {collection}:\n"
        f"{schema_lines}\n"
        "\n"
        "--- EJEMPLOS GENÉRICOS ---\n"
        "\n"
        "Pregunta: ¿Cuántos documentos hay en total?\n"
        'Query:\n[{"$count": "total"}]\n'
        "\n"
        "---\n"
        "\n"
        "Pregunta: Muéstrame los primeros 5 documentos\n"
        "Query:\n"
        '[{"$limit": 5}]\n'
        "\n"
        "---\n"
        "\n"
        "Pregunta: Ordena por [campo] de mayor a menor y devuelve los 10 primeros\n"
        "Query:\n"
        '[{"$sort": {"campo": -1}}, {"$limit": 10}]\n'
        "\n"
        "---\n"
        "\n"
        "Pregunta: Agrupa por [campo] y cuenta cuántos hay de cada valor\n"
        "Query:\n"
        '[{"$group": {"_id": "$campo", "total": {"$sum": 1}}}, {"$sort": {"total": -1}}]\n'
        "\n"
        "--- FIN EJEMPLOS ---\n"
        "\n"
        "Ahora responde SOLO con la query MQL para la siguiente pregunta:\n"
    )


def _load_template(collection: str) -> str:
    if collection not in _template_cache:
        path = TEMPLATES_DIR / f"{collection}.txt"
        if path.exists():
            _template_cache[collection] = path.read_text(encoding="utf-8")
        else:
            schema = _get_schema(collection)
            _template_cache[collection] = _build_dynamic_template(collection, schema)
    return _template_cache[collection]


def _build_messages(question: str, collection: str) -> list[dict]:
    template = _load_template(collection)
    lines = template.splitlines()
    cutoff = next(
        (i for i, line in enumerate(lines) if line.startswith("Ahora responde")),
        len(lines),
    )
    system_prompt = "\n".join(lines[:cutoff]).strip()
    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"Pregunta: {question}\nQuery:"},
    ]


def _extract_json(text: str) -> str:
    text = text.strip()
    # Strip markdown code block if present
    m = re.search(r"```(?:json)?\s*([\s\S]+?)\s*```", text)
    if m:
        return m.group(1).strip()
    # Find first JSON object or array
    m = re.search(r"(\[[\s\S]*]|\{[\s\S]*\})", text)
    if m:
        return m.group(1).strip()
    return text


def _check_no_writes(query: dict | list) -> None:
    serialized = json.dumps(query)
    for op in _WRITE_OPS:
        if op in serialized:
            raise ValueError(f"Rejected: write operator '{op}' detected")


def generate(question: str, collection: str) -> dict | list:
    """Translate a natural language question into a PyMongo-compatible MQL query.

    Uses an Ollama model (default: llama3.2) running locally at localhost:11434.
    Override the model via the OLLAMA_MODEL env variable.

    Returns:
        dict  -> use with collection.find()
        list  -> use with collection.aggregate()

    Raises:
        ValueError: output is not valid JSON or contains a write operator.
    """
    import ollama

    messages = _build_messages(question, collection)
    response = ollama.chat(
        model=_MODEL,
        messages=messages,
        options={"temperature": 0.1},
    )
    raw = response.message.content
    json_str = _extract_json(raw)
    try:
        query = json.loads(json_str)
    except json.JSONDecodeError as exc:
        raise ValueError(f"LLM output is not valid JSON:\n{json_str[:400]}") from exc
    _check_no_writes(query)
    return query
