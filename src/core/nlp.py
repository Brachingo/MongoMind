_KEYWORDS: dict[str, list[str]] = {
    "movies": [
        "movie", "movies", "film", "films", "pelicula", "peliculas",
        "director", "actor", "actriz", "cast", "genre", "genero",
        "estreno", "imdb", "rating", "duracion", "runtime",
        "titulo", "title", "award", "oscar", "premio", "watch",
    ],
    "comments": [
        "comment", "comments", "comentario", "comentarios",
        "review", "opinion", "resena", "texto", "message",
    ],
    "theaters": [
        "theater", "theaters", "teatro", "cine", "sala",
        "venue", "location", "cinema",
    ],
    "users": [
        "user", "users", "usuario", "usuarios", "email", "cuenta",
    ],
}

_DEFAULT = "movies"


def detect_collection(question: str, previous: str | None = None) -> str:
    """Return the most likely MongoDB collection for the given question.

    When no keyword matches (e.g. a follow-up question like "¿y solo las de
    2010?"), reuse *previous* if provided so the conversation stays on the same
    collection. Falls back to the default collection ('movies') otherwise.
    """
    q = question.lower()
    scores = {col: sum(1 for kw in kws if kw in q) for col, kws in _KEYWORDS.items()}
    best = max(scores, key=scores.get)
    if scores[best] > 0:
        return best
    return previous or _DEFAULT
