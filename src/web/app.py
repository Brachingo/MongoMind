import json
import sys
import uuid
from pathlib import Path

# Ensure project root is in sys.path when running as a script
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import os
import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, Request, Response
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

load_dotenv()

from src.core import db_connector, mql_generator, nlp, query_logger
from src.core.sanitizer import sanitize_question
from src.web.rate_limit import RateLimiter

TEMPLATES_DIR = Path(__file__).parent / "templates"
IMAGES_DIR    = Path(__file__).resolve().parent.parent.parent / "images"

# Conversational memory: keep the last N exchanges (user + assistant pairs).
HISTORY_WINDOW = 5
SESSION_COOKIE = "mm_session"

templates = Jinja2Templates(directory=TEMPLATES_DIR)

app = FastAPI(title="MongoMind")
app.mount("/static", StaticFiles(directory=IMAGES_DIR), name="static")

# Rate limit: max 20 queries per minute per client IP.
_rate_limiter = RateLimiter(max_requests=20, window_seconds=60.0)

# In-memory session store: session_id -> {"history": list[dict], "collection": str}
_SESSIONS: dict[str, dict] = {}


class QueryRequest(BaseModel):
    question: str


class QueryResponse(BaseModel):
    mql: str
    results: list[dict]
    collection: str
    message: str | None = None   # info (e.g. 0 results), not an error
    error: str | None = None


def _to_serializable(docs: list[dict]) -> list[dict]:
    """Convert pymongo documents to JSON-safe dicts (handles datetime, Decimal128, etc.)."""
    return json.loads(json.dumps(docs, default=str))


def _client_id(request: Request) -> str:
    """Best-effort client identifier for rate limiting / logging."""
    return request.client.host if request.client else "unknown"


def _get_session(session_id: str | None) -> tuple[str, dict]:
    """Return (session_id, session) creating a fresh session when needed."""
    if session_id and session_id in _SESSIONS:
        return session_id, _SESSIONS[session_id]
    new_id = session_id or uuid.uuid4().hex
    session = {"history": [], "collection": None}
    _SESSIONS[new_id] = session
    return new_id, session


@app.get("/", response_class=HTMLResponse)
async def index(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "index.html")


@app.post("/reset")
def reset(request: Request) -> JSONResponse:
    """Clear the conversational memory for the current session."""
    session_id = request.cookies.get(SESSION_COOKIE)
    if session_id and session_id in _SESSIONS:
        _SESSIONS[session_id] = {"history": [], "collection": None}
    return JSONResponse({"ok": True})


@app.post("/query", response_model=QueryResponse)
def query(body: QueryRequest, request: Request, response: Response) -> QueryResponse:
    """Translate a natural language question to MQL, execute it, and return results."""
    client = _client_id(request)

    # ── Rate limiting ────────────────────────────────────────────────────────
    if not _rate_limiter.allow(client):
        retry = int(_rate_limiter.retry_after(client)) + 1
        response.status_code = 429
        return QueryResponse(
            mql="", results=[], collection="",
            error=f"Demasiadas consultas. Inténtalo de nuevo en {retry} s.",
        )

    # ── Session / conversational memory ──────────────────────────────────────
    session_id, session = _get_session(request.cookies.get(SESSION_COOKIE))
    response.set_cookie(SESSION_COOKIE, session_id, httponly=True, samesite="lax")

    collection = ""
    mql_query: dict | list | None = None
    try:
        # ── Input sanitization ───────────────────────────────────────────────
        question = sanitize_question(body.question)

        collection = nlp.detect_collection(question, previous=session["collection"])
        mql_query = mql_generator.generate(question, collection, history=session["history"])
        raw_results = db_connector.execute_query(collection, mql_query)
        results = _to_serializable(raw_results)

        # Update conversational memory (trim to the last HISTORY_WINDOW exchanges).
        session["collection"] = collection
        session["history"].extend(mql_generator.history_turns(question, mql_query))
        del session["history"][: -2 * HISTORY_WINDOW]

        query_logger.log_query(question, collection, mql_query,
                               result_count=len(results), client=client)

        # Distinguish "ran fine but empty" from a real error.
        message = None
        if not results:
            message = "La consulta se ejecutó correctamente, pero no devolvió resultados."

        return QueryResponse(
            mql=json.dumps(mql_query, indent=2, ensure_ascii=False),
            results=results,
            collection=collection,
            message=message,
        )
    except ValueError as exc:
        query_logger.log_query(body.question, collection, mql_query,
                               error=str(exc), client=client)
        return QueryResponse(mql="", results=[], collection="", error=str(exc))
    except Exception as exc:
        query_logger.log_query(body.question, collection, mql_query,
                               error=str(exc), client=client)
        return QueryResponse(mql="", results=[], collection="",
                             error=f"Error inesperado: {exc}")


if __name__ == "__main__":
    host = os.getenv("APP_HOST", "0.0.0.0")
    port = int(os.getenv("APP_PORT", "8000"))
    uvicorn.run(app, host=host, port=port)
