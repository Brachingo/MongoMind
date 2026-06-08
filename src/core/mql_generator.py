import json
import os
import re
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

TEMPLATES_DIR = Path(__file__).parent.parent / "prompts" / "templates"

_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2")

_WRITE_OPS = {
    "$out", "$merge",
    "insertOne", "insertMany",
    "updateOne", "updateMany", "replaceOne",
    "deleteOne", "deleteMany", "drop",
}

_template_cache: dict[str, str] = {}


def _load_template(collection: str) -> str:
    if collection not in _template_cache:
        path = TEMPLATES_DIR / f"{collection}.txt"
        if not path.exists():
            path = TEMPLATES_DIR / "movies.txt"
        _template_cache[collection] = path.read_text(encoding="utf-8")
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
