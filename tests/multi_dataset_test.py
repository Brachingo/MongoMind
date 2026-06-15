"""
Multi-dataset — Prueba de integración del soporte multi-dataset.

Verifica que MongoMind generaliza a bases de datos distintas de sample_mflix
(sample_airbnb, sample_analytics) SIN configuración manual: enrutado por dataset,
inferencia dinámica de esquema y ejecución contra la base de datos correcta.

Requiere Ollama (llama3.2) + Atlas con sample_airbnb y sample_analytics cargados
(ver README → "Datasets adicionales" o scripts/load_sample_datasets.py).

Uso:
    python tests/multi_dataset_test.py
"""
import sys
import json
import time
sys.path.insert(0, ".")
import warnings
warnings.filterwarnings("ignore")

from src.core import datasets, nlp, mql_generator, db_connector, schema_inferrer

# (dataset, colección esperada, idioma, pregunta)
QUESTIONS = [
    ("sample_airbnb", "listingsAndReviews", "ES", "¿Cuántos alojamientos hay en total?"),
    ("sample_airbnb", "listingsAndReviews", "EN", "Show me 5 listings"),
    ("sample_airbnb", "listingsAndReviews", "ES", "Alojamientos en el país 'Spain'"),

    ("sample_analytics", "transactions", "ES", "¿Cuántas transacciones hay?"),
    ("sample_analytics", "customers",    "ES", "Muéstrame 5 clientes"),
    ("sample_analytics", "accounts",     "ES", "¿Cuántas cuentas hay en total?"),
]


def check_datasets_loaded():
    print(f"\n{'='*72}")
    print("  PASO 0 — Datasets cargados en Atlas")
    print(f"{'='*72}\n")
    ok = True
    for key in ("sample_airbnb", "sample_analytics"):
        cfg = datasets.get(key)
        for col in cfg["collections"]:
            try:
                n = len(db_connector.execute_query(col, {}, limit=1, database=cfg["database"]))
                state = "OK" if n > 0 else "VACÍA"
                if n == 0:
                    ok = False
                print(f"  [{key}/{col}] {state}")
            except Exception as e:
                ok = False
                print(f"  [{key}/{col}] ERROR: {e}")
    if not ok:
        print("\n  AVISO: faltan datos. Cárgalos con scripts/load_sample_datasets.py")
    print()
    return ok


def check_schema_inference():
    print(f"{'='*72}")
    print("  PASO 1 — Inferencia dinámica de esquema (sin ficheros .json)")
    print(f"{'='*72}\n")
    for key in ("sample_airbnb", "sample_analytics"):
        cfg = datasets.get(key)
        for col in cfg["collections"]:
            try:
                schema = schema_inferrer.infer(col, n=50, database=cfg["database"])
                fields = list(schema.get("fields", {}).keys())
                print(f"  [{key}/{col}] {len(fields)} campos: {', '.join(fields[:8])}"
                      + (" ..." if len(fields) > 8 else ""))
            except Exception as e:
                print(f"  [{key}/{col}] ERROR infiriendo esquema: {e}")
    print()


def run_pipeline():
    print(f"{'='*72}")
    print("  PASO 2 — Pipeline NL -> MQL -> resultados (datasets no mflix)")
    print(f"{'='*72}\n")

    results = []
    for i, (ds, expected_col, lang, question) in enumerate(QUESTIONS, 1):
        db_name = datasets.database_for(ds)
        detected = nlp.detect_collection(question, dataset=ds)
        routing = "OK" if detected == expected_col else f"MISROUTED (->{detected})"
        print(f"[{i:02d}/{len(QUESTIONS)}] [{ds}] [{lang}] {question}")
        t0 = time.time()
        try:
            mql = mql_generator.generate(question, detected, database=db_name)
            res = db_connector.execute_query(detected, mql, limit=100, database=db_name)
            elapsed = time.time() - t0
            n = len(res)
            status = "OK" if n > 0 else "EMPTY"
            print(f"        routing : esperado={expected_col} detectado={detected}  [{routing}]")
            print(f"        mql     : {json.dumps(mql, ensure_ascii=False)[:110]}")
            print(f"        results : {n} doc(s)   [{elapsed:.1f}s]   {status}")
            results.append((detected == expected_col, status, elapsed))
        except Exception as e:
            elapsed = time.time() - t0
            print(f"        ERROR   : {e}")
            results.append((detected == expected_col, "ERROR", elapsed))
        print()

    ok     = sum(1 for r in results if r[1] == "OK")
    empty  = sum(1 for r in results if r[1] == "EMPTY")
    error  = sum(1 for r in results if r[1] == "ERROR")
    routed = sum(1 for r in results if r[0])
    avg_t  = sum(r[2] for r in results) / len(results) if results else 0

    print(f"{'='*72}")
    print(f"  RESUMEN: {ok} con resultados / {empty} vacíos / {error} errores "
          f"(de {len(results)})")
    print(f"  Routing correcto: {routed}/{len(results)}")
    print(f"  Tiempo medio: {avg_t:.1f}s por consulta")
    print(f"{'='*72}\n")


if __name__ == "__main__":
    if check_datasets_loaded():
        check_schema_inference()
        run_pipeline()
    db_connector.close()
