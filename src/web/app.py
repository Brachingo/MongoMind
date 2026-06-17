import json
import sys
import uuid
from pathlib import Path

# Para que la raíz del proyecto esté en sys.path al lanzarlo como script
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

from src.core import datasets, db_connector, mql_generator, nlp, query_logger
from src.core.sanitizer import sanitize_question
from src.web.rate_limit import RateLimiter

TEMPLATES_DIR = Path(__file__).parent / "templates"
IMAGES_DIR    = Path(__file__).resolve().parent.parent.parent / "images"

# Memoria conversacional: guardo los últimos N intercambios (par usuario + asistente).
HISTORY_WINDOW = 5
SESSION_COOKIE = "mm_session"

templates = Jinja2Templates(directory=TEMPLATES_DIR)

app = FastAPI(title="MongoMind")
app.mount("/static", StaticFiles(directory=IMAGES_DIR), name="static")

# Límite de 20 consultas por minuto por IP de cliente.
_rate_limiter = RateLimiter(max_requests=20, window_seconds=60.0)

# Sesiones en memoria: session_id -> {"history": list[dict], "collection": str}
_SESSIONS: dict[str, dict] = {}


class QueryRequest(BaseModel):
    question: str
    dataset: str | None = None   # una de datasets.dataset_keys(); None -> por defecto


class QueryResponse(BaseModel):
    mql: str
    results: list[dict]
    collection: str
    dataset: str = ""
    message: str | None = None   # info (p.ej. 0 resultados), no es un error
    error: str | None = None


def _to_serializable(docs: list[dict]) -> list[dict]:
    """Pasa los documentos de pymongo a dicts seguros para JSON (datetime, Decimal128, etc.)."""
    return json.loads(json.dumps(docs, default=str))


def _client_id(request: Request) -> str:
    """Identificador de cliente (best-effort) para el rate limit y el log."""
    return request.client.host if request.client else "unknown"


def _new_session() -> dict:
    return {"history": [], "collection": None, "dataset": datasets.DEFAULT_DATASET}


def _get_session(session_id: str | None) -> tuple[str, dict]:
    """Devuelve (session_id, session) y crea una sesión nueva si hace falta."""
    if session_id and session_id in _SESSIONS:
        return session_id, _SESSIONS[session_id]
    new_id = session_id or uuid.uuid4().hex
    session = _new_session()
    _SESSIONS[new_id] = session
    return new_id, session


@app.get("/", response_class=HTMLResponse)
async def index(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        request, "index.html", {"datasets": datasets.options()}
    )


@app.post("/reset")
def reset(request: Request) -> JSONResponse:
    """Borra la memoria conversacional de la sesión actual."""
    session_id = request.cookies.get(SESSION_COOKIE)
    if session_id and session_id in _SESSIONS:
        _SESSIONS[session_id] = _new_session()
    return JSONResponse({"ok": True})


@app.post("/query", response_model=QueryResponse)
def query(body: QueryRequest, request: Request, response: Response) -> QueryResponse:
    """Traduce la pregunta a MQL, la ejecuta y devuelve los resultados."""
    client = _client_id(request)

    # ── Rate limiting ────────────────────────────────────────────────────────
    if not _rate_limiter.allow(client):
        retry = int(_rate_limiter.retry_after(client)) + 1
        response.status_code = 429
        return QueryResponse(
            mql="", results=[], collection="",
            error=f"Demasiadas consultas. Inténtalo de nuevo en {retry} s.",
        )

    # ── Sesión / memoria conversacional ──────────────────────────────────────
    session_id, session = _get_session(request.cookies.get(SESSION_COOKIE))
    response.set_cookie(SESSION_COOKIE, session_id, httponly=True, samesite="lax")

    # ── Selección de dataset ─────────────────────────────────────────────────
    # Lo valido contra el registro conocido; al cambiar de dataset borro la
    # memoria, porque la anáfora entre datasets ("¿y ordenadas por año?") no vale.
    dataset = datasets.resolve(body.dataset)
    if dataset != session.get("dataset"):
        session["history"], session["collection"] = [], None
        session["dataset"] = dataset
    db_name = datasets.database_for(dataset)

    collection = ""
    mql_query: dict | list | None = None
    try:
        # ── Sanitización de la entrada ───────────────────────────────────────
        question = sanitize_question(body.question)

        collection = nlp.detect_collection(question, previous=session["collection"],
                                           dataset=dataset)
        mql_query = mql_generator.generate(question, collection,
                                           history=session["history"], database=db_name)
        raw_results = db_connector.execute_query(collection, mql_query, database=db_name)
        results = _to_serializable(raw_results)

        # Actualizo la memoria (me quedo solo con los últimos HISTORY_WINDOW intercambios).
        session["collection"] = collection
        session["history"].extend(mql_generator.history_turns(question, mql_query))
        del session["history"][: -2 * HISTORY_WINDOW]

        query_logger.log_query(question, collection, mql_query,
                               result_count=len(results), client=client)

        # Distingo "se ejecutó bien pero vacío" de un error real.
        message = None
        if not results:
            message = "La consulta se ejecutó correctamente, pero no devolvió resultados."

        return QueryResponse(
            mql=json.dumps(mql_query, indent=2, ensure_ascii=False),
            results=results,
            collection=collection,
            dataset=dataset,
            message=message,
        )
    except ValueError as exc:
        query_logger.log_query(body.question, collection, mql_query,
                               error=str(exc), client=client)
        return QueryResponse(mql="", results=[], collection="", dataset=dataset,
                             error=str(exc))
    except Exception as exc:
        query_logger.log_query(body.question, collection, mql_query,
                               error=str(exc), client=client)
        return QueryResponse(mql="", results=[], collection="", dataset=dataset,
                             error=f"Error inesperado: {exc}")


if __name__ == "__main__":
    host = os.getenv("APP_HOST", "0.0.0.0")
    port = int(os.getenv("APP_PORT", "8000"))
    uvicorn.run(app, host=host, port=port)
