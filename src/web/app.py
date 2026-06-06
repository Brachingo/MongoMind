import json
import sys
from pathlib import Path

# Ensure project root is in sys.path when running as a script
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import os
import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

load_dotenv()

from src.core import db_connector, mql_generator, nlp

TEMPLATES_DIR = Path(__file__).parent / "templates"
IMAGES_DIR    = Path(__file__).resolve().parent.parent.parent / "images"

templates = Jinja2Templates(directory=TEMPLATES_DIR)

app = FastAPI(title="MongoMind")
app.mount("/static", StaticFiles(directory=IMAGES_DIR), name="static")


class QueryRequest(BaseModel):
    question: str


class QueryResponse(BaseModel):
    mql: str
    results: list[dict]
    collection: str
    error: str | None = None


def _to_serializable(docs: list[dict]) -> list[dict]:
    """Convert pymongo documents to JSON-safe dicts (handles datetime, Decimal128, etc.)."""
    return json.loads(json.dumps(docs, default=str))


@app.get("/", response_class=HTMLResponse)
async def index(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "index.html")


@app.post("/query", response_model=QueryResponse)
def query(body: QueryRequest) -> QueryResponse:
    """Translate a natural language question to MQL, execute it, and return results."""
    try:
        collection = nlp.detect_collection(body.question)
        mql_query = mql_generator.generate(body.question, collection)
        raw_results = db_connector.execute_query(collection, mql_query)
        results = _to_serializable(raw_results)
        return QueryResponse(
            mql=json.dumps(mql_query, indent=2, ensure_ascii=False),
            results=results,
            collection=collection,
        )
    except ValueError as exc:
        return QueryResponse(mql="", results=[], collection="", error=str(exc))
    except Exception as exc:
        return QueryResponse(mql="", results=[], collection="", error=f"Error inesperado: {exc}")


if __name__ == "__main__":
    host = os.getenv("APP_HOST", "0.0.0.0")
    port = int(os.getenv("APP_PORT", "8000"))
    uvicorn.run(app, host=host, port=port)
