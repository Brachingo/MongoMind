"""
Log de queries: escribe una línea JSON por cada query ejecutada en
logs/queries.log.

Cada registro guarda la pregunta, el MQL generado, la colección, el número de
resultados (o el error) y la marca de tiempo en UTC. Sirve como traza de
auditoría para revisar seguridad y como material en bruto para analizar errores.

La ruta del log se puede cambiar con la variable QUERY_LOG_FILE (lo usan los tests).
"""
import json
import os
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_LOG_FILE = Path(__file__).parent.parent.parent / "logs" / "queries.log"


def _log_path() -> Path:
    """Ruta del log activa (se puede sobreescribir con QUERY_LOG_FILE)."""
    override = os.getenv("QUERY_LOG_FILE")
    return Path(override) if override else DEFAULT_LOG_FILE


def log_query(
    question: str,
    collection: str,
    mql: dict | list | None,
    result_count: int | None = None,
    error: str | None = None,
    client: str | None = None,
) -> None:
    """Añade al log un registro estructurado de una ejecución de query.

    El logging nunca lanza: que falle el log no puede tumbar la petición del
    usuario, así que me trago cualquier error de E/S (auditoría best-effort).
    """
    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "client": client,
        "collection": collection,
        "question": question,
        "mql": mql,
        "result_count": result_count,
        "error": error,
    }
    try:
        path = _log_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps(record, ensure_ascii=False, default=str)
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(line + "\n")
    except OSError:
        # Best-effort: que el log no rompa nunca el flujo de la petición.
        pass
