from src.core import nlp, mql_generator, db_connector


def query(question: str) -> dict:
    """End-to-end pipeline: NL question -> MQL -> MongoDB results.

    Returns:
        {
            "question":   str,
            "collection": str,
            "mql":        dict | list,
            "results":    list[dict],
        }
    """
    collection = nlp.detect_collection(question)
    mql = mql_generator.generate(question, collection)
    results = db_connector.execute_query(collection, mql)
    return {
        "question": question,
        "collection": collection,
        "mql": mql,
        "results": results,
    }
