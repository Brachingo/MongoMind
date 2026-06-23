"""
Evaluación del modelo especializado nl2mongo (Chirayu/nl2mongo, CodeT5+ 220M)
sobre el MISMO benchmark de movies, como punto de comparación frente a los LLM
locales de Ollama.

nl2mongo NO es compatible con Ollama: es un seq2seq (transformers/PyTorch) que
recibe `mongo: <pregunta> | <colección> : <campos>` y emite una cadena MQL del
estilo `db.movies.find({...}, {...}).sort([("year", -1)]).limit(5)` o
`db.movies.aggregate([...])`. Este script:
  1. genera esa cadena con el modelo,
  2. la parsea a un filtro/pipeline ejecutable por db_connector,
  3. ejecuta generada y referencia contra Atlas y compara FUNCIONALMENTE,
     reutilizando exactamente la misma lógica que tests/eval.py.

El resultado se exporta como results_nl2mongo_{split}_{ts}.json, con el mismo
formato que el resto de modelos, para que entre en las tablas/figuras.

Requiere: transformers, torch, Atlas. NO requiere Ollama.

Uso:
    python tests/eval_nl2mongo.py --split test
    python tests/eval_nl2mongo.py --split dev
"""
import argparse
import importlib.util
import json
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, ".")

BENCHMARK_PATH = Path(__file__).parent.parent / "data" / "benchmark" / "movies_benchmark.json"

# Reutilizamos los helpers de comparación/agregado de tests/eval.py sin duplicarlos.
_spec = importlib.util.spec_from_file_location("bencheval", Path(__file__).parent / "eval.py")
bencheval = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(bencheval)

# Campos de nivel superior de movies (pista de esquema que espera el modelo).
MOVIES_FIELDS = ("_id, title, year, genres, directors, cast, runtime, rated, imdb, "
                 "languages, countries, awards, tomatoes, type, plot, released, "
                 "writers, num_mflix_comments, metacritic")

MODEL_NAME = "Chirayu/nl2mongo"


# --------------------------------------------------------------------------- #
# Modelo
# --------------------------------------------------------------------------- #
def load_model():
    from transformers import AutoModelForSeq2SeqLM, AutoTokenizer
    import torch
    tok = AutoTokenizer.from_pretrained(MODEL_NAME)
    model = AutoModelForSeq2SeqLM.from_pretrained(MODEL_NAME)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = model.to(device)
    return tok, model, device


def generate_raw(tok, model, device, question: str, collection: str = "movies") -> str:
    text = f"mongo: {question} | {collection} : {MOVIES_FIELDS}"
    input_ids = tok.encode(text, return_tensors="pt", add_special_tokens=True).to(device)
    out = model.generate(input_ids=input_ids, num_beams=10, max_length=128)
    return tok.decode(out[0], skip_special_tokens=True)


# --------------------------------------------------------------------------- #
# Parser de la cadena MQL emitida por nl2mongo
# --------------------------------------------------------------------------- #
def _balanced(s: str, start: int, op: str, cl: str) -> tuple[str, int]:
    """Devuelve (substring balanceado desde s[start]==op, índice tras cl)."""
    depth, i = 0, start
    while i < len(s):
        if s[i] == op:
            depth += 1
        elif s[i] == cl:
            depth -= 1
            if depth == 0:
                return s[start:i + 1], i + 1
        i += 1
    raise ValueError("paréntesis/corchete sin cerrar")


def _split_top_objects(s: str) -> list[str]:
    """Separa objetos {...} a profundidad 0 (los argumentos de find)."""
    objs, i = [], 0
    while i < len(s):
        if s[i] == "{":
            obj, j = _balanced(s, i, "{", "}")
            objs.append(obj)
            i = j
        else:
            i += 1
    return objs


def _parse_sort(chain: str) -> dict | None:
    m = re.search(r"\.sort\(\s*(\[.*?\]|\{.*?\})\s*\)", chain)
    if not m:
        return None
    body = m.group(1)
    if body.startswith("{"):
        try:
            return json.loads(body)
        except json.JSONDecodeError:
            return None
    # forma lista de tuplas: [("year", -1), ('rating', 1)]
    pairs = re.findall(r"\(\s*['\"]([\w.$]+)['\"]\s*,\s*(-?\d+)\s*\)", body)
    return {f: int(v) for f, v in pairs} or None


def _parse_limit(chain: str) -> int | None:
    m = re.search(r"\.limit\(\s*(\d+)\s*\)", chain)
    return int(m.group(1)) if m else None


def parse_nl2mongo(raw: str) -> dict | list:
    """Convierte la cadena del modelo en un dict (find) o lista (pipeline)."""
    s = raw.strip().strip("`").strip()
    mm = re.search(r"db\.\w+\.(find|aggregate|count|countDocuments)\(", s)
    if not mm:
        raise ValueError(f"salida no reconocida: {raw[:120]}")
    method = mm.group(1)
    args_start = mm.end() - 1  # posición del '('

    if method == "aggregate":
        # primer '[' tras aggregate(
        lb = s.index("[", args_start)
        arr, _ = _balanced(s, lb, "[", "]")
        return json.loads(arr)

    # find / count: extraer args dentro de (...)
    args_str, after = _balanced(s, args_start, "(", ")")
    inner = args_str[1:-1].strip()
    objs = _split_top_objects(inner) if inner else []
    filt = json.loads(objs[0]) if objs else {}
    proj = json.loads(objs[1]) if len(objs) > 1 else None
    chain = s[after:]  # .sort(...).limit(...)

    if method in ("count", "countDocuments"):
        return [{"$match": filt}, {"$count": "total"}]

    sort = _parse_sort(chain)
    limit = _parse_limit(chain)

    if not sort and not limit:
        return filt  # find simple → execute_query aplica {_id:0}
    # con sort/limit construimos pipeline equivalente
    pipeline = [{"$match": filt}]
    if sort:
        pipeline.append({"$sort": sort})
    if limit:
        pipeline.append({"$limit": limit})
    if proj:
        pipeline.append({"$project": proj})
    return pipeline


# --------------------------------------------------------------------------- #
# Bucle de evaluación (espejo de tests/eval.py)
# --------------------------------------------------------------------------- #
def run_eval(split: str = "test", limit: int | None = None) -> dict:
    from src.core import db_connector

    data = json.loads(BENCHMARK_PATH.read_text(encoding="utf-8"))
    collection = data["collection"]
    pairs = [p for p in data["pairs"] if split == "all" or p["split"] == split]
    if limit:
        pairs = pairs[:limit]

    print(f"\n{'='*80}\n  Evaluación — modelo=nl2mongo  split={split}  pares={len(pairs)}\n{'='*80}\n")
    print("  Cargando Chirayu/nl2mongo (transformers, CPU)…")
    tok, model, device = load_model()

    items = []
    for p in pairs:
        pid, q, rt = p["id"], p["question"], p["result_type"]
        expected_mql = p["expected_mql"]
        rec = {"id": pid, "complexity": p["complexity"], "result_type": rt,
               "question": q, "expected_mql": expected_mql,
               "generated_mql": None, "raw_output": None, "functional": False,
               "partial": 0.0, "exact": False, "error": None, "latency_s": None,
               "n_expected": None, "n_actual": None}
        try:
            t0 = time.time()
            raw = generate_raw(tok, model, device, q, collection)
            rec["latency_s"] = round(time.time() - t0, 2)
            rec["raw_output"] = raw
            generated = parse_nl2mongo(raw)
            rec["generated_mql"] = generated

            expected_res = db_connector.execute_query(collection, expected_mql, limit=bencheval.EVAL_LIMIT)
            actual_res = db_connector.execute_query(collection, generated, limit=bencheval.EVAL_LIMIT)
            rec["n_expected"], rec["n_actual"] = len(expected_res), len(actual_res)

            ok, partial = bencheval.functional_match(rt, expected_res, actual_res)
            rec["functional"], rec["partial"] = ok, round(partial, 3)
            rec["exact"] = bencheval.exact_match(expected_mql, generated)
        except Exception as e:
            rec["error"] = f"{type(e).__name__}: {str(e)[:160]}"

        flag = "OK  " if rec["functional"] else ("ERR " if rec["error"] else "MISS")
        lat = f"{rec['latency_s']}s" if rec["latency_s"] is not None else "-"
        print(f"  [{pid}] {flag} func={rec['functional']!s:5} part={rec['partial']:.2f} "
              f"{lat:>6} | {q[:42]}")
        items.append(rec)

    metrics = bencheval._aggregate(items)
    bencheval._print_summary(metrics)
    db_connector.close()
    return {
        "model": "nl2mongo", "split": split, "collection": collection,
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "n_pairs": len(items), "eval_limit": bencheval.EVAL_LIMIT,
        "metrics": metrics["overall"], "by_complexity": metrics["by_complexity"],
        "items": items,
    }


def main():
    parser = argparse.ArgumentParser(description="Evalúa nl2mongo sobre el benchmark NL->MQL")
    parser.add_argument("--split", choices=["dev", "test", "all"], default="test")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--no-save", action="store_true")
    args = parser.parse_args()

    report = run_eval(split=args.split, limit=args.limit)
    if not args.no_save:
        path = bencheval._export(report)
        print(f"  Resultados guardados en {path}")


if __name__ == "__main__":
    main()
