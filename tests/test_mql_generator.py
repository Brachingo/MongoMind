"""Unit tests for mql_generator helpers — no model inference required."""
import sys
sys.path.insert(0, ".")
import json
import pytest
from src.core.mql_generator import _extract_json, _check_no_writes, _build_messages


# ── _extract_json ──────────────────────────────────────────────────────────────

class TestExtractJson:
    def test_plain_object(self):
        assert _extract_json('{"title": "Inception"}') == '{"title": "Inception"}'

    def test_plain_array(self):
        raw = '[{"$match": {"year": 2010}}]'
        assert _extract_json(raw) == raw

    def test_strips_markdown_json_fence(self):
        raw = '```json\n{"genres": "Action"}\n```'
        assert _extract_json(raw) == '{"genres": "Action"}'

    def test_strips_plain_code_fence(self):
        raw = '```\n{"year": 2010}\n```'
        assert _extract_json(raw) == '{"year": 2010}'

    def test_extracts_json_from_surrounding_text(self):
        raw = 'Here is the query:\n{"imdb.rating": {"$gt": 8}}\nDone.'
        result = _extract_json(raw)
        assert json.loads(result) == {"imdb.rating": {"$gt": 8}}

    def test_extracts_array_from_surrounding_text(self):
        raw = 'The pipeline is [{"$match": {}}] as requested.'
        result = _extract_json(raw)
        assert json.loads(result) == [{"$match": {}}]


# ── _check_no_writes ───────────────────────────────────────────────────────────

class TestCheckNoWrites:
    def test_safe_query_passes(self):
        _check_no_writes({"genres": "Action"})

    def test_safe_pipeline_passes(self):
        _check_no_writes([{"$match": {"year": 2010}}, {"$limit": 5}])

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


# ── _build_messages ────────────────────────────────────────────────────────────

class TestBuildMessages:
    def test_returns_two_messages(self):
        msgs = _build_messages("find action movies", "movies")
        assert len(msgs) == 2

    def test_first_is_system(self):
        msgs = _build_messages("find action movies", "movies")
        assert msgs[0]["role"] == "system"

    def test_second_is_user(self):
        msgs = _build_messages("find action movies", "movies")
        assert msgs[1]["role"] == "user"

    def test_user_message_contains_question(self):
        msgs = _build_messages("find action movies", "movies")
        assert "find action movies" in msgs[1]["content"]

    def test_system_contains_schema(self):
        msgs = _build_messages("any question", "movies")
        assert "imdb.rating" in msgs[0]["content"]

    def test_system_contains_examples(self):
        msgs = _build_messages("any question", "movies")
        assert "Christopher Nolan" in msgs[0]["content"]

    def test_system_does_not_contain_placeholder(self):
        msgs = _build_messages("any question", "movies")
        assert "{user_question}" not in msgs[0]["content"]
