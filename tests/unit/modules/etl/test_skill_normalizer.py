import pytest
from unittest.mock import patch

from src.modules.etl.skill_normalizer import SkillNormalizer


@pytest.fixture
def mock_ontology_labels():
    return [
        "React.js",
        "Vue.js",
        ".NET Ecosystem",
        "AI & Machine Learning",
        "PostgreSQL",
        "MySQL"
    ]


def test_exact_match(mock_ontology_labels):
    normalizer = SkillNormalizer(ontology_labels=mock_ontology_labels)
    
    # Exact match case insensitive
    result = normalizer.normalize("react.js")
    assert result.canonical == "React.js"
    assert result.method == "exact"
    assert result.confidence == 1.0


def test_alias_match(mock_ontology_labels):
    normalizer = SkillNormalizer(ontology_labels=mock_ontology_labels)
    
    # Alias dari _ALIAS_MAP (dotnet -> .NET Ecosystem)
    result = normalizer.normalize("dotnet")
    assert result.canonical == ".NET Ecosystem"
    assert result.method == "alias"
    assert result.confidence == 1.0


def test_separator_logic(mock_ontology_labels):
    normalizer = SkillNormalizer(ontology_labels=mock_ontology_labels)
    
    # "AI & Machine Learning" akan diekstrak otomatis menjadi "ai" dan "machine learning"
    # Sehingga jika inputnya "ai", akan nge-match ke alias buatan
    result = normalizer.normalize("ai")
    assert result.canonical == "AI & Machine Learning"
    assert result.method == "alias"


def test_fuzzy_match(mock_ontology_labels):
    normalizer = SkillNormalizer(ontology_labels=mock_ontology_labels, fuzzy_threshold=70)
    
    # Typo yang tidak ada di alias map tapi masuk threshold
    result = normalizer.normalize("Reect.js") 
    assert result.canonical == "React.js"
    assert "fuzzy" in result.method


def test_not_found(mock_ontology_labels):
    normalizer = SkillNormalizer(ontology_labels=mock_ontology_labels)
    
    result = normalizer.normalize("Sesuatu Yang Asing")
    assert result.canonical is None
    assert result.method == "not_found"


def test_batch_normalize_and_get_canonical(mock_ontology_labels):
    normalizer = SkillNormalizer(ontology_labels=mock_ontology_labels)
    
    raw = ["react.js", "dotnet", "asing"]
    
    batch_res = normalizer.normalize_batch(raw)
    assert len(batch_res) == 3
    assert batch_res[0].canonical == "React.js"
    assert batch_res[1].canonical == ".NET Ecosystem"
    assert batch_res[2].canonical is None
    
    canonical_res = normalizer.get_canonical_labels(raw)
    assert len(canonical_res) == 2
    assert "React.js" in canonical_res
    assert ".NET Ecosystem" in canonical_res


def test_fuzzy_not_available(mock_ontology_labels):
    # Buat instance baru dan matikan manual rapidfuzz
    normalizer = SkillNormalizer(ontology_labels=mock_ontology_labels)
    normalizer._fuzzy_available = False # ensure fallback mode
    
    # Typo yang harusnya fuzzy tapi karena off jadi not_found
    result = normalizer.normalize("Reect.js")
    assert result.canonical is None
    assert result.method == "not_found"
