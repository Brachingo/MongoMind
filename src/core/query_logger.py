"""
Query logger — appends one JSON line per executed query to logs/queries.log.

Each record captures the question, the generated MQL, the target collection,
the number of results (or the error), and a UTC timestamp. This gives an audit
trail for security review and a raw dataset for later error analysis.

The log file can be redirected via the QUERY_LOG_FILE env variable (used in tests).
"""
import json
import os
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_LOG_FILE = Path(__file__).parent.parent.parent / "logs" / "queries.log"


def _log_path() -> Path:
    """Return the active log file path (overridable via QUERY_LOG_FILE)."""
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
    """Append a structured record of one query execution to the log file.

    Logging never raises: a logging failure must not break the user request,
    so any I/O error is swallowed (best-effort audit trail).
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
        # Best-effort: never let logging break the request path.
        pass
