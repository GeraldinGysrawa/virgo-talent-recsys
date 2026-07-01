# =============================================================
# tests/unit/test_sanchez_similarity.py
# WB-SIM-02 — SanchezSimilarity
#
# Titik keputusan kritis:
#   - Identik (label sama) → 1.0 tanpa traversal graph
#   - Label tidak ada di ontologi → 0.0
#   - URI sama → 1.0
#   - Formula: sim = 1 - log2(1 + |sym_diff| / |union|)
#   - Sibling (subsumers overlap besar) → similarity tinggi
#   - Disjoint (tidak ada overlap) → similarity rendah/0
#   - Union kosong → 0.0
#
# Dependency mock:
#   - SkillGraph (MagicMock dengan subsumers & parents terkontrol)
# =============================================================

import math
from unittest.mock import MagicMock

import pytest

from src.modules.semantic_similarity.sanchez import SanchezSimilarity
from src.modules.semantic_similarity.skill_graph import SkillNode


# ----------------------------------------------------------
# Helper
# ----------------------------------------------------------

def _node(label: str, suffix: str | None = None) -> SkillNode:
    return SkillNode(
        uri=f"http://padepokan79.com/ontology#{suffix or label}",
        label=label,
    )


def _make_sanchez(graph: MagicMock | None = None) -> SanchezSimilarity:
    return SanchezSimilarity(skill_graph=graph or MagicMock())


# ===========================================================
# Tests
# ===========================================================

class TestIdenticalLabels:
    def test_identical_label_returns_1(self):
        sanchez = _make_sanchez()
        result = sanchez.similarity("Python", "Python")
        assert result == 1.0

    def test_case_insensitive_identical_returns_1(self):
        sanchez = _make_sanchez()
        result = sanchez.similarity("python", "Python")
        assert result == 1.0

    def test_identical_skips_graph_lookup(self):
        mock_graph = MagicMock()
        sanchez = _make_sanchez(mock_graph)
        sanchez.similarity("Python", "Python")
        mock_graph.get_by_label.assert_not_called()


class TestUnknownLabels:
    def test_unknown_label_a_returns_0(self):
        mock_graph = MagicMock()
        mock_graph.get_by_label.side_effect = [None, _node("Python")]
        sanchez = _make_sanchez(mock_graph)
        result = sanchez.similarity("TidakAda", "Python")
        assert result == 0.0

    def test_unknown_label_b_returns_0(self):
        mock_graph = MagicMock()
        mock_graph.get_by_label.side_effect = [_node("Python"), None]
        sanchez = _make_sanchez(mock_graph)
        result = sanchez.similarity("Python", "TidakAda")
        assert result == 0.0

    def test_both_unknown_returns_0(self):
        mock_graph = MagicMock()
        mock_graph.get_by_label.return_value = None
        sanchez = _make_sanchez(mock_graph)
        result = sanchez.similarity("X", "Y")
        assert result == 0.0


class TestSameURI:
    def test_same_uri_via_different_labels_returns_1(self):
        """Dua label berbeda yang map ke URI sama → similarity 1.0."""
        mock_graph = MagicMock()
        node = _node("Python")
        mock_graph.get_by_label.return_value = node  # keduanya return node yang sama
        sanchez = _make_sanchez(mock_graph)
        result = sanchez.similarity("Python", "PYTHON")  # case berbeda, sama URI
        assert result == 1.0


class TestSimilarityFormula:
    def test_disjoint_subsumers_return_zero(self):
        """
        phi_a = {A, Root1}, phi_b = {B, Root2} → tidak ada overlap
        union = 4, sym_diff = 4
        disnorm = log2(1 + 4/4) = log2(2) = 1.0
        sim = 1 - 1.0 = 0.0
        """
        mock_graph = MagicMock()
        node_a = _node("A")
        node_b = _node("B")
        mock_graph.get_by_label.side_effect = [node_a, node_b]
        mock_graph.subsumers.side_effect = [
            frozenset({"uri://A", "uri://Root1"}),
            frozenset({"uri://B", "uri://Root2"}),
        ]
        sanchez = _make_sanchez(mock_graph)
        result = sanchez.similarity("A", "B")
        assert result == pytest.approx(0.0, abs=1e-6)

    def test_sibling_nodes_have_high_similarity(self):
        """
        phi_django = {Django, WebFW, Root}, phi_react = {React, WebFW, Root}
        union = 4, sym_diff = {Django, React} = 2
        disnorm = log2(1 + 2/4) = log2(1.5) ≈ 0.585
        sim ≈ 0.415
        """
        mock_graph = MagicMock()
        django = _node("Django")
        react = _node("React.js")
        mock_graph.get_by_label.side_effect = [django, react]
        mock_graph.subsumers.side_effect = [
            frozenset({"uri://Django", "uri://WebFW", "uri://Root"}),
            frozenset({"uri://React", "uri://WebFW", "uri://Root"}),
        ]
        sanchez = _make_sanchez(mock_graph)
        result = sanchez.similarity("Django", "React.js")
        expected = 1 - math.log2(1 + 2 / 4)
        assert result == pytest.approx(expected, abs=1e-6)
        assert 0.3 < result < 0.6

    def test_identical_subsumers_return_1(self):
        """
        phi_a = phi_b (identik) → sym_diff = 0
        disnorm = log2(1 + 0) = 0.0
        sim = 1.0
        """
        mock_graph = MagicMock()
        node_a = _node("A")
        node_b = _node("B", suffix="A")  # URI berbeda tapi subsumers identik
        node_b.uri = "uri://B"
        mock_graph.get_by_label.side_effect = [node_a, node_b]
        shared = frozenset({"uri://Root", "uri://Parent"})
        mock_graph.subsumers.side_effect = [shared, shared]
        sanchez = _make_sanchez(mock_graph)
        result = sanchez.similarity("A", "B")
        assert result == pytest.approx(1.0, abs=1e-6)

    def test_result_bounded_between_0_and_1(self):
        """Similarity harus selalu antara 0.0 dan 1.0."""
        mock_graph = MagicMock()
        node_a = _node("A")
        node_b = _node("B")
        mock_graph.get_by_label.side_effect = [node_a, node_b]
        mock_graph.subsumers.side_effect = [
            frozenset({f"uri://{i}" for i in range(10)}),
            frozenset({f"uri://{i}" for i in range(5, 20)}),
        ]
        sanchez = _make_sanchez(mock_graph)
        result = sanchez.similarity("A", "B")
        assert 0.0 <= result <= 1.0


class TestEmptySubsumers:
    def test_empty_union_returns_0(self):
        """Jika kedua subsumers kosong, union kosong → return 0.0."""
        mock_graph = MagicMock()
        node_a = _node("A")
        node_b = _node("B")
        mock_graph.get_by_label.side_effect = [node_a, node_b]
        mock_graph.subsumers.side_effect = [frozenset(), frozenset()]
        sanchez = _make_sanchez(mock_graph)
        result = sanchez.similarity("A", "B")
        assert result == 0.0


class TestSimilarityByURI:
    def test_same_uri_returns_1(self):
        sanchez = _make_sanchez()
        result = sanchez.similarity_by_uri("uri://Python", "uri://Python")
        assert result == 1.0

    def test_different_uri_uses_formula(self):
        mock_graph = MagicMock()
        mock_graph.subsumers.side_effect = [
            frozenset({"uri://A", "uri://Root"}),
            frozenset({"uri://B", "uri://Root"}),
        ]
        sanchez = _make_sanchez(mock_graph)
        result = sanchez.similarity_by_uri("uri://A", "uri://B")
        # union=3, sym_diff=2 → disnorm=log2(1+2/3)=log2(1.667)≈0.737 → sim≈0.263
        assert 0.0 < result < 1.0
