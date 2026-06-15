"""
Día 17 — Script de evaluación del benchmark NL->MQL.

Para cada par (pregunta, MQL de referencia) del benchmark:
  1. Genera la MQL con el modelo (Ollama) a partir de la pregunta.
  2. Ejecuta la query generada y la de referencia contra Atlas.
  3. Compara los resultados FUNCIONALMENTE (no por string): según el result_type
     del par (count / scalar / documents / groups) decide si la respuesta es
     equivalente, tolerando proyecciones, nombres de campo y orden distintos.

Métricas:
  * Corrección funcional (%)        — resultados equivalentes
  * Exact match (%)                 — MQL idéntica tras normalizar JSON
  * Tasa de error de ejecución (%)  — generación inválida o fallo al ejecutar
  * Latencia media de generación (s)
  * Corrección parcial media        — Jaccard de resultados (documents/groups)
Desglose por nivel de complejidad.

Requiere Ollama + Atlas. NO es un test de pytest (la lógica de comparación sí se
testea en tests/test_eval.py). Exporta data/benchmark/results_{model}_{split}_{ts}.json.

Uso:
    python tests/eval.py                      # split test (por defecto)
    python tests/eval.py --split dev
    python tests/eval.py --model mistral --split test
    python tests/eval.py --limit 5            # solo los primeros 5 (prueba rápida)
"""
import sys
import os
import json
import time
import argparse
from datetime import datetime
from pathlib import Path
sys.path.insert(0, ".")

BENCHMARK_PATH = Path(__file__).parent.parent / "data" / "benchmark" / "movies_benchmark.json"
RESULTS_DIR = Path(__file__).parent.parent / "data" / "benchmark"

# Higher than the app's default cap so most result sets are not truncated,
# which would make set comparison unreliable. Both queries use the same limit.
EVAL_LIMIT = 1000
_FLOAT_REL_TOL = 1e-3


# ── Helpers de extracción ────────────────────────────────────────────────────

def _is_number(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def scalar_value(result):
    """Si result es un único doc con exactamente un valor numérico (sin _id), lo devuelve."""
    if isinstance(result, list) and len(result) == 1 and isinstance(result[0], dict):
        nums = [v for k, v in result[0].items() if k != "_id" and _is_number(v)]
        if len(nums) == 1:
            return nums[0]
    return None


def count_value(result):
    """Número de un resultado de conteo: el escalar de un $count, o el nº de docs."""
    sv = scalar_value(result)
    if sv is not None:
        return sv
    if isinstance(result, list):
        return len(result)
    return None


def titles(result):
    """Conjunto de títulos presentes en los documentos (None si no es lista)."""
    if not isinstance(result, list):
        return None
    return {doc["title"] for doc in result if isinstance(doc, dict) and "title" in doc}


def doc_set(result):
    """Conjunto de documentos canónicos (sin _id) como JSON ordenado."""
    out = set()
    for doc in result:
        if isinstance(doc, dict):
            d = {k: v for k, v in doc.items() if k != "_id"}
            out.add(json.dumps(d, sort_keys=True, default=str))
    return out


def groups_map(result):
    """Mapa str(_id) -> métrica principal (primer valor numérico no _id) de cada grupo."""
    if not isinstance(result, list):
        return None
    m = {}
    for doc in result:
        if not isinstance(doc, dict) or "_id" not in doc:
            return None
        key = json.dumps(doc["_id"], sort_keys=True, default=str)
        nums = [v for k, v in doc.items() if k != "_id" and _is_number(v)]
        m[key] = nums[0] if nums else None
    return m


def num_close(a, b) -> bool:
    if a is None or b is None:
        return False
    if not (_is_number(a) and _is_number(b)):
        return a == b
    if isinstance(a, int) and isinstance(b, int):
        return a == b
    denom = max(abs(a), abs(b), 1e-9)
    return abs(a - b) / denom <= _FLOAT_REL_TOL


def _jaccard(a: set, b: set) -> float:
    if not a and not b:
        return 1.0
    union = a | b
    return len(a & b) / len(union) if union else 1.0


# ── Comparación funcional ────────────────────────────────────────────────────

def functional_match(result_type: str, expected, actual) -> tuple[bool, float]:
    """Devuelve (match_exacto_funcional, correccion_parcial[0..1])."""
    if result_type == "count":
        e, a = count_value(expected), count_value(actual)
        ok = e is not None and a is not None and e == a
        return ok, (1.0 if ok else 0.0)

    if result_type == "scalar":
        e, a = scalar_value(expected), scalar_value(actual)
        ok = num_close(e, a)
        return ok, (1.0 if ok else 0.0)

    if result_type == "groups":
        ge, ga = groups_map(expected), groups_map(actual)
        if ge is None or ga is None:
            return False, 0.0
        keys_e, keys_a = set(ge), set(ga)
        partial = _jaccard(keys_e, keys_a)
        ok = keys_e == keys_a and all(num_close(ge[k], ga.get(k)) for k in ge)
        return ok, partial

    # documents (por defecto)
    te, ta = titles(expected), titles(actual)
    if te:  # la referencia tiene títulos -> comparar por título (robusto a proyección)
        ta = ta or set()
        return te == ta, _jaccard(te, ta)
    de, da = doc_set(expected), doc_set(actual)
    return de == da, _jaccard(de, da)


def normalize_mql(mql) -> str:
    """Forma canónica para exact match (orden de claves normalizado; orden de pipeline preservado)."""
    return json.dumps(mql, sort_keys=True, ensure_ascii=False, default=str)


def exact_match(expected_mql, generated_mql) -> bool:
    return normalize_mql(expected_mql) == normalize_mql(generated_mql)


# ── Bucle de evaluación ──────────────────────────────────────────────────────

def run_eval(split: str = "test", limit: int | None = None) -> dict:
    from src.core import db_connector, mql_generator

    data = json.loads(BENCHMARK_PATH.read_text(encoding="utf-8"))
    collection = data["collection"]
    pairs = [p for p in data["pairs"] if split == "all" or p["split"] == split]
    if limit:
        pairs = pairs[:limit]

    model = os.getenv("OLLAMA_MODEL", "llama3.2")
    print(f"\n{'='*80}")
    print(f"  Evaluación — modelo={model}  split={split}  pares={len(pairs)}")
    if split == "test":
        print("  AVISO: split de TEST -> úsalo solo para reportar, NO para ajustar prompts.")
    print(f"{'='*80}\n")

    items = []
    for p in pairs:
        pid, q, rt = p["id"], p["question"], p["result_type"]
        expected_mql = p["expected_mql"]
        rec = {"id": pid, "complexity": p["complexity"], "result_type": rt,
               "question": q, "expected_mql": expected_mql,
               "generated_mql": None, "functional": False, "partial": 0.0,
               "exact": False, "error": None, "latency_s": None,
               "n_expected": None, "n_actual": None}
        try:
            t0 = time.time()
            generated = mql_generator.generate(q, collection)
            rec["latency_s"] = round(time.time() - t0, 2)
            rec["generated_mql"] = generated

            expected_res = db_connector.execute_query(collection, expected_mql, limit=EVAL_LIMIT)
            actual_res = db_connector.execute_query(collection, generated, limit=EVAL_LIMIT)
            rec["n_expected"], rec["n_actual"] = len(expected_res), len(actual_res)

            ok, partial = functional_match(rt, expected_res, actual_res)
            rec["functional"], rec["partial"] = ok, round(partial, 3)
            rec["exact"] = exact_match(expected_mql, generated)
        except Exception as e:
            rec["error"] = f"{type(e).__name__}: {str(e)[:160]}"

        flag = "OK  " if rec["functional"] else ("ERR " if rec["error"] else "MISS")
        lat = f"{rec['latency_s']}s" if rec["latency_s"] is not None else "-"
        print(f"  [{pid}] {flag} func={rec['functional']!s:5} part={rec['partial']:.2f} "
              f"exact={rec['exact']!s:5} {lat:>6} | {q[:46]}")
        items.append(rec)

    metrics = _aggregate(items)
    _print_summary(metrics)

    db_connector.close()
    return {
        "model": model, "split": split, "collection": collection,
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "n_pairs": len(items), "eval_limit": EVAL_LIMIT,
        "metrics": metrics["overall"], "by_complexity": metrics["by_complexity"],
        "items": items,
    }


def _aggregate(items: list[dict]) -> dict:
    n = len(items) or 1
    func = sum(1 for it in items if it["functional"])
    exact = sum(1 for it in items if it["exact"])
    errors = sum(1 for it in items if it["error"])
    lats = [it["latency_s"] for it in items if it["latency_s"] is not None]
    partials = [it["partial"] for it in items]

    overall = {
        "functional_accuracy": round(func / n, 3),
        "exact_match": round(exact / n, 3),
        "execution_error_rate": round(errors / n, 3),
        "partial_correctness": round(sum(partials) / n, 3),
        "avg_latency_s": round(sum(lats) / len(lats), 2) if lats else None,
        "n": len(items),
    }
    by_complexity = {}
    for level in ("simple", "media", "alta", "ambiguous"):
        group = [it for it in items if it["complexity"] == level]
        if group:
            by_complexity[level] = {
                "n": len(group),
                "functional_accuracy": round(sum(1 for it in group if it["functional"]) / len(group), 3),
            }
    return {"overall": overall, "by_complexity": by_complexity}


def _print_summary(metrics: dict):
    o = metrics["overall"]
    print(f"\n{'='*80}")
    print(f"  RESUMEN  (n={o['n']})")
    print(f"    Corrección funcional : {o['functional_accuracy']*100:.1f}%")
    print(f"    Exact match          : {o['exact_match']*100:.1f}%")
    print(f"    Corrección parcial   : {o['partial_correctness']*100:.1f}%")
    print(f"    Tasa de error        : {o['execution_error_rate']*100:.1f}%")
    print(f"    Latencia media       : {o['avg_latency_s']}s")
    print(f"  Por complejidad:")
    for level, m in metrics["by_complexity"].items():
        print(f"    {level:10}: {m['functional_accuracy']*100:5.1f}%  (n={m['n']})")
    print(f"{'='*80}\n")


def _export(report: dict) -> Path:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    safe_model = report["model"].replace(":", "_").replace("/", "_")
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    path = RESULTS_DIR / f"results_{safe_model}_{report['split']}_{ts}.json"
    path.write_text(json.dumps(report, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    return path


def main():
    parser = argparse.ArgumentParser(description="Evalúa el benchmark NL->MQL")
    parser.add_argument("--split", choices=["dev", "test", "all"], default="test",
                        help="Split a evaluar (por defecto: test)")
    parser.add_argument("--model", help="Modelo Ollama (sobrescribe OLLAMA_MODEL)")
    parser.add_argument("--limit", type=int, help="Evaluar solo los primeros N pares")
    parser.add_argument("--no-save", action="store_true", help="No exportar el JSON de resultados")
    args = parser.parse_args()

    if args.model:
        os.environ["OLLAMA_MODEL"] = args.model

    report = run_eval(split=args.split, limit=args.limit)

    if not args.no_save:
        path = _export(report)
        print(f"Resultados exportados a: {path}")


if __name__ == "__main__":
    main()
