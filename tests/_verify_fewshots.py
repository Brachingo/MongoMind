"""Verify all few-shot MQL examples in the movies template actually execute."""
import sys
sys.path.insert(0, ".")
from src.core.db_connector import execute_query, close

cases = [
    ("Filtro simple por título",         "movies", {"title": "Inception"}),
    ("Género + año",                      "movies", {"genres": "Horror", "year": {"$gt": 2010}}),
    ("IMDb > 8.5 ordenado",              "movies", [
        {"$match": {"imdb.rating": {"$gt": 8.5}}},
        {"$sort": {"imdb.rating": -1}},
        {"$project": {"title": 1, "imdb.rating": 1, "year": 1, "_id": 0}},
    ]),
    ("Top 10 más largas",               "movies", [
        {"$match": {"runtime": {"$exists": True, "$type": "int"}}},
        {"$sort": {"runtime": -1}},
        {"$limit": 10},
        {"$project": {"title": 1, "runtime": 1, "_id": 0}},
    ]),
    ("Contar por género",               "movies", [
        {"$unwind": "$genres"},
        {"$group": {"_id": "$genres", "total": {"$sum": 1}}},
        {"$sort": {"total": -1}},
    ]),
    ("$in directores",                  "movies", {"directors": {"$in": ["Christopher Nolan", "Steven Spielberg"]}}),
    ("$regex título",                   "movies", {"title": {"$regex": "war", "$options": "i"}}),
    ("Media runtime Action",            "movies", [
        {"$match": {"genres": "Action", "runtime": {"$exists": True, "$type": "int"}}},
        {"$group": {"_id": None, "duracion_media_minutos": {"$avg": "$runtime"}}},
    ]),
    ("Cast + awards.wins",              "movies", {"cast": "Tom Hanks", "awards.wins": {"$gt": 5}}),
    ("Top 5 directores",               "movies", [
        {"$unwind": "$directors"},
        {"$group": {"_id": "$directors", "num_peliculas": {"$sum": 1}}},
        {"$sort": {"num_peliculas": -1}},
        {"$limit": 5},
    ]),
    ("Filtro combinado Drama/Thriller", "movies", [
        {"$match": {"genres": {"$in": ["Drama", "Thriller"]}, "imdb.rating": {"$gte": 7, "$lte": 9}, "year": {"$gte": 2000, "$lte": 2015}}},
        {"$project": {"title": 1, "imdb.rating": 1, "_id": 0}},
        {"$sort": {"imdb.rating": -1}},
    ]),
    ("$lookup comentarios Dark Knight",  "movies", [
        {"$match": {"title": "The Dark Knight"}},
        {"$lookup": {"from": "comments", "localField": "_id", "foreignField": "movie_id", "as": "comentarios"}},
        {"$project": {"title": 1, "num_comentarios": {"$size": "$comentarios"}, "_id": 0}},
    ]),
]

ok = 0
for name, col, query in cases:
    try:
        results = execute_query(col, query)
        print(f"  OK  {name} -> {len(results)} doc(s)  {str(results[0])[:80] if results else '[]'}")
        ok += 1
    except Exception as e:
        print(f"  FAIL {name} -> {e}")

close()
print(f"\n{ok}/{len(cases)} examples verified.")
