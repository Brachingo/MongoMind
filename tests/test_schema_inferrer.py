"""Unit tests for schema_inferrer — no MongoDB connection required."""
import sys
sys.path.insert(0, ".")
import json
import pytest
from src.core.schema_inferrer import _py_type, _infer_fields, _infer_field, _safe_example


# ── _py_type ───────────────────────────────────────────────────────────────────

class TestPyType:
    def test_string(self):    assert _py_type("hello") == "string"
    def test_int(self):       assert _py_type(42)       == "integer"
    def test_float(self):     assert _py_type(3.14)     == "float"
    def test_bool(self):      assert _py_type(True)     == "boolean"
    def test_list(self):      assert _py_type([1, 2])   == "array"
    def test_dict(self):      assert _py_type({"a": 1}) == "object"
    def test_none(self):      assert _py_type(None)     == "null"


# ── _infer_field (scalars) ─────────────────────────────────────────────────────

class TestInferFieldScalar:
    def test_string_type(self):
        r = _infer_field(["Inception", "Titanic", "The Matrix"], total_docs=3)
        assert r["type"] == "string"

    def test_integer_type(self):
        r = _infer_field([2008, 1999, 2010], total_docs=3)
        assert r["type"] == "integer"

    def test_float_type(self):
        r = _infer_field([8.5, 7.2, 9.0], total_docs=3)
        assert r["type"] == "float"

    def test_example_present(self):
        r = _infer_field(["Inception", "Titanic"], total_docs=2)
        assert "example" in r

    def test_low_cardinality_string_gets_values(self):
        genres = ["Action", "Drama", "Comedy", "Horror", "Action", "Drama"]
        r = _infer_field(genres, total_docs=6)
        assert "values" in r
        assert set(r["values"]) == {"Action", "Comedy", "Drama", "Horror"}

    def test_high_cardinality_string_no_values(self):
        titles = [f"Movie {i}" for i in range(50)]
        r = _infer_field(titles, total_docs=50)
        assert "values" not in r

    def test_optional_flag_when_sparse(self):
        # Only 5 of 20 docs have this field
        r = _infer_field(["a", "b", "c", "d", "e"], total_docs=20)
        assert r.get("optional") is True

    def test_no_optional_flag_when_dense(self):
        r = _infer_field(["a"] * 19, total_docs=20)
        assert "optional" not in r


# ── _infer_field (arrays) ──────────────────────────────────────────────────────

class TestInferFieldArray:
    def test_array_of_strings(self):
        r = _infer_field([["Action", "Drama"], ["Comedy"]], total_docs=2)
        assert r["type"] == "array<string>"

    def test_array_of_strings_example(self):
        r = _infer_field([["Action", "Drama"], ["Comedy"]], total_docs=2)
        assert "example" in r

    def test_array_enum_values(self):
        r = _infer_field(
            [["Action", "Drama"], ["Comedy"], ["Horror", "Thriller"]],
            total_docs=3,
        )
        assert "values" in r
        assert "Action" in r["values"]

    def test_array_of_integers(self):
        r = _infer_field([[1, 2, 3], [4, 5]], total_docs=2)
        assert r["type"] == "array<integer>"


# ── _infer_field (objects) ─────────────────────────────────────────────────────

class TestInferFieldObject:
    def test_object_type(self):
        r = _infer_field([{"rating": 8.5, "votes": 1000}], total_docs=1)
        assert r["type"] == "object"

    def test_object_has_nested_fields(self):
        r = _infer_field(
            [{"rating": 8.5, "votes": 1000}, {"rating": 7.2, "votes": 500}],
            total_docs=2,
        )
        assert "fields" in r
        assert "rating" in r["fields"]
        assert "votes" in r["fields"]

    def test_nested_types(self):
        r = _infer_field(
            [{"rating": 8.5, "id": 42}, {"rating": 7.2, "id": 11}],
            total_docs=2,
        )
        assert r["fields"]["rating"]["type"] == "float"
        assert r["fields"]["id"]["type"] == "integer"


# ── _infer_fields (full document list) ────────────────────────────────────────

class TestInferFields:
    def test_basic_fields(self):
        docs = [
            {"title": "Inception", "year": 2010, "rating": 8.8},
            {"title": "Titanic",   "year": 1997, "rating": 7.8},
        ]
        fields = _infer_fields(docs)
        assert set(fields.keys()) == {"title", "year", "rating"}

    def test_id_excluded(self):
        docs = [{"_id": "abc123", "title": "Inception"}]
        fields = _infer_fields(docs)
        assert "_id" not in fields

    def test_optional_field_detected(self):
        docs = [{"title": f"Movie {i}"} for i in range(20)]
        docs[0]["rare_field"] = "value"  # only 1 of 20 has this field
        fields = _infer_fields(docs)
        assert fields["rare_field"].get("optional") is True

    def test_nested_object_inferred(self):
        docs = [
            {"title": "Movie A", "imdb": {"rating": 8.5, "votes": 1000}},
            {"title": "Movie B", "imdb": {"rating": 7.0, "votes": 500}},
        ]
        fields = _infer_fields(docs)
        assert fields["imdb"]["type"] == "object"
        assert "rating" in fields["imdb"]["fields"]

    def test_array_field_inferred(self):
        docs = [
            {"title": "Movie A", "genres": ["Action", "Drama"]},
            {"title": "Movie B", "genres": ["Comedy"]},
        ]
        fields = _infer_fields(docs)
        assert fields["genres"]["type"] == "array<string>"

    def test_mixed_presence_optional(self):
        docs = [{"title": f"M{i}", "plot": "text"} for i in range(10)]
        for i in range(3):
            docs[i]["awards"] = {"wins": i}
        fields = _infer_fields(docs)
        assert fields["awards"].get("optional") is True
        assert "optional" not in fields["plot"]


# ── _safe_example ──────────────────────────────────────────────────────────────

class TestSafeExample:
    def test_plain_value(self):
        assert _safe_example("Inception") == "Inception"

    def test_list_value(self):
        assert _safe_example([1, 2, 3]) == [1, 2, 3]

    def test_non_serialisable_becomes_string(self):
        class Unserializable:
            def __str__(self): return "custom"
        result = _safe_example(Unserializable())
        assert result == "custom"
