"""Detección de colección.

El enrutado por keywords (por dataset) vive ahora en src/core/datasets.py.
Aquí dejo solo un envoltorio fino para no romper compatibilidad: quien no se
preocupe por el dataset sigue obteniendo el enrutado de sample_mflix de siempre.
"""
from src.core import datasets


def detect_collection(question: str, previous: str | None = None,
                      dataset: str | None = None) -> str:
    """Devuelve la colección más probable para la pregunta.

    Si ninguna keyword encaja (típico en un follow-up tipo "¿y solo las de
    2010?"), reutiliza *previous* si pertenece al dataset, para que la
    conversación no cambie de colección. Si no, usa la colección por defecto.
    *dataset* elige el conjunto de keywords (por defecto sample_mflix).
    """
    return datasets.detect_collection(dataset or datasets.DEFAULT_DATASET,
                                      question, previous)
