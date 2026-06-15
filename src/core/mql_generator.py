import json
import os
import re
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

TEMPLATES_DIR = Path(__file__).parent.parent / "prompts" / "templates"
SCHEMAS_DIR = Path(__file__).parent.parent.parent / "data" / "schemas"

_DEFAULT_MODEL = "llama3.2"


def _model() -> str:
    """Active Ollama model, read at call time so eval can switch it via OLLAMA_MODEL."""
    return os.getenv("OLLAMA_MODEL", _DEFAULT_MODEL)

_WRITE_OPS = {
    "$out", "$merge",
    "insertOne", "insertMany",
    "updateOne", "updateMany", "replaceOne",
    "deleteOne", "deleteMany", "drop",
}

# Caches keyed by (database, collection) so the same collection name in two
# different datasets does not collide.
_template_cache: dict[tuple[str | None, str], str] = {}
_schema_cache: dict[tuple[str | None, str], dict] = {}

# Cap example value length in the dynamic schema so a single huge field (e.g. an
# embedded reviews/array document) cannot bloat the prompt.
_MAX_EXAMPLE_LEN = 120


def _get_schema(collection: str, database: str | None = None) -> dict:
    """Return schema dict for *collection*, loading from file or inferring live."""
    key = (database, collection)
    if key in _schema_cache:
        return _schema_cache[key]

    schema_path = SCHEMAS_DIR / f"{collection}.json"
    if schema_path.exists():
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
    else:
        from src.core import schema_inferrer  # avoid circular import at module level
        schema = schema_inferrer.infer(collection, database=database)

    _schema_cache[key] = schema
    return schema


def _truncate(s: str) -> str:
    """Shorten an example/value string so a giant field cannot bloat the prompt."""
    return s if len(s) <= _MAX_EXAMPLE_LEN else s[:_MAX_EXAMPLE_LEN] + "…"


def _schema_fields_to_lines(fields: dict, prefix: str = "") -> list[str]:
    """Render schema fields dict into human-readable bullet lines."""
    lines = []
    for name, meta in fields.items():
        full_name = f"{prefix}.{name}" if prefix else name
        ftype = meta.get("type", "unknown")
        parts = [f"- {full_name}: {ftype}"]

        if "values" in meta:
            vals = ", ".join(str(v) for v in meta["values"][:15])
            parts.append(f"Valores: {_truncate(vals)}")
        elif "example" in meta:
            ex = meta["example"]
            ex_str = f'"{ex}"' if isinstance(ex, str) else str(ex)
            parts.append(f"Ejemplo: {_truncate(ex_str)}")

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


def _load_template(collection: str, database: str | None = None) -> str:
    key = (database, collection)
    if key not in _template_cache:
        path = TEMPLATES_DIR / f"{collection}.txt"
        if path.exists():
            _template_cache[key] = path.read_text(encoding="utf-8")
        else:
            schema = _get_schema(collection, database=database)
            _template_cache[key] = _build_dynamic_template(collection, schema)
    return _template_cache[key]


def _format_user_turn(question: str) -> str:
    """Render a question as the user-turn content the model is trained to expect."""
    return f"Pregunta: {question}\nQuery:"


def history_turns(question: str, query: dict | list) -> list[dict]:
    """Build the two chat turns (user question + assistant MQL) for one resolved
    exchange, ready to be replayed as conversational history on the next call."""
    return [
        {"role": "user", "content": _format_user_turn(question)},
        {"role": "assistant", "content": json.dumps(query, ensure_ascii=False)},
    ]


def _build_messages(
    question: str,
    collection: str,
    history: list[dict] | None = None,
    database: str | None = None,
) -> list[dict]:
    """Build the chat messages for the LLM.

    *history* is an optional list of prior {role, content} turns (alternating
    user/assistant) inserted between the system prompt and the current question
    so the model can resolve anaphoric follow-ups ("¿y ordenadas por año?").
    """
    template = _load_template(collection, database=database)
    lines = template.splitlines()
    cutoff = next(
        (i for i, line in enumerate(lines) if line.startswith("Ahora responde")),
        len(lines),
    )
    system_prompt = "\n".join(lines[:cutoff]).strip()

    messages = [{"role": "system", "content": system_prompt}]
    if history:
        messages.extend(history)
    messages.append({"role": "user", "content": _format_user_turn(question)})
    return messages


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


# Matches an unquoted object key right after '{' or ',' (JS-style: {size: 5}).
_UNQUOTED_KEY = re.compile(r'([{,]\s*)([A-Za-z_$][A-Za-z0-9_$.]*)(\s*:)')
# Matches a trailing comma before a closing } or ].
_TRAILING_COMMA = re.compile(r',(\s*[}\]])')


def _repair_json(text: str) -> str:
    """Best-effort repair of near-JSON the LLM sometimes emits.

    Fixes the two most common formatting slips seen with local models:
      - unquoted object keys:  {size: 5}      -> {"size": 5}
      - trailing commas:       [{...},]       -> [{...}]

    Only structural punctuation is touched; string values are left intact.
    """
    text = _UNQUOTED_KEY.sub(r'\1"\2"\3', text)
    text = _TRAILING_COMMA.sub(r'\1', text)
    return text


def _check_no_writes(query: dict | list) -> None:
    serialized = json.dumps(query)
    for op in _WRITE_OPS:
        if op in serialized:
            raise ValueError(f"Rejected: write operator '{op}' detected")


def generate(
    question: str,
    collection: str,
    history: list[dict] | None = None,
    database: str | None = None,
) -> dict | list:
    """Translate a natural language question into a PyMongo-compatible MQL query.

    Uses an Ollama model (default: llama3.2) running locally at localhost:11434.
    Override the model via the OLLAMA_MODEL env variable.

    Args:
        question:   The natural language question.
        collection: Target MongoDB collection.
        history:    Optional list of prior {role, content} turns (conversational
                    memory) so follow-up questions can resolve references.
        database:   Target database (selects the schema/template context). Defaults
                    to the single-dataset behaviour (sample_mflix).

    Returns:
        dict  -> use with collection.find()
        list  -> use with collection.aggregate()

    Raises:
        ValueError: output is not valid JSON or contains a write operator.
    """
    import ollama

    messages = _build_messages(question, collection, history, database=database)
    response = ollama.chat(
        model=_model(),
        messages=messages,
        options={"temperature": 0.1},
    )
    raw = response.message.content
    json_str = _extract_json(raw)
    try:
        query = json.loads(json_str)
    except json.JSONDecodeError:
        # Retry once after repairing common LLM formatting slips.
        try:
            query = json.loads(_repair_json(json_str))
        except json.JSONDecodeError as exc:
            raise ValueError(f"LLM output is not valid JSON:\n{json_str[:400]}") from exc
    _check_no_writes(query)
    return query
