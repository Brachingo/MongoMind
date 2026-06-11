"""Unit tests for collection detection, including conversational context."""
import sys
sys.path.insert(0, ".")
from src.core.nlp import detect_collection


class TestKeywordDetection:
    def test_movies_default(self):
        assert detect_collection("algo sin palabras clave") == "movies"

    def test_detects_movies(self):
        assert detect_collection("películas de Nolan") == "movies"

    def test_detects_comments(self):
        assert detect_collection("muéstrame los comentarios recientes") == "comments"

    def test_detects_theaters(self):
        assert detect_collection("¿cuántos cines hay en Nueva York?") == "theaters"

    def test_detects_users(self):
        assert detect_collection("lista de usuarios registrados") == "users"


class TestConversationalContext:
    def test_follow_up_reuses_previous(self):
        # No keyword in the follow-up -> stay on the previous collection.
        assert detect_collection("¿y solo las de 2010?", previous="comments") == "comments"

    def test_keyword_overrides_previous(self):
        # Explicit keyword wins over the previous collection.
        assert detect_collection("ahora los comentarios", previous="movies") == "comments"

    def test_no_previous_falls_back_to_default(self):
        assert detect_collection("ordénalos por fecha", previous=None) == "movies"
