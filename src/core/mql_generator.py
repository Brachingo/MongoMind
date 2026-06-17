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
    """Modelo de Ollama activo. Lo leo en cada llamada para que eval pueda cambiarlo con OLLAMA_MODEL."""
    return os.getenv("OLLAMA_MODEL", _DEFAULT_MODEL)

_WRITE_OPS = {
    "$out", "$merge",
    "insertOne", "insertMany",
    "updateOne", "updateMany", "replaceOne",
    "deleteOne", "deleteMany", "drop",
}

# Cachés indexadas por (database, collection) para que el mismo nombre de
# colección en dos datasets distintos no se pise.
_template_cache: dict[tuple[str | None, str], str] = {}
_schema_cache: dict[tuple[str | None, str], dict] = {}

# Tope de longitud del valor de ejemplo en el esquema dinámico, para que un solo
# campo enorme (p.ej. un array/objeto de reviews incrustado) no infle el prompt.
_MAX_EXAMPLE_LEN = 120


def _get_schema(collection: str, database: str | None = None) -> dict:
    """Devuelve el esquema de *collection*, leyéndolo del fichero o infiriéndolo al vuelo."""
    key = (database, collection)
    if key in _schema_cache:
        return _schema_cache[key]

    schema_path = SCHEMAS_DIR / f"{collection}.json"
    if schema_path.exists():
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
    else:
        from src.core import schema_inferrer  # import aquí para evitar el ciclo de importación
        schema = schema_inferrer.infer(collection, database=database)

    _schema_cache[key] = schema
    return schema


def _truncate(s: str) -> str:
    """Acorta una cadena de ejemplo/valor para que un campo gigante no infle el prompt."""
    return s if len(s) <= _MAX_EXAMPLE_LEN else s[:_MAX_EXAMPLE_LEN] + "…"


def _schema_fields_to_lines(fields: dict, prefix: str = "") -> list[str]:
    """Convierte el dict de campos del esquema en líneas legibles tipo bullet."""
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
    """Construye una plantilla de prompt a partir del esquema inferido cuando no hay un .txt."""
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
    """Da a la pregunta el formato de turno de usuario que el modelo espera."""
    return f"Pregunta: {question}\nQuery:"


def history_turns(question: str, query: dict | list) -> list[dict]:
    """Construye los dos turnos (pregunta del usuario + MQL del asistente) de un
    intercambio ya resuelto, listos para reinyectarlos como historial en la siguiente llamada."""
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
    """Arma la lista de mensajes para el LLM.

    *history* es una lista opcional de turnos previos {role, content} (alternando
    usuario/asistente) que meto entre el system prompt y la pregunta actual, para
    que el modelo resuelva follow-ups anafóricos ("¿y ordenadas por año?").
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
    # Quito el bloque de código markdown si viene envuelto
    m = re.search(r"```(?:json)?\s*([\s\S]+?)\s*```", text)
    if m:
        return m.group(1).strip()
    # Busco el primer objeto o array JSON
    m = re.search(r"(\[[\s\S]*]|\{[\s\S]*\})", text)
    if m:
        return m.group(1).strip()
    return text


# Clave de objeto sin comillas justo tras '{' o ',' (estilo JS: {size: 5}).
_UNQUOTED_KEY = re.compile(r'([{,]\s*)([A-Za-z_$][A-Za-z0-9_$.]*)(\s*:)')
# Coma sobrante antes de un } o ] de cierre.
_TRAILING_COMMA = re.compile(r',(\s*[}\]])')


def _repair_json(text: str) -> str:
    """Reparación best-effort del casi-JSON que a veces suelta el LLM.

    Arregla los dos despistes de formato más habituales en modelos locales:
      - claves sin comillas:  {size: 5}      -> {"size": 5}
      - comas sobrantes:      [{...},]       -> [{...}]

    Solo toco la puntuación estructural; los valores string quedan intactos.
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
    """Traduce una pregunta en lenguaje natural a una query MQL para PyMongo.

    Usa un modelo de Ollama (por defecto llama3.2) corriendo en local en
    localhost:11434. El modelo se puede cambiar con la variable OLLAMA_MODEL.

    *history* es la memoria conversacional (turnos previos) para resolver
    referencias en los follow-ups; *database* elige el contexto de
    esquema/plantilla (por defecto sample_mflix).

    Devuelve un dict (para find) o una lista (para aggregate). Lanza ValueError
    si la salida no es JSON válido o contiene un operador de escritura.
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
        # Reintento una vez tras reparar los despistes de formato típicos del LLM.
        try:
            query = json.loads(_repair_json(json_str))
        except json.JSONDecodeError as exc:
            raise ValueError(f"La salida del LLM no es JSON válido:\n{json_str[:400]}") from exc
    _check_no_writes(query)
    return query
