"""
Smoke test: 5 NL questions through the full pipeline
  nlp.detect_collection -> mql_generator.generate -> db_connector.execute_query

Run:  python tests/smoke_test.py
Note: first run downloads ~400MB from HuggingFace (cached afterwards).
"""
import sys, json
sys.path.insert(0, ".")
import src.core as pipeline
# cancelar warning
import warnings
warnings.filterwarnings("ignore")

QUESTIONS = [
    "which movies are of genre Action?",
    "find movies directed by Christopher Nolan",
    "which movies have imdb rating greater than 8?",
    "count movies grouped by genre",
    "find top 5 movies with highest imdb rating",
]


def main():
    print("Loading nl2mongo model (cached after first run)...\n")
    passed = 0

    for i, q in enumerate(QUESTIONS, 1):
        print(f"[{i}/5] {q}")
        try:
            r = pipeline.query(q)
            print(f"       collection : {r['collection']}")
            print(f"       mql        : {json.dumps(r['mql'])[:120]}")
            print(f"       results    : {len(r['results'])} doc(s)", end="")
            if r["results"]:
                first = {k: v for k, v in list(r["results"][0].items())[:2]}
                print(f"  (e.g. {first})", end="")
            print()
            passed += 1
        except Exception as e:
            print(f"       ERROR: {e}")
        print()

    print(f"{passed}/{len(QUESTIONS)} questions answered successfully.")


if __name__ == "__main__":
    main()
