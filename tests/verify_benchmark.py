"""
Días 15-16 — Verifica que TODAS las queries de referencia del benchmark son
ejecutables contra Atlas y devuelven resultados (no vacíos, sin errores).

No usa Ollama: solo ejecuta el expected_mql de cada par y reporta el recuento.
Sirve como control de calidad del benchmark antes de construir tests/eval.py.

Requiere conexión a Atlas (sample_mflix).

Uso:
    python tests/verify_benchmark.py
"""
import sys
import json
from pathlib import Path
sys.path.insert(0, ".")
import warnings
warnings.filterwarnings("ignore")

from src.core import db_connector

BENCHMARK_PATH = Path(__file__).parent.parent / "data" / "benchmark" / "movies_benchmark.json"


def main():
    data = json.loads(BENCHMARK_PATH.read_text(encoding="utf-8"))
    pairs = data["pairs"]
    collection = data["collection"]

    print(f"\n{'='*78}")
    print(f"  Verificación del benchmark — {len(pairs)} queries de referencia sobre '{collection}'")
    print(f"{'='*78}\n")

    errors, empties = [], []
    for p in pairs:
        pid, q, mql = p["id"], p["question"], p["expected_mql"]
        try:
            results = db_connector.execute_query(collection, mql)
            n = len(results)
            flag = "OK   " if n > 0 else "VACÍO"
            if n == 0:
                empties.append(p)
            print(f"  [{pid}] {flag} {n:>4} docs  | {q[:58]}")
        except Exception as e:
            errors.append((p, str(e)))
            print(f"  [{pid}] ERROR        | {q[:58]}")
            print(f"        -> {str(e)[:120]}")

    print(f"\n{'='*78}")
    ok = len(pairs) - len(errors) - len(empties)
    print(f"  RESULTADO: {ok} OK / {len(empties)} vacíos / {len(errors)} errores  (de {len(pairs)})")
    print(f"{'='*78}\n")

    if empties:
        print("  Queries que devuelven 0 resultados (revisar valores/títulos):")
        for p in empties:
            print(f"   [{p['id']}] {p['question']}")
            print(f"          {json.dumps(p['expected_mql'], ensure_ascii=False)[:110]}")
        print()
    if errors:
        print("  Queries con ERROR de ejecución (revisar sintaxis MQL):")
        for p, e in errors:
            print(f"   [{p['id']}] {p['question']}")
            print(f"          {e[:140]}")
        print()

    db_connector.close()
    return len(errors) == 0 and len(empties) == 0


if __name__ == "__main__":
    ok = main()
    sys.exit(0 if ok else 1)
