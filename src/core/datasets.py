"""
Registro explícito de los datasets sobre los que MongoMind puede operar.

Mantener un registro CERRADO (en lugar de "cualquier base de datos arbitraria")
nos da tres cosas que importan para un asistente fiable:
  - enrutado de colección por keywords adaptado a cada dataset,
  - una lista controlada para poblar el selector de la web / validar la API,
  - una frontera de seguridad: solo se consultan bases de datos conocidas.

Para añadir un dataset basta con una entrada aquí: el nombre real de la base de
datos en Atlas, sus colecciones con las keywords de enrutado, y la colección por
defecto (la que se usa cuando una pregunta de seguimiento no tiene keywords).

Las keywords de sample_mflix son las que vivían antes en nlp.py (se conservan
idénticas para no alterar el comportamiento ya probado).
"""

DATASETS: dict[str, dict] = {
    "sample_mflix": {
        "label": "Películas · sample_mflix",
        "database": "sample_mflix",
        "default_collection": "movies",
        "collections": {
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
        },
    },
    "sample_airbnb": {
        "label": "Airbnb · sample_airbnb",
        "database": "sample_airbnb",
        "default_collection": "listingsAndReviews",
        "collections": {
            "listingsAndReviews": [
                "airbnb", "alojamiento", "alojamientos", "anuncio", "anuncios",
                "listing", "listings", "habitacion", "habitaciones",
                "apartamento", "apartamentos", "piso", "casa", "propiedad",
                "host", "anfitrion", "huesped", "huespedes", "guest",
                "review", "reviews", "resena", "resenas",
                "precio", "price", "noche", "noches", "night",
                "cama", "camas", "bed", "beds", "bedroom", "bedrooms",
                "baño", "baños", "bathroom", "bathrooms",
                "alquiler", "rent", "room", "rooms", "accommodation", "amenities",
            ],
        },
    },
    "sample_analytics": {
        "label": "Banca · sample_analytics",
        "database": "sample_analytics",
        "default_collection": "transactions",
        "collections": {
            "accounts": [
                "cuenta", "cuentas", "account", "accounts",
                "limite", "limit", "producto", "productos", "product", "products",
            ],
            "customers": [
                "cliente", "clientes", "customer", "customers",
                "email", "nombre", "name", "tier", "beneficio", "beneficios",
                "benefit", "benefits", "usuario", "usuarios",
            ],
            "transactions": [
                "transaccion", "transacciones", "transaction", "transactions",
                "compra", "compras", "venta", "ventas", "buy", "sell",
                "symbol", "simbolo", "accion", "acciones", "stock", "stocks",
                "importe", "amount", "precio", "price", "operacion", "operaciones",
            ],
        },
    },
}

DEFAULT_DATASET = "sample_mflix"


def dataset_keys() -> list[str]:
    """Claves de los datasets disponibles, en orden de definición."""
    return list(DATASETS.keys())


def is_valid(dataset_key: str | None) -> bool:
    return dataset_key in DATASETS


def resolve(dataset_key: str | None) -> str:
    """Devuelve un dataset válido: el dado si existe, si no el por defecto."""
    return dataset_key if is_valid(dataset_key) else DEFAULT_DATASET


def get(dataset_key: str | None) -> dict:
    return DATASETS[resolve(dataset_key)]


def database_for(dataset_key: str | None) -> str:
    """Nombre real de la base de datos en Atlas para este dataset."""
    return get(dataset_key)["database"]


def options() -> list[dict]:
    """Lista [{key, label}] para poblar el selector de la web."""
    return [{"key": k, "label": v["label"]} for k, v in DATASETS.items()]


def detect_collection(dataset_key: str | None, question: str,
                      previous: str | None = None) -> str:
    """Colección más probable para *question* DENTRO de *dataset_key*.

    Puntúa la pregunta contra las keywords de cada colección del dataset. Si
    ninguna keyword coincide (típico en preguntas de seguimiento), reutiliza
    *previous* cuando pertenece a este dataset; si no, usa la colección por
    defecto del dataset.
    """
    cfg = get(dataset_key)
    collections = cfg["collections"]
    q = question.lower()
    scores = {col: sum(1 for kw in kws if kw in q) for col, kws in collections.items()}
    best = max(scores, key=scores.get)
    if scores[best] > 0:
        return best
    if previous in collections:
        return previous
    return cfg["default_collection"]
