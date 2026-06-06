"""Quick connectivity check: MongoDB Atlas + sample_mflix collections."""
import os
import sys
from dotenv import load_dotenv
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure, OperationFailure

load_dotenv()

URI = os.getenv("MONGODB_URI")
DB_NAME = os.getenv("MONGODB_DB_NAME", "sample_mflix")
EXPECTED_COLLECTIONS = {"movies", "comments", "users", "theaters", "sessions"}

def main():
    print(f"Connecting to {DB_NAME}...")
    try:
        client = MongoClient(URI, serverSelectionTimeoutMS=8000)
        client.admin.command("ping")
        print("  Ping OK")
    except ConnectionFailure as e:
        print(f"  Connection failed: {e}")
        sys.exit(1)

    db = client[DB_NAME]
    collections = set(db.list_collection_names())
    print(f"  Collections found: {sorted(collections)}")

    missing = EXPECTED_COLLECTIONS - collections
    if missing:
        print(f"  Missing collections: {missing}")
        print("  -> Load 'Sample Dataset' in Atlas (cluster > ... > Load Sample Dataset)")
        sys.exit(1)

    print("\nCollection stats:")
    for name in sorted(EXPECTED_COLLECTIONS & collections):
        count = db[name].estimated_document_count()
        sample = db[name].find_one({}, {"_id": 0})
        keys = list(sample.keys())[:6] if sample else []
        print(f"  {name:<12} {count:>6} docs   fields: {keys}")

    print("\nAll checks passed.")
    client.close()

if __name__ == "__main__":
    main()
