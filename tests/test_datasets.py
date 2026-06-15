"""Unit tests for the dataset registry and per-dataset collection routing."""
import sys
sys.path.insert(0, ".")
from src.core import datasets


class TestRegistry:
    def test_default_is_mflix(self):
        assert datasets.DEFAULT_DATASET == "sample_mflix"

    def test_known_datasets_present(self):
        keys = datasets.dataset_keys()
        assert {"sample_mflix", "sample_airbnb", "sample_analytics"} <= set(keys)

    def test_resolve_unknown_falls_back(self):
        assert datasets.resolve("no_existe") == "sample_mflix"
        assert datasets.resolve(None) == "sample_mflix"

    def test_resolve_keeps_valid(self):
        assert datasets.resolve("sample_airbnb") == "sample_airbnb"

    def test_database_for(self):
        assert datasets.database_for("sample_analytics") == "sample_analytics"

    def test_options_shape(self):
        opts = datasets.options()
        assert all("key" in o and "label" in o for o in opts)
        assert {o["key"] for o in opts} == set(datasets.dataset_keys())


class TestRouting:
    def test_mflix_keyword(self):
        assert datasets.detect_collection("sample_mflix", "películas de Nolan") == "movies"

    def test_airbnb_single_collection(self):
        assert datasets.detect_collection("sample_airbnb", "alojamientos baratos") \
            == "listingsAndReviews"

    def test_analytics_transactions(self):
        assert datasets.detect_collection("sample_analytics", "compras de acciones") \
            == "transactions"

    def test_analytics_customers(self):
        assert datasets.detect_collection("sample_analytics", "lista de clientes") \
            == "customers"

    def test_analytics_accounts(self):
        assert datasets.detect_collection("sample_analytics", "cuentas con mayor límite") \
            == "accounts"

    def test_follow_up_reuses_previous_within_dataset(self):
        # No keyword -> stay on previous collection of the same dataset.
        assert datasets.detect_collection("sample_analytics", "¿y las mayores?",
                                          previous="accounts") == "accounts"

    def test_follow_up_default_when_previous_foreign(self):
        # 'movies' is not a collection of analytics -> fall back to its default.
        assert datasets.detect_collection("sample_analytics", "ordénalas",
                                          previous="movies") == "transactions"

    def test_unknown_dataset_routes_via_default(self):
        # resolve() makes an unknown dataset behave like mflix.
        assert datasets.detect_collection("no_existe", "películas de Nolan") == "movies"
