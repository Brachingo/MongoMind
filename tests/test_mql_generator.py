"""Unit tests for mql_generator helpers — no model inference required."""
import sys
sys.path.insert(0, ".")
import json
import pytest
from src.core.mql_generator import (
    _extract_json, _check_no_writes, _build_messages, history_turns, _repair_json,
)


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


# ── _repair_json (tolerancia a JSON casi-válido del LLM) ─────────────────────────

class TestRepairJson:
    def test_quotes_unquoted_key(self):
        assert json.loads(_repair_json('{"$sample": {size: 5}}')) == {"$sample": {"size": 5}}

    def test_quotes_multiple_unquoted_keys(self):
        repaired = _repair_json('{"$project": {text: 1, year: 1}}')
        assert json.loads(repaired) == {"$project": {"text": 1, "year": 1}}

    def test_removes_trailing_comma(self):
        assert json.loads(_repair_json('[{"$match": {}},]')) == [{"$match": {}}]

    def test_already_valid_json_unchanged(self):
        valid = '{"genres": "Action"}'
        assert json.loads(_repair_json(valid)) == {"genres": "Action"}

    def test_does_not_corrupt_string_values(self):
        # A colon inside a string value must not be treated as a key separator.
        valid = '{"title": "Mission: Impossible"}'
        assert json.loads(_repair_json(valid)) == {"title": "Mission: Impossible"}


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


# ── Conversational history ───────────────────────────────────────────────────

class TestHistory:
    def test_no_history_is_two_messages(self):
        msgs = _build_messages("q", "movies", history=None)
        assert len(msgs) == 2
        assert [m["role"] for m in msgs] == ["system", "user"]

    def test_history_inserted_between_system_and_question(self):
        hist = history_turns("primera pregunta", {"genres": "Action"})
        msgs = _build_messages("segunda pregunta", "movies", history=hist)
        # system + 2 history turns + current user question
        assert [m["role"] for m in msgs] == ["system", "user", "assistant", "user"]

    def test_history_preserves_prior_question_and_answer(self):
        hist = history_turns("pelis de accion", {"genres": "Action"})
        msgs = _build_messages("¿y ordenadas por año?", "movies", history=hist)
        joined = "\n".join(m["content"] for m in msgs)
        assert "pelis de accion" in joined
        assert '"genres": "Action"' in joined or '"Action"' in joined

    def test_current_question_is_last(self):
        hist = history_turns("antigua", {"year": 2000})
        msgs = _build_messages("nueva pregunta", "movies", history=hist)
        assert "nueva pregunta" in msgs[-1]["content"]
        assert msgs[-1]["role"] == "user"


class TestHistoryTurns:
    def test_returns_user_then_assistant(self):
        turns = history_turns("hola", {"a": 1})
        assert [t["role"] for t in turns] == ["user", "assistant"]

    def test_assistant_content_is_valid_json(self):
        turns = history_turns("hola", [{"$match": {"x": 1}}])
        assert json.loads(turns[1]["content"]) == [{"$match": {"x": 1}}]

    def test_user_content_contains_question(self):
        turns = history_turns("¿cuántas pelis?", {})
        assert "¿cuántas pelis?" in turns[0]["content"]
