"""
Día 11 — Prueba end-to-end de la memoria conversacional.

Simula una conversación con preguntas de seguimiento que sólo tienen sentido
con el contexto anterior ("¿y ordenadas por año?", "¿y solo las de después de
2010?"). Reproduce la misma lógica de sesión que app.py: mantiene un historial
de turnos y lo pasa a cada llamada.

Requiere Ollama (llama3.2) + conexión a Atlas (sample_mflix).

Uso:
    python tests/conversation_test.py
"""
import sys
import json
sys.path.insert(0, ".")
import warnings
warnings.filterwarnings("ignore")

import src.core as pipeline
from src.core import mql_generator

HISTORY_WINDOW = 5

# Una conversación con referencias anafóricas (cada turno depende del anterior).
CONVERSATION = [
    "Películas dirigidas por Christopher Nolan",
    "¿Y solo las que tienen un rating IMDb mayor de 8?",
    "Ordénalas por año de estreno",
    "¿Cuántas hay en total?",
]


def main():
    history: list[dict] = []
    previous_collection = None

    print(f"\n{'='*72}")
    print("  Día 11 — Memoria conversacional (preguntas de seguimiento)")
    print(f"{'='*72}\n")

    for i, question in enumerate(CONVERSATION, 1):
        print(f"[Turno {i}] Usuario: {question}")
        try:
            r = pipeline.query(question, history=history,
                               previous_collection=previous_collection)
            mql = r["mql"]
            n = len(r["results"])
            print(f"          Colección: {r['collection']}")
            print(f"          MQL      : {json.dumps(mql, ensure_ascii=False)[:120]}")
            print(f"          Resultados: {n} doc(s)")

            # Actualizar memoria igual que en app.py.
            previous_collection = r["collection"]
            history.extend(mql_generator.history_turns(question, mql))
            del history[: -2 * HISTORY_WINDOW]
        except Exception as e:
            print(f"          ERROR: {e}")
        print()

    print(f"{'='*72}")
    print(f"  Historial final: {len(history)} mensajes "
          f"({len(history)//2} intercambios recordados)")
    print(f"{'='*72}\n")
    print("  Revisa que el MQL de cada turno acumula las restricciones del anterior:")
    print("   · Turno 2 debe mantener el filtro de director Nolan + rating > 8")
    print("   · Turno 3 debe añadir $sort por año conservando los filtros")
    print("   · Turno 4 debe contar sobre el mismo conjunto filtrado\n")


if __name__ == "__main__":
    main()
