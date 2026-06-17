"""Tests de la lógica de comparación de eval — sin Ollama ni Atlas."""
import sys
sys.path.insert(0, ".")
from tests.eval import (
    functional_match, exact_match, scalar_value, count_value,
    titles, groups_map, num_close,
)


# ── extracción ───────────────────────────────────────────────────────────────

class TestExtractors:
    def test_scalar_value_single_metric(self):
        assert scalar_value([{"_id": None, "media": 102.5}]) == 102.5

    def test_scalar_value_ignores_id(self):
        assert scalar_value([{"_id": None, "total": 7}]) == 7

    def test_scalar_value_none_when_many(self):
        assert scalar_value([{"a": 1}, {"a": 2}]) is None

    def test_count_value_from_count_doc(self):
        assert count_value([{"total": 42}]) == 42

    def test_count_value_falls_back_to_len(self):
        assert count_value([{"title": "A"}, {"title": "B"}]) == 2

    def test_titles_extraction(self):
        assert titles([{"title": "A"}, {"title": "B"}]) == {"A", "B"}

    def test_groups_map_primary_metric(self):
        gm = groups_map([{"_id": "Action", "total": 10}, {"_id": "Drama", "total": 5}])
        assert gm == {'"Action"': 10, '"Drama"': 5}

    def test_num_close_float_tolerance(self):
        assert num_close(102.5000, 102.5004) is True
        assert num_close(102.5, 110.0) is False


# ── count ────────────────────────────────────────────────────────────────────

class TestCount:
    def test_count_match_different_field_name(self):
        ok, _ = functional_match("count", [{"total": 100}], [{"count": 100}])
        assert ok is True

    def test_count_match_model_returned_docs(self):
        # El modelo devolvió los documentos en vez de un conteo -> len == el conteo.
        expected = [{"total": 3}]
        actual = [{"title": "A"}, {"title": "B"}, {"title": "C"}]
        ok, _ = functional_match("count", expected, actual)
        assert ok is True

    def test_count_mismatch(self):
        ok, _ = functional_match("count", [{"total": 100}], [{"total": 99}])
        assert ok is False


# ── scalar ───────────────────────────────────────────────────────────────────

class TestScalar:
    def test_scalar_match_within_tolerance(self):
        ok, _ = functional_match("scalar", [{"_id": None, "avg": 100.0}], [{"_id": None, "media": 100.05}])
        assert ok is True

    def test_scalar_mismatch(self):
        ok, _ = functional_match("scalar", [{"_id": None, "avg": 100.0}], [{"_id": None, "avg": 50.0}])
        assert ok is False


# ── documents ────────────────────────────────────────────────────────────────

class TestDocuments:
    def test_documents_match_by_title_ignoring_projection(self):
        expected = [{"title": "A", "imdb": {"rating": 9}}]
        actual = [{"title": "A", "year": 2008, "genres": ["Action"]}]  # distinta proyección
        ok, partial = functional_match("documents", expected, actual)
        assert ok is True and partial == 1.0

    def test_documents_order_independent(self):
        expected = [{"title": "A"}, {"title": "B"}]
        actual = [{"title": "B"}, {"title": "A"}]
        ok, _ = functional_match("documents", expected, actual)
        assert ok is True

    def test_documents_partial_jaccard(self):
        expected = [{"title": "A"}, {"title": "B"}, {"title": "C"}, {"title": "D"}]
        actual = [{"title": "A"}, {"title": "B"}]
        ok, partial = functional_match("documents", expected, actual)
        assert ok is False
        assert abs(partial - 0.5) < 1e-9   # |inter|=2, |union|=4

    def test_documents_mismatch(self):
        ok, _ = functional_match("documents", [{"title": "A"}], [{"title": "Z"}])
        assert ok is False


# ── groups ───────────────────────────────────────────────────────────────────

class TestGroups:
    def test_groups_match_different_metric_name(self):
        expected = [{"_id": "Action", "total": 10}, {"_id": "Drama", "total": 5}]
        actual = [{"_id": "Drama", "n": 5}, {"_id": "Action", "n": 10}]  # otro nombre + orden
        ok, partial = functional_match("groups", expected, actual)
        assert ok is True and partial == 1.0

    def test_groups_mismatch_value(self):
        expected = [{"_id": "Action", "total": 10}]
        actual = [{"_id": "Action", "total": 7}]
        ok, _ = functional_match("groups", expected, actual)
        assert ok is False

    def test_groups_missing_key_partial(self):
        expected = [{"_id": "Action", "total": 10}, {"_id": "Drama", "total": 5}]
        actual = [{"_id": "Action", "total": 10}]
        ok, partial = functional_match("groups", expected, actual)
        assert ok is False and abs(partial - 0.5) < 1e-9


# ── exact match ──────────────────────────────────────────────────────────────

class TestExactMatch:
    def test_exact_match_key_order_insensitive(self):
        assert exact_match({"genres": "Action", "year": 2010},
                           {"year": 2010, "genres": "Action"}) is True

    def test_exact_match_pipeline_order_sensitive(self):
        a = [{"$match": {"x": 1}}, {"$limit": 5}]
        b = [{"$limit": 5}, {"$match": {"x": 1}}]
        assert exact_match(a, b) is False

    def test_exact_match_false_on_difference(self):
        assert exact_match({"genres": "Action"}, {"genres": "Drama"}) is False
