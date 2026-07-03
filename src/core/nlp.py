"""Detección de colección.

El enrutado por keywords (por dataset) vive ahora en src/core/datasets.py.
Aquí dejo solo un envoltorio fino para no romper compatibilidad: quien no se
preocupe por el dataset sigue obteniendo el enrutado de sample_mflix de siempre.
"""
from src.core import datasets


def detect_collection(question: str, previous: str | None = None,
                      dataset: str | None = None) -> str:

    return datasets.detect_collection(dataset or datasets.DEFAULT_DATASET,
                                      question, previous)
