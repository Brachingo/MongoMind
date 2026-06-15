"""Collection detection.

The per-dataset keyword routing now lives in src/core/datasets.py (so several
datasets can be supported). This module keeps a thin, backwards-compatible
wrapper: callers that don't care about the dataset get the sample_mflix routing,
exactly as before.
"""
from src.core import datasets


def detect_collection(question: str, previous: str | None = None,
                      dataset: str | None = None) -> str:
    """Return the most likely MongoDB collection for the given question.

    When no keyword matches (e.g. a follow-up like "¿y solo las de 2010?"),
    reuse *previous* if it belongs to the dataset so the conversation stays on
    the same collection. Falls back to the dataset's default collection.

    *dataset* selects which keyword set to use (defaults to sample_mflix).
    """
    return datasets.detect_collection(dataset or datasets.DEFAULT_DATASET,
                                      question, previous)
