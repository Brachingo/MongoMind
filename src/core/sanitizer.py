"""
Sanitización de entrada: limpia y valida la pregunta del usuario antes de
meterla en el prompt del LLM.

Es una medida de defensa en profundidad: como la pregunta acaba dentro del
prompt, quito caracteres de control, colapso espacios y acoto la longitud para
reducir la superficie de inyección de prompts y los inputs desbocados.
"""
import re
import unicodedata

MAX_QUESTION_LENGTH = 500
MIN_QUESTION_LENGTH = 2

# Los caracteres de control (salvo los espacios habituales) se eliminan sin más.
_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_WHITESPACE = re.compile(r"\s+")


def sanitize_question(question: str) -> str:
    
    if not isinstance(question, str):
        raise ValueError("La pregunta debe ser texto.")

    text = unicodedata.normalize("NFC", question)
    text = _CONTROL_CHARS.sub("", text)
    text = _WHITESPACE.sub(" ", text).strip()

    if not text:
        raise ValueError("La pregunta está vacía.")
    if len(text) < MIN_QUESTION_LENGTH:
        raise ValueError("La pregunta es demasiado corta.")
    if len(text) > MAX_QUESTION_LENGTH:
        raise ValueError(
            f"La pregunta es demasiado larga (máximo {MAX_QUESTION_LENGTH} caracteres)."
        )

    return text
