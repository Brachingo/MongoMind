"""Structural validation of the movies benchmark — no MongoDB/Ollama needed."""
import sys
sys.path.insert(0, ".")
import json
from pathlib import Path
import pytest
from src.core.mql_generator import _check_no_writes

BENCHMARK_PATH = Path(__file__).parent.parent / "data" / "benchmark" / "movies_benchmark.json"

_COMPLEXITIES = {"simple", "media", "alta", "ambiguous"}
_RESULT_TYPES = {"documents", "count", "scalar", "groups"}
_LANGS = {"es", "en"}
_SPLITS = {"dev", "test"}


@pytest.fixture(scope="module")
def data():
    return json.loads(BENCHMARK_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def pairs(data):
    return data["pairs"]


def test_file_loads_and_has_pairs(pairs):
    assert isinstance(pairs, list)
    assert len(pairs) >= 60


def test_ids_are_unique(pairs):
    ids = [p["id"] for p in pairs]
    assert len(ids) == len(set(ids))


def test_required_fields_present_and_typed(pairs):
    for p in pairs:
        assert isinstance(p["question"], str) and p["question"].strip()
        assert p["complexity"] in _COMPLEXITIES
        assert p["result_type"] in _RESULT_TYPES
        assert p["lang"] in _LANGS
        assert p["split"] in _SPLITS
        assert isinstance(p["expected_mql"], (dict, list))
        # find filter is a non-empty dict; pipeline is a non-empty list
        assert p["expected_mql"], f"empty expected_mql in {p['id']}"


def test_no_write_operators_in_references(pairs):
    # Every reference query must be read-only.
    for p in pairs:
        _check_no_writes(p["expected_mql"])  # raises ValueError on a write op


def test_complexity_counts_match_metadata(data, pairs):
    declared = data["complexity_counts"]
    for level, expected in declared.items():
        actual = sum(1 for p in pairs if p["complexity"] == level)
        assert actual == expected, f"{level}: declared {expected}, found {actual}"


def test_dev_test_split_ratio(pairs):
    n = len(pairs)
    n_test = sum(1 for p in pairs if p["split"] == "test")
    ratio = n_test / n
    # Maintain roughly a 70/30 dev/test split.
    assert 0.20 <= ratio <= 0.40, f"test ratio {ratio:.2f} outside 0.20-0.40"


def test_every_complexity_has_both_splits(pairs):
    # Test set must be representative: each complexity should appear in test.
    for level in _COMPLEXITIES:
        splits = {p["split"] for p in pairs if p["complexity"] == level}
        assert "test" in splits, f"complexity '{level}' has no test items"


def test_pipelines_are_list_of_stage_dicts(pairs):
    for p in pairs:
        mql = p["expected_mql"]
        if isinstance(mql, list):
            assert all(isinstance(stage, dict) for stage in mql), p["id"]
