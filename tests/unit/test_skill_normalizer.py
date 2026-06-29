# =============================================================
# tests/unit/test_skill_normalizer.py
# WB-ETL-03 — SkillNormalizer
#
# Titik keputusan kritis:
#   - Lapisan 0 (exact): label persis sesuai ontologi → method="exact"
#   - Lapisan 1 (alias): variasi penulisan umum → method="alias"
#   - Lapisan 2 (fuzzy): jika rapidfuzz tersedia → method=f"fuzzy:{score}"
#   - not_found: tidak ada match → canonical=None, method="not_found"
#   - normalize_batch: mengembalikan hasil untuk semua label
#   - get_canonical_labels: membuang label not_found
# =============================================================

import pytest

from src.modules.etl.skill_normalizer import SkillNormalizer, NormalizeResult

# Label ontologi yang digunakan di seluruh test
ONTOLOGY_LABELS = [
    "Python",
    "JavaScript",
    "React.js",
    "Node.js",
    "PostgreSQL",
    "Go",
    "Docker",
    "Kubernetes",
    "AI & Machine Learning",
    "TypeScript",
]


@pytest.fixture
def normalizer() -> SkillNormalizer:
    return SkillNormalizer(ontology_labels=ONTOLOGY_LABELS)


# ===========================================================
# Tests
# ===========================================================

class TestExactMatch:
    def test_exact_match_same_case(self, normalizer):
        result = normalizer.normalize("Python")
        assert result.canonical == "Python"
        assert result.method == "exact"
        assert result.confidence == 1.0

    def test_exact_match_upper_case(self, normalizer):
        result = normalizer.normalize("PYTHON")
        assert result.canonical == "Python"
        assert result.method == "exact"

    def test_exact_match_lower_case(self, normalizer):
        result = normalizer.normalize("javascript")
        assert result.canonical == "JavaScript"
        assert result.method == "exact"

    def test_exact_match_with_leading_trailing_spaces(self, normalizer):
        result = normalizer.normalize("  Python  ")
        assert result.canonical == "Python"
        assert result.method == "exact"


class TestAliasMatch:
    def test_react_alias(self, normalizer):
        result = normalizer.normalize("react")
        assert result.canonical == "React.js"
        assert result.method == "alias"

    def test_reactjs_alias(self, normalizer):
        result = normalizer.normalize("reactjs")
        assert result.canonical == "React.js"
        assert result.method == "alias"

    def test_react_js_with_space(self, normalizer):
        result = normalizer.normalize("react js")
        assert result.canonical == "React.js"
        assert result.method == "alias"

    def test_golang_alias(self):
        # "go" dan "golang" di alias map → "Go"
        n = SkillNormalizer(ontology_labels=ONTOLOGY_LABELS + ["Go"])
        result = n.normalize("golang")
        assert result.canonical == "Go"
        assert result.method == "alias"

    def test_node_js_alias(self, normalizer):
        result = normalizer.normalize("node js")
        assert result.canonical == "Node.js"
        assert result.method == "alias"

    def test_postgres_alias(self, normalizer):
        result = normalizer.normalize("postgres")
        assert result.canonical == "PostgreSQL"
        assert result.method == "alias"

    def test_ts_alias_for_typescript(self, normalizer):
        result = normalizer.normalize("ts")
        assert result.canonical == "TypeScript"
        assert result.method == "alias"

    def test_alias_confidence_is_1(self, normalizer):
        result = normalizer.normalize("react")
        assert result.confidence == 1.0


class TestNotFound:
    def test_completely_unknown_skill(self, normalizer):
        result = normalizer.normalize("XYZNonExistentSkillABC12345")
        assert result.canonical is None
        assert result.method == "not_found"
        assert result.confidence == 0.0

    def test_not_found_original_preserved(self, normalizer):
        result = normalizer.normalize("WeirdSkill999")
        assert result.original == "WeirdSkill999"


class TestNormalizeBatch:
    def test_returns_result_for_all_inputs(self, normalizer):
        labels = ["Python", "react", "XYZUnknown"]
        results = normalizer.normalize_batch(labels)
        assert len(results) == 3

    def test_batch_preserves_order(self, normalizer):
        labels = ["Python", "react", "XYZUnknown"]
        results = normalizer.normalize_batch(labels)
        assert results[0].canonical == "Python"
        assert results[1].canonical == "React.js"
        assert results[2].canonical is None

    def test_empty_batch_returns_empty(self, normalizer):
        assert normalizer.normalize_batch([]) == []

    def test_batch_includes_not_found(self, normalizer):
        results = normalizer.normalize_batch(["Python", "Cobol99XYZ"])
        not_found = [r for r in results if r.method == "not_found"]
        assert len(not_found) == 1


class TestGetCanonicalLabels:
    def test_filters_out_not_found(self, normalizer):
        canonical = normalizer.get_canonical_labels(["Python", "UnknownXYZ", "react"])
        assert None not in canonical
        assert "Python" in canonical
        assert "React.js" in canonical
        assert "UnknownXYZ" not in canonical

    def test_empty_input_returns_empty(self, normalizer):
        assert normalizer.get_canonical_labels([]) == []

    def test_all_valid_returns_all(self, normalizer):
        canonical = normalizer.get_canonical_labels(["Python", "react"])
        assert len(canonical) == 2


class TestNormalizeResultDataclass:
    def test_normalize_result_has_original(self, normalizer):
        result = normalizer.normalize("Python")
        assert result.original == "Python"

    def test_normalize_result_is_normalize_result_type(self, normalizer):
        result = normalizer.normalize("Python")
        assert isinstance(result, NormalizeResult)
