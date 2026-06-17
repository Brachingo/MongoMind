"""Tests del log de queries — escribe en un fichero temporal vía QUERY_LOG_FILE."""
import sys
sys.path.insert(0, ".")
import json
import importlib


def _fresh_logger(tmp_path, monkeypatch):
    log_file = tmp_path / "queries.log"
    monkeypatch.setenv("QUERY_LOG_FILE", str(log_file))
    # Reimporto para que el módulo coja la variable de entorno vía _log_path().
    from src.core import query_logger
    importlib.reload(query_logger)
    return query_logger, log_file


def test_writes_one_jsonl_record(tmp_path, monkeypatch):
    logger, log_file = _fresh_logger(tmp_path, monkeypatch)
    logger.log_query("¿cuántas pelis?", "movies", [{"$count": "n"}],
                     result_count=1, client="127.0.0.1")
    lines = log_file.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    rec = json.loads(lines[0])
    assert rec["question"] == "¿cuántas pelis?"
    assert rec["collection"] == "movies"
    assert rec["result_count"] == 1
    assert rec["error"] is None
    assert "timestamp" in rec


def test_appends_multiple_records(tmp_path, monkeypatch):
    logger, log_file = _fresh_logger(tmp_path, monkeypatch)
    logger.log_query("q1", "movies", {}, result_count=0)
    logger.log_query("q2", "comments", [], error="boom")
    lines = log_file.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 2
    assert json.loads(lines[1])["error"] == "boom"


def test_logging_never_raises_on_bad_path(tmp_path, monkeypatch):
    # Pongo un fichero donde se espera un directorio, así mkdir/open fallan;
    # log_query debe tragarse el OSError en vez de romper la petición.
    blocker = tmp_path / "blocker"
    blocker.write_text("i am a file, not a directory")
    monkeypatch.setenv("QUERY_LOG_FILE", str(blocker / "queries.log"))
    from src.core import query_logger
    importlib.reload(query_logger)
    query_logger.log_query("q", "movies", {}, result_count=0)  # must not raise
