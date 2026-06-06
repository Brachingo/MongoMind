"""Unit tests for mql_generator helpers — no model inference required."""
import sys
sys.path.insert(0, ".")
import pytest
from src.core.mql_generator import _safe_parse, _parse_shell, _check_no_writes


# ── _safe_parse ────────────────────────────────────────────────────────────────

class TestSafeParse:
    def test_json_object(self):
        assert _safe_parse('{"title": "Inception"}') == {"title": "Inception"}

    def test_json_array(self):
        result = _safe_parse('[{"$match": {"year": 2010}}]')
        assert result == [{"$match": {"year": 2010}}]

    def test_python_single_quotes(self):
        assert _safe_parse("{'title': 'Inception'}") == {"title": "Inception"}

    def test_nested_operator(self):
        r = _safe_parse('{"imdb.rating": {"$gt": 8}}')
        assert r == {"imdb.rating": {"$gt": 8}}

    def test_invalid_raises(self):
        with pytest.raises(ValueError):
            _safe_parse("not json!!!")


# ── _parse_shell ───────────────────────────────────────────────────────────────

class TestParseShell:
    def test_find_no_projection(self):
        result = _parse_shell('db.movies.find({"genres": "Action"})')
        assert result == {"genres": "Action"}

    def test_find_with_projection_returns_pipeline(self):
        result = _parse_shell('db.movies.find({"year": 2010}, {"_id": 0, "title": 1})')
        assert isinstance(result, list)
        assert result[0] == {"$match": {"year": 2010}}
        assert {"$project": {"_id": 0, "title": 1}} in result

    def test_aggregate(self):
        result = _parse_shell(
            'db.movies.aggregate([{"$group": {"_id": "$genres", "count": {"$sum": 1}}}])'
        )
        assert isinstance(result, list)
        assert result[0]["$group"]["_id"] == "$genres"

    def test_find_sort_limit(self):
        result = _parse_shell(
            'db.movies.find({}, {"_id": 0}).sort([("imdb.rating", -1)]).limit(5)'
        )
        assert isinstance(result, list)
        ops = [list(s.keys())[0] for s in result]
        assert "$sort" in ops
        assert "$limit" in ops
        sort_stage = next(s for s in result if "$sort" in s)
        assert sort_stage["$sort"]["imdb.rating"] == -1
        limit_stage = next(s for s in result if "$limit" in s)
        assert limit_stage["$limit"] == 5

    def test_find_nested_filter(self):
        result = _parse_shell('db.movies.find({"imdb.rating": {"$gt": 8}})')
        assert result == {"imdb.rating": {"$gt": 8}}

    def test_unrecognized_raises(self):
        with pytest.raises(ValueError):
            _parse_shell("SELECT * FROM movies")


# ── _check_no_writes ───────────────────────────────────────────────────────────

class TestCheckNoWrites:
    def test_safe_query_passes(self):
        _check_no_writes({"genres": "Action"})

    def test_insert_rejected(self):
        with pytest.raises(ValueError, match="write operator"):
            _check_no_writes({"insertOne": {"title": "bad"}})

    def test_drop_rejected(self):
        with pytest.raises(ValueError, match="write operator"):
            _check_no_writes([{"drop": "movies"}])

    def test_out_in_pipeline_rejected(self):
        with pytest.raises(ValueError, match="write operator"):
            _check_no_writes([{"$match": {}}, {"$out": "backup"}])

    def test_merge_rejected(self):
        with pytest.raises(ValueError, match="write operator"):
            _check_no_writes([{"$merge": {"into": "other"}}])
