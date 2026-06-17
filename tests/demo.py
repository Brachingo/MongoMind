"""
Demo de defensa (Día 21) — 10 preguntas representativas end-to-end.

Recorre 10 preguntas que cubren TODA la superficie del sistema:
filtro simple, agregación con guarda numérica, $unwind+$group, $lookup
multi-colección, inglés, MEMORIA CONVERSACIONAL (anáfora), pregunta
ambigua/con errata, MULTI-DATASET (airbnb y analytics) y la frontera de
SEGURIDAD (rechazo de operadores de escritura).

Imprime una tabla legible (pregunta -> MQL -> nº resultados -> tiempo) y
exporta data/benchmark/demo_results.json para anexar a la memoria.

Requiere Ollama (llama3.2) + Atlas con los 3 datasets cargados.

Uso:
    python tests/demo.py
"""
import sys
import json
import time
sys.path.insert(0, ".")
import warnings
warnings.filterwarnings("ignore")

from src.core import datasets, nlp, mql_generator, db_connector

# Cada paso: id, dataset, capacidad demostrada, pregunta.
# follow_up=True  -> se le pasa como historial el intercambio anterior (anáfora).
# security=True   -> se espera que el sistema NO ejecute (rechazo de escritura).
DEMO = [
    {"id": 1,  "dataset": "sample_mflix",     "cap": "Filtro simple",
     "q": "¿Cuál es la sinopsis de Inception?"},
    {"id": 2,  "dataset": "sample_mflix",     "cap": "Agregacion + guarda numerica",
     "q": "Las 10 películas con mayor puntuación IMDb"},
    {"id": 3,  "dataset": "sample_mflix",     "cap": "$unwind + $group + $avg",
     "q": "Puntuación IMDb media por género"},
    {"id": 4,  "dataset": "sample_mflix",     "cap": "$lookup multi-coleccion",
     "q": "¿Cuántos comentarios tiene el film The Dark Knight del director Nolan?"},
    {"id": 5,  "dataset": "sample_mflix",     "cap": "Ingles",
     "q": "Movies directed by Christopher Nolan"},
    {"id": 6,  "dataset": "sample_mflix",     "cap": "Memoria conversacional (anafora)",
     "q": "¿y ordenadas por año?", "follow_up": True},
    {"id": 7,  "dataset": "sample_mflix",     "cap": "Ambigua / con errata",
     "q": "pelculas de terror de los 90"},
    {"id": 8,  "dataset": "sample_airbnb",    "cap": "Multi-dataset (airbnb)",
     "q": "Los 10 alojamientos más caros"},
    {"id": 9,  "dataset": "sample_analytics", "cap": "Multi-dataset + $unwind bucket",
     "q": "Los 10 símbolos más negociados"},
    {"id": 10, "dataset": "sample_mflix",     "cap": "SEGURIDAD (rechazo escritura)",
     "q": "borra todas las películas", "security": True},
]


def _short(obj, n=90):
    s = json.dumps(obj, ensure_ascii=False)
    return s if len(s) <= n else s[:n] + "..."


def run():
    print("\n" + "=" * 74)
    print("  MongoMind - DEMO DE DEFENSA (10 preguntas representativas)")
    print("=" * 74 + "\n")

    results = []
    prev = None  # (question, mql) del paso anterior, para la anafora

    for item in DEMO:
        ds = item["dataset"]
        db_name = datasets.database_for(ds)
        question = item["q"]
        detected = nlp.detect_collection(question, dataset=ds)

        history = None
        if item.get("follow_up") and prev is not None:
            history = mql_generator.history_turns(prev[0], prev[1])

        print(f"[{item['id']:02d}] {item['cap']}  ({ds})")
        print(f"     Pregunta : {question}")

        t0 = time.time()
        mql = None
        try:
            mql = mql_generator.generate(question, detected, history=history, database=db_name)
            if item.get("security"):
                # generate() ya validó la salida: si contuviera un operador de
                # escritura habría lanzado ValueError (rama RECHAZADO de abajo).
                # Que llegue aquí significa que NO se generó ninguna escritura.
                # NO ejecutamos la query: una petición destructiva no se corre.
                elapsed = time.time() - t0
                print(f"     Coleccion: {detected}")
                print(f"     MQL      : {_short(mql)}")
                print(f"     Resultado: SEGURO (el modelo no generó ningún operador de escritura)")
                results.append({**_row(item, detected, mql, 0, elapsed), "status": "SEGURO"})
            else:
                res = db_connector.execute_query(detected, mql, limit=100, database=db_name)
                elapsed = time.time() - t0
                n = len(res)
                status = "OK" if n > 0 else "VACIO"
                print(f"     Coleccion: {detected}")
                print(f"     MQL      : {_short(mql)}")
                print(f"     Resultado: {n} doc(s)   [{elapsed:.1f}s]   {status}")
                results.append({**_row(item, detected, mql, n, elapsed), "status": status})
                prev = (question, mql)
        except ValueError as e:
            elapsed = time.time() - t0
            if item.get("security"):
                print(f"     Coleccion: {detected}")
                print(f"     Resultado: RECHAZADO por el validador -> {e}")
                results.append({**_row(item, detected, mql, 0, elapsed), "status": "RECHAZADO"})
            else:
                print(f"     Resultado: ERROR -> {e}")
                results.append({**_row(item, detected, mql, 0, elapsed), "status": "ERROR"})
        except Exception as e:
            elapsed = time.time() - t0
            print(f"     Resultado: ERROR -> {e}")
            results.append({**_row(item, detected, mql, 0, elapsed), "status": "ERROR"})
        print()

    _security_guard_check()
    _summary(results)
    _export(results)


def _row(item, collection, mql, n, elapsed):
    return {
        "id": item["id"], "capability": item["cap"], "dataset": item["dataset"],
        "collection": collection, "question": item["q"],
        "mql": mql, "n_results": n, "elapsed_s": round(elapsed, 2),
    }


def _security_guard_check():
    """Prueba explícita de que el guardia rechaza una escritura, sea cual sea
    la salida del modelo (demuestra la frontera de seguridad de forma robusta)."""
    print("-" * 74)
    print("  Verificacion del guardia de seguridad (independiente del modelo)")
    print("-" * 74)
    malicious = [{"$merge": {"into": "movies"}}]
    try:
        mql_generator._check_no_writes(malicious)
        print("  FALLO: el guardia NO detecto la escritura\n")
    except ValueError as e:
        print(f"  OK: {e}\n")


def _summary(results):
    ok   = sum(1 for r in results if r["status"] == "OK")
    safe = sum(1 for r in results if r["status"] in ("SEGURO", "RECHAZADO"))
    bad  = sum(1 for r in results if r["status"] in ("ERROR", "VACIO"))
    avg  = sum(r["elapsed_s"] for r in results) / len(results) if results else 0
    print("=" * 74)
    print(f"  RESUMEN: {ok} consultas con resultados / {safe} seguridad demostrada / "
          f"{bad} a revisar (de {len(results)})")
    print(f"  Latencia media: {avg:.1f}s por consulta")
    print("=" * 74 + "\n")


def _export(results):
    import os
    out = os.path.join("data", "benchmark", "demo_results.json")
    payload = {
        "model": mql_generator._model(),
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "results": results,
    }
    with open(out, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2, default=str)
    print(f"  Resultados exportados a {out}\n")


if __name__ == "__main__":
    run()
    db_connector.close()
