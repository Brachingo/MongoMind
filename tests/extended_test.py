"""
Prueba extensa del pipeline completo con Ollama.
Cubre: filtros simples, comparaciones numéricas, top-N, agrupaciones,
       nombres propios, español, inglés, regex, $lookup, edge cases.

Uso:
    python tests/extended_test.py
    python tests/extended_test.py --stop-on-error
"""
import sys
import json
import time
import argparse
sys.path.insert(0, ".")

import src.core as pipeline

QUESTIONS = [
    # ── Filtros simples ──────────────────────────────────────────────────────
    ("filtro_simple",    "ES", "Películas del género Action"),
    ("filtro_simple",    "ES", "Películas de Drama estrenadas después de 2000"),
    ("filtro_simple",    "EN", "Find movies rated PG-13"),
    ("filtro_simple",    "EN", "Movies from the USA"),

    # ── Comparaciones numéricas ──────────────────────────────────────────────
    ("numerico",         "ES", "Películas con puntuación IMDb superior a 8.5"),
    ("numerico",         "ES", "Películas con más de 100 premios ganados"),
    ("numerico",         "EN", "Find movies with runtime greater than 180 minutes"),
    ("numerico",         "EN", "Movies released between 2010 and 2015"),

    # ── Top-N / sort ─────────────────────────────────────────────────────────
    ("top_n",            "ES", "Las 5 películas con mayor puntuación IMDb"),
    ("top_n",            "ES", "Las 10 películas más largas"),
    ("top_n",            "EN", "Top 5 movies with most award wins"),
    ("top_n",            "EN", "Find top 3 movies sorted by year descending"),

    # ── Nombres propios (directores / actores) ───────────────────────────────
    ("nombres_propios",  "ES", "Películas dirigidas por Martin Scorsese"),
    ("nombres_propios",  "ES", "Películas en las que actúa Tom Hanks"),
    ("nombres_propios",  "EN", "Movies directed by Christopher Nolan"),
    ("nombres_propios",  "EN", "Movies starring Leonardo DiCaprio"),

    # ── Agrupaciones ─────────────────────────────────────────────────────────
    ("agregacion",       "ES", "¿Cuántas películas hay de cada género?"),
    ("agregacion",       "ES", "Los 5 directores con más películas"),
    ("agregacion",       "EN", "Count movies grouped by year"),
    ("agregacion",       "EN", "Average IMDb rating per genre"),

    # ── Regex / búsqueda textual ─────────────────────────────────────────────
    ("regex",            "ES", "Películas cuyo título contiene la palabra 'love'"),
    ("regex",            "EN", "Movies with 'dark' in the title"),

    # ── Consultas combinadas ─────────────────────────────────────────────────
    ("combinado",        "ES", "Películas de Terror o Thriller con IMDb mayor de 7 estrenadas después de 2005"),
    ("combinado",        "EN", "Action movies with more than 50 award nominations sorted by imdb rating"),

    # ── $lookup (multi-colección) ────────────────────────────────────────────
    ("lookup",           "ES", "¿Cuántos comentarios tiene la película The Dark Knight?"),
]


def run(stop_on_error: bool = False):
    results = []
    total = len(QUESTIONS)

    print(f"\n{'─'*70}")
    print(f"  MongoMind — Prueba extensa  ({total} preguntas)")
    print(f"{'─'*70}\n")

    for i, (category, lang, question) in enumerate(QUESTIONS, 1):
        print(f"[{i:02d}/{total}] [{lang}] [{category}]")
        print(f"       {question}")
        t0 = time.time()
        try:
            r = pipeline.query(question)
            elapsed = time.time() - t0
            mql_preview = json.dumps(r["mql"])[:100]
            n = len(r["results"])
            status = "OK" if n > 0 else "EMPTY"
            print(f"       collection : {r['collection']}")
            print(f"       mql        : {mql_preview}")
            print(f"       results    : {n} doc(s)   [{elapsed:.1f}s]")
            results.append((category, lang, question, status, n, elapsed, None))
        except Exception as e:
            elapsed = time.time() - t0
            print(f"       ERROR      : {e}")
            results.append((category, lang, question, "ERROR", 0, elapsed, str(e)))
            if stop_on_error:
                break
        print()

    # ── Resumen ──────────────────────────────────────────────────────────────
    ok    = sum(1 for r in results if r[3] == "OK")
    empty = sum(1 for r in results if r[3] == "EMPTY")
    error = sum(1 for r in results if r[3] == "ERROR")
    avg_t = sum(r[5] for r in results) / len(results) if results else 0

    print(f"{'─'*70}")
    print(f"  RESUMEN: {ok} con resultados / {empty} vacíos / {error} errores  "
          f"(de {len(results)} ejecutadas)")
    print(f"  Tiempo medio por consulta: {avg_t:.1f}s")
    print(f"{'─'*70}\n")

    # Detalle de vacíos y errores
    issues = [(r[0], r[1], r[2], r[3], r[6]) for r in results if r[3] != "OK"]
    if issues:
        print("  Consultas sin resultados o con error:")
        for cat, lang, q, status, err in issues:
            tag = f"[{status}]"
            print(f"   {tag:<8} [{lang}] [{cat}] {q}")
            if err:
                print(f"            {err}")
        print()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--stop-on-error", action="store_true")
    args = parser.parse_args()
    run(stop_on_error=args.stop_on_error)
