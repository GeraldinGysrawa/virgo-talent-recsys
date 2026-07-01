# =============================================================
# tests/unit/test_skill_matcher.py
# WB-SIM-01 — SkillMatcher
#
# Titik keputusan kritis:
#   - match([]) → [] tanpa memanggil Neo4j
#   - Skill tidak ada di ontologi → di-skip dari requirement
#   - Semua skill tidak valid → return []
#   - Fallback mode (SKILL_SIMILARITY = 0): skor dihitung via SanchezSimilarity
#   - Best Match Average dihitung benar untuk multi-requirement
#
# Dependency mock:
#   - Neo4j driver (MagicMock) — tidak ada HTTP/Bolt call nyata
#   - SkillGraph (MagicMock)
#   - SanchezSimilarity (MagicMock)
# =============================================================

from unittest.mock import MagicMock

import pytest

from src.modules.semantic_similarity.matcher import SkillMatcher
from src.modules.semantic_similarity.skill_graph import SkillNode


# ----------------------------------------------------------
# Helper
# ----------------------------------------------------------

def _node(label: str, uri: str | None = None) -> SkillNode:
    return SkillNode(uri=uri or f"http://padepokan79.com/ontology#{label}", label=label)


def _make_matcher(
    graph: MagicMock | None = None,
    sanchez: MagicMock | None = None,
    driver: MagicMock | None = None,
) -> SkillMatcher:
    return SkillMatcher(
        driver=driver or MagicMock(),
        skill_graph=graph or MagicMock(),
        sanchez=sanchez or MagicMock(),
    )


def _setup_fallback_session(mock_driver: MagicMock, talents: list[dict]) -> MagicMock:
    """
    Setup mock session untuk dua panggilan:
      1. _check_similarity_available → total=0 (fallback mode)
      2. _fetch_talent_skills → daftar record talenta
    """
    mock_session = MagicMock()

    # Panggilan pertama: cek SKILL_SIMILARITY
    mock_count = MagicMock()
    mock_count.single.return_value = {"total": 0}

    # Panggilan kedua: ambil data talent
    class FakeRecord:
        def __init__(self, d):
            self._d = d
        def __getitem__(self, k):
            return self._d[k]

    fake_records = [FakeRecord(t) for t in talents]
    mock_session.run.side_effect = [mock_count, fake_records]

    mock_driver.session.return_value.__enter__ = MagicMock(return_value=mock_session)
    mock_driver.session.return_value.__exit__ = MagicMock(return_value=False)

    return mock_session


# ===========================================================
# Tests
# ===========================================================

class TestMatchEmptyRequirements:
    def test_empty_requirements_returns_empty_list(self):
        matcher = _make_matcher()
        result, _ = matcher.match([])
        assert result == []

    def test_empty_requirements_does_not_call_driver(self):
        mock_driver = MagicMock()
        matcher = _make_matcher(driver=mock_driver)
        matcher.match([])
        mock_driver.session.assert_not_called()


class TestMatchSkillNotInGraph:
    def test_unknown_skill_yields_no_valid_requirements(self):
        """Skill yang tidak ada di ontologi → semua requirement terhapus → []."""
        mock_graph = MagicMock()
        mock_graph.get_by_label.return_value = None  # tidak ditemukan

        mock_driver = MagicMock()
        mock_session = MagicMock()
        mock_count = MagicMock()
        mock_count.single.return_value = {"total": 0}
        mock_session.run.return_value = mock_count
        mock_driver.session.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_driver.session.return_value.__exit__ = MagicMock(return_value=False)

        matcher = _make_matcher(graph=mock_graph, driver=mock_driver)
        result, _ = matcher.match([["SkillTidakAda"]])
        assert result == []

    def test_partial_valid_skills_filters_only_unknown(self):
        """Jika grup [A, B] dan hanya A dikenal, B di-drop tapi A tetap."""
        mock_graph = MagicMock()
        python_node = _node("Python")
        # A=Python dikenal, B=SkillAcak tidak dikenal
        mock_graph.get_by_label.side_effect = lambda label: (
            python_node if label == "Python" else None
        )

        mock_driver = MagicMock()
        _setup_fallback_session(mock_driver, [
            {"nip": "001", "nama": "Andi", "skills": ["Python"]}
        ])

        mock_sanchez = MagicMock()
        mock_sanchez.similarity.return_value = 1.0

        matcher = _make_matcher(graph=mock_graph, sanchez=mock_sanchez, driver=mock_driver)
        result, _ = matcher.match([["Python", "SkillAcak"]])

        # Harus ada hasil (Python valid)
        assert len(result) == 1
        assert result[0].skill_score == pytest.approx(1.0)


class TestMatchFallbackMode:
    def test_fallback_uses_sanchez_similarity(self):
        """Ketika SKILL_SIMILARITY=0, skor dihitung via SanchezSimilarity."""
        mock_graph = MagicMock()
        python_node = _node("Python")
        mock_graph.get_by_label.return_value = python_node

        mock_driver = MagicMock()
        _setup_fallback_session(mock_driver, [
            {"nip": "001", "nama": "Andi", "skills": ["Python"]}
        ])

        mock_sanchez = MagicMock()
        mock_sanchez.similarity.return_value = 0.9

        matcher = _make_matcher(graph=mock_graph, sanchez=mock_sanchez, driver=mock_driver)
        result, _ = matcher.match([["Python"]])

        assert len(result) == 1
        assert result[0].skill_score == pytest.approx(0.9)
        mock_sanchez.similarity.assert_called()

    def test_fallback_best_match_average_multi_requirement(self):
        """
        Dua requirement [Python] dan [React.js]:
        - Python vs Python → 1.0
        - React.js vs Python → 0.3
        BMA = (1.0 + 0.3) / 2 = 0.65
        """
        mock_graph = MagicMock()
        python_node = _node("Python")
        react_node = _node("React.js")

        def get_by_label(label):
            return {"Python": python_node, "React.js": react_node}.get(label)

        mock_graph.get_by_label.side_effect = get_by_label

        mock_driver = MagicMock()
        _setup_fallback_session(mock_driver, [
            {"nip": "001", "nama": "Andi", "skills": ["Python"]}
        ])

        mock_sanchez = MagicMock()
        # Python vs Python = 1.0; React.js vs Python = 0.3
        def sim_side_effect(req, talent):
            if req == "Python" and talent == "Python":
                return 1.0
            if req == "React.js" and talent == "Python":
                return 0.3
            return 0.0

        mock_sanchez.similarity.side_effect = sim_side_effect

        matcher = _make_matcher(graph=mock_graph, sanchez=mock_sanchez, driver=mock_driver)
        result, _ = matcher.match([["Python"], ["React.js"]])

        assert len(result) == 1
        assert result[0].skill_score == pytest.approx(0.65, abs=0.01)

    def test_fallback_talent_without_skills_gets_zero(self):
        """Talenta tanpa skills harus mendapat skor 0.0."""
        mock_graph = MagicMock()
        python_node = _node("Python")
        mock_graph.get_by_label.return_value = python_node

        mock_driver = MagicMock()
        _setup_fallback_session(mock_driver, [
            {"nip": "001", "nama": "Andi", "skills": []}
        ])

        matcher = _make_matcher(graph=mock_graph, driver=mock_driver)
        result, _ = matcher.match([["Python"]])

        assert len(result) == 1
        assert result[0].skill_score == pytest.approx(0.0)

    def test_results_sorted_descending_by_score(self):
        """Hasil harus diurutkan descending berdasarkan skill_score."""
        mock_graph = MagicMock()
        python_node = _node("Python")
        mock_graph.get_by_label.return_value = python_node

        mock_driver = MagicMock()
        _setup_fallback_session(mock_driver, [
            {"nip": "001", "nama": "Andi", "skills": ["Python"]},
            {"nip": "002", "nama": "Budi", "skills": []},
        ])

        mock_sanchez = MagicMock()
        mock_sanchez.similarity.return_value = 0.8

        matcher = _make_matcher(graph=mock_graph, sanchez=mock_sanchez, driver=mock_driver)
        result, _ = matcher.match([["Python"]])

        assert result[0].skill_score >= result[1].skill_score


def _setup_neo4j_session(mock_driver: MagicMock, talents: list[dict], similarity_records: list[dict]) -> MagicMock:
    """
    Setup mock session untuk tiga panggilan:
      1. _check_similarity_available → total=5 (Neo4j mode aktif)
      2. _fetch_talent_skills → daftar record talenta
      3. Query matrix similarity (UNWIND)
    """
    mock_session = MagicMock()

    # Panggilan 1: _check_similarity_available
    mock_count = MagicMock()
    mock_count.single.return_value = {"total": 5}

    # Panggilan 2: _fetch_talent_skills
    class FakeRecordTalents:
        def __init__(self, d):
            self._d = d
        def __getitem__(self, k):
            return self._d[k]
    fake_talents = [FakeRecordTalents(t) for t in talents]

    # Panggilan 3: Query matrix similarity
    class FakeRecordSim:
        def __init__(self, d):
            self._d = d
        def __getitem__(self, k):
            return self._d[k]
    fake_sims = [FakeRecordSim(s) for s in similarity_records]

    mock_session.run.side_effect = [mock_count, fake_talents, fake_sims]

    mock_driver.session.return_value.__enter__ = MagicMock(return_value=mock_session)
    mock_driver.session.return_value.__exit__ = MagicMock(return_value=False)

    return mock_session


class TestMatchNeo4jMode:
    def test_neo4j_mode_returns_scores_from_database(self):
        """Memastikan skor dihitung dari data r.score di database Neo4j."""
        mock_graph = MagicMock()
        python_node = _node("Python")
        django_node = _node("Django")
        
        def get_by_label(label):
            return {"Python": python_node, "Django": django_node}.get(label)
        mock_graph.get_by_label.side_effect = get_by_label

        mock_driver = MagicMock()
        _setup_neo4j_session(
            mock_driver,
            talents=[{"nip": "001", "nama": "Andi", "skills": ["Django"]}],
            similarity_records=[{
                "req_uri": "http://padepokan79.com/ontology#Python",
                "talent_uri": "http://padepokan79.com/ontology#Django",
                "score": 0.75
            }]
        )

        matcher = _make_matcher(graph=mock_graph, driver=mock_driver)
        result, _ = matcher.match([["Python"]])

        assert len(result) == 1
        assert result[0].nip == "001"
        assert result[0].skill_score == pytest.approx(0.75)
        assert result[0].match_details[0].source == "neo4j"

    def test_neo4j_mode_exact_match_returns_one(self):
        """Skor kemiripan skill identik secara URI harus bernilai 1.0."""
        mock_graph = MagicMock()
        python_node = _node("Python")
        mock_graph.get_by_label.return_value = python_node

        mock_driver = MagicMock()
        _setup_neo4j_session(
            mock_driver,
            talents=[{"nip": "001", "nama": "Andi", "skills": ["Python"]}],
            similarity_records=[{
                "req_uri": "http://padepokan79.com/ontology#Python",
                "talent_uri": "http://padepokan79.com/ontology#Python",
                "score": 1.0
            }]
        )

        matcher = _make_matcher(graph=mock_graph, driver=mock_driver)
        result, _ = matcher.match([["Python"]])

        assert result[0].skill_score == pytest.approx(1.0)

    def test_neo4j_mode_disjunctive_requirements(self):
        """Uji OR logic dalam grup: ambil alternatif dengan skor tertinggi."""
        mock_graph = MagicMock()
        python_node = _node("Python")
        django_node = _node("Django")
        react_node = _node("React.js")
        
        def get_by_label(label):
            return {
                "Python": python_node,
                "Django": django_node,
                "React.js": react_node
            }.get(label)
        mock_graph.get_by_label.side_effect = get_by_label

        mock_driver = MagicMock()
        _setup_neo4j_session(
            mock_driver,
            talents=[{"nip": "001", "nama": "Andi", "skills": ["Django"]}],
            similarity_records=[
                {
                    "req_uri": "http://padepokan79.com/ontology#Python",
                    "talent_uri": "http://padepokan79.com/ontology#Django",
                    "score": 0.4
                },
                {
                    "req_uri": "http://padepokan79.com/ontology#React.js",
                    "talent_uri": "http://padepokan79.com/ontology#Django",
                    "score": 0.8
                }
            ]
        )

        matcher = _make_matcher(graph=mock_graph, driver=mock_driver)
        # Kebutuhan OR: Python atau React.js (harus mengambil skor 0.8)
        result, _ = matcher.match([["Python", "React.js"]])

        assert result[0].skill_score == pytest.approx(0.8)

    def test_neo4j_mode_talent_without_skills_returns_zero(self):
        """Talenta tanpa skill mendapatkan skor kemiripan 0.0."""
        mock_graph = MagicMock()
        python_node = _node("Python")
        mock_graph.get_by_label.return_value = python_node

        mock_driver = MagicMock()
        # setup dengan count > 0 tapi list talent skills kosong
        _setup_neo4j_session(
            mock_driver,
            talents=[{"nip": "001", "nama": "Andi", "skills": []}],
            similarity_records=[]
        )

        matcher = _make_matcher(graph=mock_graph, driver=mock_driver)
        result, _ = matcher.match([["Python"]])

        assert result[0].skill_score == pytest.approx(0.0)

    def test_neo4j_mode_talent_unmapped_skills_returns_zero(self):
        """Talenta dengan skill yang tidak terdaftar di graf ontologi mendapat skor 0.0."""
        mock_graph = MagicMock()
        python_node = _node("Python")
        # get_by_label mengembalikan None untuk skill talenta ("Cobol")
        def get_by_label(label):
            return python_node if label == "Python" else None
        mock_graph.get_by_label.side_effect = get_by_label

        mock_driver = MagicMock()
        _setup_neo4j_session(
            mock_driver,
            talents=[{"nip": "001", "nama": "Andi", "skills": ["Cobol"]}],
            similarity_records=[]
        )

        matcher = _make_matcher(graph=mock_graph, driver=mock_driver)
        result, _ = matcher.match([["Python"]])

        assert result[0].skill_score == pytest.approx(0.0)
