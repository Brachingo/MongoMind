"""
Carga datasets de muestra de MongoDB (sample_airbnb, sample_analytics) en el
cluster de Atlas usando los ficheros NDJSON (Extended JSON) de un mirror público.

Atlas solo permite cargar TODOS los sample datasets a la vez desde su UI. Este
script importa selectivamente las colecciones que necesitamos para probar la
generalización de MongoMind a otras bases de datos, sin depender de mongoimport.

Por defecto clona el mirror público él mismo (un solo comando, reproducible). Si
ya lo tienes clonado, pásalo con --src para evitar la descarga.

Uso:
    python scripts/load_sample_datasets.py                 # auto-clona y carga todo
    python scripts/load_sample_datasets.py --only sample_analytics
    python scripts/load_sample_datasets.py --drop          # recrea las colecciones
    python scripts/load_sample_datasets.py --src <ruta>    # usa un mirror ya clonado

Requiere MONGODB_URI con permisos de ESCRITURA en el entorno (.env): el usuario
de solo lectura del proyecto no puede insertar. Idempotente con --drop.
"""
import argparse
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import certifi
from bson import json_util
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv()

# Mirror público de los sample datasets de MongoDB en formato NDJSON (Extended JSON).
MIRROR_URL = "https://github.com/neelabalan/mongodb-sample-dataset.git"

# database -> [collection names] (el nombre de fichero es <collection>.json)
DATASETS: dict[str, list[str]] = {
    "sample_airbnb": ["listingsAndReviews"],
    "sample_analytics": ["accounts", "customers", "transactions"],
}

BATCH = 1000


def _clone_mirror() -> Path:
    """Clona el mirror (shallow) en un directorio temporal y devuelve su ruta."""
    dest = Path(tempfile.gettempdir()) / "mongodb-sample-dataset"
    if (dest / "sample_airbnb").exists():
        print(f"Mirror ya presente en {dest}")
        return dest
    print(f"Clonando mirror en {dest} ...")
    subprocess.run(
        ["git", "clone", "--depth", "1", MIRROR_URL, str(dest)],
        check=True,
    )
    return dest


def _client() -> MongoClient:
    uri = os.getenv("MONGODB_URI")
    if not uri:
        sys.exit("ERROR: MONGODB_URI no está definido en el entorno (.env)")
    return MongoClient(uri, serverSelectionTimeoutMS=20000, tlsCAFile=certifi.where())


def _load_collection(col, path: Path, drop: bool) -> int:
    if drop:
        col.drop()
    inserted, batch = 0, []
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            batch.append(json_util.loads(line))
            if len(batch) >= BATCH:
                col.insert_many(batch, ordered=False)
                inserted += len(batch)
                batch = []
                print(f"    ...{inserted} docs", end="\r")
    if batch:
        col.insert_many(batch, ordered=False)
        inserted += len(batch)
    return inserted


def main():
    ap = argparse.ArgumentParser(description="Carga sample datasets en Atlas")
    ap.add_argument("--src", help="Ruta a un mirror ya clonado (si se omite, se clona solo)")
    ap.add_argument("--only", choices=list(DATASETS), help="Cargar solo este dataset")
    ap.add_argument("--drop", action="store_true", help="Eliminar colección antes de cargar")
    args = ap.parse_args()

    src = Path(args.src) if args.src else _clone_mirror()
    targets = {args.only: DATASETS[args.only]} if args.only else DATASETS

    client = _client()
    for db_name, collections in targets.items():
        db = client[db_name]
        print(f"\n[{db_name}]")
        for col_name in collections:
            path = src / db_name / f"{col_name}.json"
            if not path.exists():
                print(f"  {col_name}: NO encontrado en {path} — saltando")
                continue
            existing = db[col_name].estimated_document_count()
            if existing and not args.drop:
                print(f"  {col_name}: ya tiene {existing} docs (usa --drop para recargar) — saltando")
                continue
            n = _load_collection(db[col_name], path, args.drop)
            print(f"  {col_name}: {n} docs cargados".ljust(40))
    client.close()
    print("\nHecho.")


if __name__ == "__main__":
    main()
