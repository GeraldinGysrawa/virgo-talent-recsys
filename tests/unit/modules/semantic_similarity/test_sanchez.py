import math
import pytest
from unittest.mock import MagicMock

from src.modules.semantic_similarity.sanchez import SanchezSimilarity
from src.modules.semantic_similarity.skill_graph import SkillNode


@pytest.fixture
def mock_graph():
    graph = MagicMock()
    
    # Mocking get_by_label
    def get_by_label_side_effect(label):
        label_lower = label.lower()
        if label_lower == "react":
            return SkillNode(uri="http://example.com/React", label="React")
        elif label_lower == "vue":
            return SkillNode(uri="http://example.com/Vue", label="Vue")
        elif label_lower == "angular":
            return SkillNode(uri="http://example.com/Angular", label="Angular")
        return None
        
    graph.get_by_label.side_effect = get_by_label_side_effect
    
    # Mocking subsumers
    def subsumers_side_effect(uri):
        if uri == "http://example.com/React":
            return frozenset(["http://example.com/React", "http://example.com/Frontend", "http://example.com/IT"])
        elif uri == "http://example.com/Vue":
            return frozenset(["http://example.com/Vue", "http://example.com/Frontend", "http://example.com/IT"])
        elif uri == "http://example.com/Angular":
            return frozenset(["http://example.com/Angular", "http://example.com/Other"])
        elif uri == "http://example.com/Empty":
            return frozenset()
        return frozenset()
        
    graph.subsumers.side_effect = subsumers_side_effect
    return graph


@pytest.fixture
def sanchez(mock_graph):
    return SanchezSimilarity(mock_graph)


def test_similarity_identical_labels(sanchez):
    # similarity antara skill yang sama menghasilkan skor 1.0 (meskipun beda case)
    assert sanchez.similarity("React", "react") == 1.0
    assert sanchez.similarity("Vue", "Vue") == 1.0


def test_similarity_missing_label(sanchez):
    # similarity jika salah satu skill tidak ditemukan menghasilkan skor 0.0
    assert sanchez.similarity("React", "UnknownSkill") == 0.0
    assert sanchez.similarity("UnknownSkill", "React") == 0.0
    assert sanchez.similarity("Unknown1", "Unknown2") == 0.0


def test_similarity_partial_overlap(sanchez):
    # similarity untuk dua skill yang memiliki sebagian subsumer/ancestor yang sama
    # React: {React, Frontend, IT}
    # Vue: {Vue, Frontend, IT}
    # Union: {React, Vue, Frontend, IT} -> len = 4
    # Sym Diff: {React, Vue} -> len = 2
    # disnorm = log2(1 + 2/4) = log2(1.5) = 0.5849625...
    # sim = 1 - 0.5849625 = 0.4150375...
    sim = sanchez.similarity("React", "Vue")
    assert 0.0 < sim < 1.0
    
    expected_sim = 1 - math.log2(1 + 2/4)
    assert math.isclose(sim, expected_sim)


def test_similarity_by_uri_direct(sanchez):
    # similarity_by_uri() menghasilkan skor sesuai data subsumer mock
    sim = sanchez.similarity_by_uri("http://example.com/React", "http://example.com/Angular")
    # React: {React, Frontend, IT} -> len 3
    # Angular: {Angular, Other} -> len 2
    # Union: 5
    # Sym Diff: 5
    # disnorm = log2(1 + 5/5) = log2(2) = 1.0
    # sim = 1 - 1.0 = 0.0
    assert math.isclose(sim, 0.0)
    
    # Identical URI
    assert sanchez.similarity_by_uri("http://example.com/React", "http://example.com/React") == 1.0


def test_similarity_empty_subsumers(sanchez):
    # edge case jika subsumer kosong (union kosong), kembalikan 0.0
    sim = sanchez.similarity_by_uri("http://example.com/Empty", "http://example.com/React")
    assert sim == 0.0
    
    sim2 = sanchez.similarity_by_uri("http://example.com/Empty", "http://example.com/Empty")
    # Karena uri sama, function similarity_by_uri akan langsung bypass return 1.0 di awal
    assert sim2 == 1.0
