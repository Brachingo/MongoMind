"""
Input sanitization — clean and validate the user's natural language question
before it is incorporated into the LLM prompt.

This is a defence-in-depth measure: the question becomes part of the prompt
sent to the model, so we strip control characters, collapse whitespace and
enforce a length bound to limit prompt-injection surface and runaway inputs.
"""
import re
import unicodedata

MAX_QUESTION_LENGTH = 500
MIN_QUESTION_LENGTH = 2

# Control characters (except common whitespace) are stripped outright.
_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_WHITESPACE = re.compile(r"\s+")


def sanitize_question(question: str) -> str:
    """Return a cleaned question or raise ValueError if it is not usable.

    Steps:
      1. Reject non-string / empty input.
      2. Normalise Unicode (NFC) so look-alike characters collapse.
      3. Strip control characters and collapse runs of whitespace.
      4. Enforce min/max length bounds.

    Raises:
        ValueError: the question is empty, too short, or too long.
    """
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
