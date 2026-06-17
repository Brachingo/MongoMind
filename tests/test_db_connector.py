"""Tests de db_connector contra el cluster real sample_mflix de Atlas."""
import pytest
from src.core.db_connector import execute_query, close


@pytest.fixture(scope="session", autouse=True)
def cleanup():
    yield
    close()


def test_find_returns_list_of_dicts():
    results = execute_query("movies", {"title": "Inception"})
    assert isinstance(results, list)
    assert len(results) == 1
    assert results[0]["title"] == "Inception"


def test_find_excludes_id():
    results = execute_query("movies", {"title": "Inception"})
    assert "_id" not in results[0]


def test_aggregate_count():
    pipeline = [{"$match": {"genres": "Action"}}, {"$count": "total"}]
    results = execute_query("movies", pipeline)
    assert len(results) == 1
    assert results[0]["total"] > 0


def test_limit_is_respected():
    results = execute_query("movies", {}, limit=5)
    assert len(results) <= 5


def test_invalid_query_type_raises():
    with pytest.raises((ValueError, TypeError)):
        execute_query("movies", "bad query")


def test_unknown_collection_returns_empty():
    results = execute_query("nonexistent_collection_xyz", {})
    assert results == []
