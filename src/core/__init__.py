from src.core import nlp, mql_generator, db_connector


def query(question: str, history: list[dict] | None = None,
          previous_collection: str | None = None) -> dict:
    """End-to-end pipeline: NL question -> MQL -> MongoDB results.

    Args:
        question:            The natural language question.
        history:             Optional prior {role, content} turns (conversational
                             memory) so follow-up questions resolve references.
        previous_collection: Collection used in the previous turn; reused when the
                             current question has no collection keyword.

    Returns:
        {
            "question":   str,
            "collection": str,
            "mql":        dict | list,
            "results":    list[dict],
        }
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
