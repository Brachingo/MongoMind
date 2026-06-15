"""
Integration tests for the FastAPI layer using TestClient.

The LLM (Ollama) and MongoDB (Atlas) are monkeypatched, so these tests run
offline and deterministically. They verify the Day 11/12 wiring:
session-based conversational memory, rate limiting, input sanitization,
and the 0-results-vs-error distinction.
"""
import sys
sys.path.insert(0, ".")
import json
import pytest
from fastapi.testclient import TestClient

import src.web.app as webapp
from src.web.rate_limit import RateLimiter


@pytest.fixture
def client(monkeypatch, tmp_path):
    # Redirect the query log to a temp file so tests don't touch the real log.
    monkeypatch.setenv("QUERY_LOG_FILE", str(tmp_path / "queries.log"))
    # Fake LLM: echoes the collection so we can assert on it; records history seen.
    calls = {"history": []}

    def fake_generate(question, collection, history=None, database=None):
        calls["history"].append(list(history or []))
        calls.setdefault("databases", []).append(database)
        return {"q": question, "col": collection}

    def fake_execute(collection, query, limit=100, database=None):
        # Return a non-empty result unless the question asks for "empty".
        if "vacio" in json.dumps(query, ensure_ascii=False):
            return []
        return [{"title": "Doc", "collection": collection}]

    monkeypatch.setattr(webapp.mql_generator, "generate", fake_generate)
    monkeypatch.setattr(webapp.db_connector, "execute_query", fake_execute)
    # Fresh session store + generous rate limiter per test.
    webapp._SESSIONS.clear()
    webapp._rate_limiter = RateLimiter(max_requests=100, window_seconds=60)
    c = TestClient(webapp.app)
    c._calls = calls
    return c


def test_basic_query_returns_results(client):
    r = client.post("/query", json={"question": "películas de accion"})
    assert r.status_code == 200
    body = r.json()
    assert body["error"] is None
    assert body["collection"] == "movies"
    assert len(body["results"]) == 1


def test_sets_session_cookie(client):
    r = client.post("/query", json={"question": "películas de accion"})
    assert webapp.SESSION_COOKIE in r.cookies


def test_empty_input_is_rejected(client):
    r = client.post("/query", json={"question": "   "})
    assert r.json()["error"] is not None
    assert "vac" in r.json()["error"].lower()


def test_zero_results_sets_message_not_error(client):
    # "vacio" makes the fake DB return [] -> info message, not error.
    r = client.post("/query", json={"question": "buscar vacio total"})
    body = r.json()
    assert body["error"] is None
    assert body["message"] is not None
    assert body["results"] == []


def test_conversational_memory_grows_across_turns(client):
    client.post("/query", json={"question": "películas de accion"})
    client.post("/query", json={"question": "¿y ordenadas por año?"})
    # The 2nd generate() call must have received the 1st exchange as history.
    second_call_history = client._calls["history"][1]
    assert len(second_call_history) == 2  # user + assistant from turn 1
    assert "películas de accion" in second_call_history[0]["content"]


def test_reset_clears_memory(client):
    client.post("/query", json={"question": "películas de accion"})
    client.post("/reset")
    client.post("/query", json={"question": "otra cosa cualquiera"})
    # After reset, the latest generate() call sees empty history again.
    assert client._calls["history"][-1] == []


def test_dataset_selection_routes_to_its_database(client):
    # Selecting sample_airbnb must run against that database and route to its collection.
    r = client.post("/query", json={"question": "alojamientos baratos",
                                     "dataset": "sample_airbnb"})
    body = r.json()
    assert body["dataset"] == "sample_airbnb"
    assert body["collection"] == "listingsAndReviews"
    assert client._calls["databases"][-1] == "sample_airbnb"


def test_unknown_dataset_falls_back_to_default(client):
    r = client.post("/query", json={"question": "películas de accion",
                                     "dataset": "no_existe"})
    body = r.json()
    assert body["dataset"] == "sample_mflix"
    assert body["collection"] == "movies"


def test_switching_dataset_clears_memory(client):
    client.post("/query", json={"question": "películas de accion",
                                "dataset": "sample_mflix"})
    client.post("/query", json={"question": "alojamientos en Madrid",
                                "dataset": "sample_airbnb"})
    # The airbnb call must NOT have seen the mflix exchange as history.
    assert client._calls["history"][-1] == []


def test_rate_limit_returns_429(client):
    webapp._rate_limiter = RateLimiter(max_requests=2, window_seconds=60)
    client.post("/query", json={"question": "una"})
    client.post("/query", json={"question": "dos"})
    r = client.post("/query", json={"question": "tres"})
    assert r.status_code == 429
    assert "Demasiadas" in r.json()["error"]
