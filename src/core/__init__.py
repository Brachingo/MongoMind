from src.core import nlp, mql_generator, db_connector


def query(question: str, history: list[dict] | None = None,
          previous_collection: str | None = None) -> dict:
    """Pipeline completo: pregunta NL -> MQL -> resultados de MongoDB.

    *history* es la memoria conversacional (turnos previos) para resolver
    referencias en los follow-ups; *previous_collection* es la colección del
    turno anterior, que se reutiliza cuando la pregunta actual no trae keyword.

    Devuelve un dict con question, collection, mql y results.
    """
    collection = nlp.detect_collection(question, previous=previous_collection)
    mql = mql_generator.generate(question, collection, history=history)
    results = db_connector.execute_query(collection, mql)
    return {
        "question": question,
        "collection": collection,
        "mql": mql,
        "results": results,
    }
