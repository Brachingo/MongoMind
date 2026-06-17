"""Tests de la sanitización de entrada — sin dependencias externas."""
import sys
sys.path.insert(0, ".")
import pytest
from src.core.sanitizer import sanitize_question, MAX_QUESTION_LENGTH


class TestValid:
    def test_plain_question_unchanged(self):
        assert sanitize_question("Películas de Nolan") == "Películas de Nolan"

    def test_collapses_whitespace(self):
        assert sanitize_question("  hola    mundo  ") == "hola mundo"

    def test_strips_newlines_and_tabs(self):
        assert sanitize_question("línea1\n\tlínea2") == "línea1 línea2"

    def test_strips_control_characters(self):
        assert sanitize_question("abc\x00\x07def") == "abcdef"

    def test_accepts_max_length(self):
        q = "a" * MAX_QUESTION_LENGTH
        assert sanitize_question(q) == q


class TestInvalid:
    def test_empty_raises(self):
        with pytest.raises(ValueError):
            sanitize_question("")

    def test_whitespace_only_raises(self):
        with pytest.raises(ValueError):
            sanitize_question("    \n\t  ")

    def test_single_char_raises(self):
        with pytest.raises(ValueError):
            sanitize_question("a")

    def test_too_long_raises(self):
        with pytest.raises(ValueError, match="larga"):
            sanitize_question("a" * (MAX_QUESTION_LENGTH + 1))

    def test_non_string_raises(self):
        with pytest.raises(ValueError):
            sanitize_question(12345)  # type: ignore[arg-type]
