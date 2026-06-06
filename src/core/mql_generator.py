import ast
import json
import re
from pathlib import Path
from dotenv import load_dotenv
import warnings
warnings.filterwarnings("ignore")
load_dotenv()

SCHEMAS_DIR = Path(__file__).parent.parent.parent / "data" / "schemas"
_MODEL_NAME = "Chirayu/nl2mongo"

_model = None
_tokenizer = None
_device = None

_WRITE_OPS = {
    "$out", "$merge", "insertOne", "insertMany",
    "updateOne", "updateMany", "replaceOne",
    "deleteOne", "deleteMany", "drop",
}


def _load_model():
    global _model, _tokenizer, _device
    if _model is None:
        import torch
        from transformers import AutoTokenizer, AutoModelForSeq2SeqLM
        _tokenizer = AutoTokenizer.from_pretrained(_MODEL_NAME)
        _model = AutoModelForSeq2SeqLM.from_pretrained(_MODEL_NAME)
        _device = "cuda" if torch.cuda.is_available() else "cpu"
        _model = _model.to(_device)
    return _model, _tokenizer


def _get_fields(collection: str) -> str:
    """Return comma-separated field list from the collection schema JSON."""
    path = SCHEMAS_DIR / f"{collection}.json"
    if not path.exists():
        return collection
    schema = json.loads(path.read_text(encoding="utf-8"))
    fields = []
    for name, info in schema.get("fields", {}).items():
        if info.get("type") == "object":
            for sub in info.get("fields", {}):
                fields.append(f"{name}.{sub}")
        else:
            fields.append(name)
    return ", ".join(fields)


def _extract_balanced(text: str, func: str) -> str | None:
    """Extract the content inside func(...), handling nested parentheses."""
    marker = f".{func}("
    idx = text.find(marker)
    if idx == -1:
        return None
    start = idx + len(marker)
    depth = 1
    i = start
    while i < len(text) and depth > 0:
        if text[i] == "(":
            depth += 1
        elif text[i] == ")":
            depth -= 1
        i += 1
    return text[start : i - 1].strip()


def _safe_parse(s: str) -> dict | list:
    """Parse JSON or Python-literal syntax into a Python dict/list."""
    try:
        return json.loads(s)
    except json.JSONDecodeError:
        pass
    try:
        result = ast.literal_eval(s)
        return json.loads(json.dumps(result))
    except Exception:
        pass
    raise ValueError(f"Cannot parse as JSON or Python literal: {s[:300]}")


def _parse_shell(output: str) -> dict | list:
    """Convert MongoDB shell syntax to PyMongo-compatible dict (find) or list (aggregate)."""
    output = output.strip()

    # aggregate([...])
    agg_args = _extract_balanced(output, "aggregate")
    if agg_args is not None:
        return _safe_parse(agg_args)

    # find({filter}) or find({filter}, {projection})
    find_args = _extract_balanced(output, "find")
    if find_args is None:
        raise ValueError(f"Unrecognized model output: {output[:300]}")

    # Split filter and optional projection at the top-level comma
    depth = 0
    split_at = None
    for i, ch in enumerate(find_args):
        if ch in "([{":
            depth += 1
        elif ch in ")]}":
            depth -= 1
        elif ch == "," and depth == 0:
            split_at = i
            break

    filter_str = find_args[:split_at].strip() if split_at else find_args.strip()
    projection_str = find_args[split_at + 1 :].strip() if split_at else None
    filter_doc = _safe_parse(filter_str)

    sort_args = _extract_balanced(output, "sort")
    limit_args = _extract_balanced(output, "limit")

    if not any([sort_args, limit_args, projection_str]):
        return filter_doc

    # Build aggregate pipeline from chained find().sort().limit()
    pipeline: list = [{"$match": filter_doc}] if filter_doc else []

    if sort_args:
        pairs = re.findall(r'\(\s*["\']([^"\']+)["\']\s*,\s*(-?\d+)\s*\)', sort_args)
        if pairs:
            pipeline.append({"$sort": {field: int(direction) for field, direction in pairs}})

    if limit_args:
        pipeline.append({"$limit": int(limit_args)})

    if projection_str:
        pipeline.append({"$project": _safe_parse(projection_str)})

    return pipeline


def _check_no_writes(query: dict | list) -> None:
    serialized = json.dumps(query)
    for op in _WRITE_OPS:
        if op in serialized:
            raise ValueError(f"Rejected: write operator '{op}' detected in generated query")


def generate(question: str, collection: str) -> dict | list:
    """Translate a natural language question into a PyMongo-compatible MQL query.

    Uses Chirayu/nl2mongo (CodeT5+ 220M) running locally.

    Args:
        question: User question in Spanish or English.
        collection: Target MongoDB collection name.

    Returns:
        dict  → caller should use collection.find(result)
        list  → caller should use collection.aggregate(result)

    Raises:
        ValueError: If output contains no valid MQL or a write operator.
    """
    import torch

    model, tokenizer = _load_model()
    fields = _get_fields(collection)
    prompt = f"mongo: {question} | {collection} : {fields}"

    inputs = tokenizer(prompt, return_tensors="pt").to(_device)
    with torch.no_grad():
        output_ids = model.generate(
            **inputs,
            num_beams=10,
            max_length=256,
            repetition_penalty=2.5,
            length_penalty=1.0,
            early_stopping=True,
        )

    raw = tokenizer.decode(output_ids[0], skip_special_tokens=True)
    query = _parse_shell(raw)
    _check_no_writes(query)
    return query
