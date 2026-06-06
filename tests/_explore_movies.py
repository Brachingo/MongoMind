import sys
sys.path.insert(0, ".")
from src.core.db_connector import execute_query, close

genres = execute_query("movies", [
    {"$unwind": "$genres"},
    {"$group": {"_id": "$genres"}},
    {"$sort": {"_id": 1}},
])
print("GENRES:", [g["_id"] for g in genres])

rated = execute_query("movies", [
    {"$group": {"_id": "$rated"}},
    {"$sort": {"_id": 1}},
])
print("RATED:", [r["_id"] for r in rated])

yr = execute_query("movies", [
    {"$group": {"_id": None, "minYear": {"$min": "$year"}, "maxYear": {"$max": "$year"}}},
])
print("YEAR RANGE:", yr)

top_directors = execute_query("movies", [
    {"$unwind": "$directors"},
    {"$group": {"_id": "$directors", "count": {"$sum": 1}}},
    {"$sort": {"count": -1}},
    {"$limit": 5},
])
print("TOP DIRECTORS:", top_directors)

avg_runtime = execute_query("movies", [
    {"$match": {"runtime": {"$exists": True}}},
    {"$group": {"_id": None, "avgRuntime": {"$avg": "$runtime"}}},
])
print("AVG RUNTIME:", avg_runtime)

close()
