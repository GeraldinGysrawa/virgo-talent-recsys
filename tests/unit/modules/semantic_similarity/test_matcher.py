import pytest
from unittest.mock import MagicMock, patch

from src.modules.semantic_similarity.matcher import SkillMatcher
from src.modules.semantic_similarity.skill_graph import SkillNode


@pytest.fixture
def mock_graph():
    graph = MagicMock()
    # Mocking get_by_label to return valid nodes for specific skills
    def get_by_label_side_effect(label):
        valid = ["React", "Vue", "MySQL", "PostgreSQL", "TalentSkill1", "TalentSkill2"]
        if label in valid:
            return SkillNode(uri=f"http://test/{label}", label=label)
        return None
    graph.get_by_label.side_effect = get_by_label_side_effect
    return graph


@pytest.fixture
def mock_sanchez():
    sanchez = MagicMock()
    sanchez.similarity.return_value = 0.5
    return sanchez


@pytest.fixture
def mock_driver():
    driver = MagicMock()
    session = MagicMock()
    driver.session.return_value.__enter__.return_value = session
    return driver


def test_matcher_initialization(mock_driver, mock_graph, mock_sanchez):
    # Memastikan inisialisasi class menggunakan parameter yang valid
    matcher = SkillMatcher(mock_driver, mock_graph, mock_sanchez, "test_db")
    assert matcher._driver == mock_driver
    assert matcher._graph == mock_graph
    assert matcher._sanchez == mock_sanchez
    assert matcher._database == "test_db"


def test_matcher_empty_or_invalid_requirements(mock_driver, mock_graph, mock_sanchez):
    matcher = SkillMatcher(mock_driver, mock_graph, mock_sanchez)
    
    # Requirement kosong tidak diproses, kembalikan array kosong
    assert matcher.match([]) == []
    
    # Requirement yang berisi skill asing (tidak ada di graph/ontologi)
    # Semua skill "UnknownSkill" ditolak -> valid_requirements kosong -> kembalikan []
    assert matcher.match([["UnknownSkill"]]) == []


@patch.object(SkillMatcher, '_check_similarity_available', return_value=False)
@patch.object(SkillMatcher, '_fetch_talent_skills')
def test_fallback_disjunctive_logic(mock_fetch, mock_check, mock_driver, mock_graph, mock_sanchez):
    # Memastikan requirement OR disjunctive logic berfungsi (mengambil skor tertinggi)
    # Mode: fallback (computed)
    mock_fetch.return_value = {("123", "Talent A"): ["TalentSkill1"]}
    
    matcher = SkillMatcher(mock_driver, mock_graph, mock_sanchez)
    
    def sanchez_similarity(req, talent):
        if req == "React": return 0.3
        if req == "Vue": return 0.8
        return 0.0
    mock_sanchez.similarity.side_effect = sanchez_similarity
    
    # Disjunctive requirement: ["React", "Vue"] is one group -> OR logic
    reqs = [["React", "Vue"]]
    results = matcher.match(reqs)
    
    assert len(results) == 1
    # Expect best score from the group, which is 0.8 (Vue)
    assert results[0].skill_score == 0.8
    assert results[0].match_details[0].best_match_skill == "TalentSkill1"
    assert results[0].match_details[0].source == "computed"


@patch.object(SkillMatcher, '_check_similarity_available', return_value=False)
@patch.object(SkillMatcher, '_fetch_talent_skills')
def test_fallback_and_average_logic(mock_fetch, mock_check, mock_driver, mock_graph, mock_sanchez):
    # Memastikan perhitungan rata-rata antar grup berjalan benar.
    # Mode: fallback (computed)
    mock_fetch.return_value = {("123", "Talent A"): ["TalentSkill1"]}
    
    matcher = SkillMatcher(mock_driver, mock_graph, mock_sanchez)
    
    def sanchez_similarity(req, talent):
        if req == "React": return 1.0       # Perfect match for React
        if req == "MySQL": return 0.2       # Low match
        if req == "PostgreSQL": return 0.4  # Better match for DB
        return 0.0
    mock_sanchez.similarity.side_effect = sanchez_similarity
    
    # 2 Grup: ["React"] AND ["MySQL" OR "PostgreSQL"]
    reqs = [["React"], ["MySQL", "PostgreSQL"]]
    results = matcher.match(reqs)
    
    assert len(results) == 1
    # Group 1 best: 1.0 (React)
    # Group 2 best: 0.4 (PostgreSQL)
    # Average: (1.0 + 0.4) / 2 = 0.7
    assert results[0].skill_score == 0.7


@patch.object(SkillMatcher, '_check_similarity_available', return_value=True)
@patch.object(SkillMatcher, '_fetch_talent_skills')
def test_neo4j_mode(mock_fetch, mock_check, mock_driver, mock_graph, mock_sanchez):
    # Memastikan mode Neo4j berjalan jika relasi SKILL_SIMILARITY tersedia
    mock_fetch.return_value = {("123", "Talent A"): ["TalentSkill1"]}
    
    session = mock_driver.session.return_value.__enter__.return_value
    def session_run_side_effect(query, params=None):
        if "UNWIND $req_uris" in query:
            # Mengembalikan mock relasi seolah dari Neo4j
            return [
                {"req_uri": "http://test/React", "talent_uri": "http://test/TalentSkill1", "score": 0.9}
            ]
        return []
    session.run.side_effect = session_run_side_effect
    
    matcher = SkillMatcher(mock_driver, mock_graph, mock_sanchez)
    reqs = [["React"]]
    
    results = matcher.match(reqs)
    
    assert len(results) == 1
    assert results[0].skill_score == 0.9
    assert results[0].match_details[0].source == "neo4j"


@patch.object(SkillMatcher, '_check_similarity_available', return_value=False)
@patch.object(SkillMatcher, '_fetch_talent_skills')
def test_talent_without_skills(mock_fetch, mock_check, mock_driver, mock_graph, mock_sanchez):
    # Talent tidak punya skill (list kosong) kembalikan skor aman 0.0
    mock_fetch.return_value = {("123", "Talent Empty"): []}
    
    matcher = SkillMatcher(mock_driver, mock_graph, mock_sanchez)
    reqs = [["React"]]
    
    results = matcher.match(reqs)
    
    assert len(results) == 1
    assert results[0].skill_score == 0.0
