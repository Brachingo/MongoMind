"""
Días 13-14 — Prueba con colecciones NO vistas (sin plantilla few-shot .txt).

comments, theaters y users no tienen src/prompts/templates/*.txt, así que el
pipeline debe:
  1. Inferir el esquema en tiempo real con schema_inferrer.
  2. Construir una plantilla dinámica desde ese esquema.
  3. Generar MQL ejecutable sin ninguna configuración manual previa.

Requiere Ollama (llama3.2) + conexión a Atlas (sample_mflix).

Uso:
    python tests/unseen_collections_test.py
"""
import sys
import json
import time
sys.path.insert(0, ".")
import warnings
warnings.filterwarnings("ignore")

import src.core as pipeline
from src.core import schema_inferrer, nlp

# (colección esperada, idioma, pregunta)
QUESTIONS = [
    ("comments", "ES", "¿Cuántos comentarios hay en total?"),
    ("comments", "EN", "Show me 5 comments"),
    ("comments", "ES", "Muéstrame los comentarios del usuario con nombre 'Mercedes Tyler'"),

    ("theaters", "ES", "¿Cuántos cines hay en total?"),
    ("theaters", "EN", "Show me 5 theaters"),
    ("theaters", "ES", "Cines ubicados en el estado de California (CA)"),

    ("users", "ES", "¿Cuántos usuarios hay registrados?"),
    ("users", "EN", "Show me 5 users"),
    ("users", "ES", "Busca el usuario con email que contenga 'test'"),
]

COLLECTIONS = ["comments", "theaters", "users"]


def check_schema_inference():
    print(f"\n{'='*72}")
    print("  PASO 1 — Inferencia dinámica de esquema (sin ficheros .json)")
    print(f"{'='*72}\n")
    for col in COLLECTIONS:
        try:
            schema = schema_inferrer.infer(col, n=50)
            fields = list(schema.get("fields", {}).keys())
            print(f"  [{col:9}] {len(fields)} campos inferidos: {', '.join(fields[:8])}"
                  + (" ..." if len(fields) > 8 else ""))
        except Exception as e:
            print(f"  [{col:9}] ERROR infiriendo esquema: {e}")
    print()


def run_pipeline():
    print(f"{'='*72}")
    print("  PASO 2 — Pipeline NL -> MQL -> resultados (colecciones no vistas)")
    print(f"{'='*72}\n")

    results = []
    for i, (expected_col, lang, question) in enumerate(QUESTIONS, 1):
        print(f"[{i:02d}/{len(QUESTIONS)}] [{lang}] {question}")
        detected = nlp.detect_collection(question)
        routing = "OK" if detected == expected_col else f"MISROUTED (->{detected})"
        t0 = time.time()
        try:
            r = pipeline.query(question)
            elapsed = time.time() - t0
            n = len(r["results"])
            status = "OK" if n > 0 else "EMPTY"
            print(f"        routing    : esperado={expected_col} detectado={detected}  [{routing}]")
            print(f"        mql        : {json.dumps(r['mql'], ensure_ascii=False)[:110]}")
            print(f"        results    : {n} doc(s)   [{elapsed:.1f}s]   {status}")
            results.append((expected_col, detected == expected_col, status, n, elapsed, None))
        except Exception as e:
            elapsed = time.time() - t0
            print(f"        ERROR      : {e}")
            results.append((expected_col, detected == expected_col, "ERROR", 0, elapsed, str(e)))
        print()

    # ── Resumen ──────────────────────────────────────────────────────────────
    ok       = sum(1 for r in results if r[2] == "OK")
    empty    = sum(1 for r in results if r[2] == "EMPTY")
    error    = sum(1 for r in results if r[2] == "ERROR")
    routed   = sum(1 for r in results if r[1])
    avg_t    = sum(r[4] for r in results) / len(results) if results else 0

    print(f"{'='*72}")
    print(f"  RESUMEN: {ok} con resultados / {empty} vacíos / {error} errores  "
          f"(de {len(results)})")
    print(f"  Routing correcto: {routed}/{len(results)}")
    print(f"  Tiempo medio: {avg_t:.1f}s por consulta")
    print(f"{'='*72}\n")


if __name__ == "__main__":
    check_schema_inference()
    run_pipeline()
