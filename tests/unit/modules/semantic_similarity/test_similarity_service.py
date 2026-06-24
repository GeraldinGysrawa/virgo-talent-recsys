import pytest
from unittest.mock import MagicMock, patch

from src.modules.semantic_similarity.similarity_service import SemanticSimilarityService


def test_service_uninitialized_state():
    driver = MagicMock()
    service = SemanticSimilarityService(driver)
    
    # rank_talents() sebelum initialize() harus melemparkan RuntimeError
    with pytest.raises(RuntimeError, match="belum diinisialisasi"):
        service.rank_talents([["React"]])
        
    # recompute_ic_similarity() sebelum initialize() harus melemparkan RuntimeError
    with pytest.raises(RuntimeError, match="belum diinisialisasi"):
        service.recompute_ic_similarity()


@patch("src.modules.semantic_similarity.similarity_service.SkillGraph")
@patch("src.modules.semantic_similarity.similarity_service.SanchezSimilarity")
@patch("src.modules.semantic_similarity.similarity_service.SkillMatcher")
def test_initialize_and_reload(mock_matcher_cls, mock_sanchez_cls, mock_graph_cls):
    driver = MagicMock()
    service = SemanticSimilarityService(driver, "mydb")
    
    service.initialize()
    
    # Memastikan dependency dibuat dengan argumen yang benar
    mock_graph_cls.assert_called_once_with(driver, "mydb")
    mock_sanchez_cls.assert_called_once_with(mock_graph_cls.return_value)
    mock_matcher_cls.assert_called_once_with(
        driver=driver,
        skill_graph=mock_graph_cls.return_value,
        sanchez=mock_sanchez_cls.return_value,
        database="mydb"
    )
    
    # reload() memanggil ulang logika inisialisasi yang sama
    service.reload()
    assert mock_graph_cls.call_count == 2
    assert mock_sanchez_cls.call_count == 2
    assert mock_matcher_cls.call_count == 2


@patch("src.modules.semantic_similarity.similarity_service.SkillGraph")
@patch("src.modules.semantic_similarity.similarity_service.SanchezSimilarity")
@patch("src.modules.semantic_similarity.similarity_service.SkillMatcher")
def test_rank_talents_passthrough(mock_matcher_cls, mock_sanchez_cls, mock_graph_cls):
    driver = MagicMock()
    service = SemanticSimilarityService(driver)
    service.initialize()
    
    # Setup mock matcher behavior
    mock_matcher_instance = mock_matcher_cls.return_value
    mock_matcher_instance.match.return_value = (["mocked_score"], ["Missing"])
    
    reqs = [["React"], ["Vue"]]
    result, unrec = service.rank_talents(reqs)
    
    # Memastikan call diteruskan ke matcher.match dengan argumen yang sama
    mock_matcher_instance.match.assert_called_once_with(reqs)
    assert result == ["mocked_score"]
    assert unrec == ["Missing"]


@patch("src.modules.semantic_similarity.similarity_service.ICPrecomputer")
@patch("src.modules.semantic_similarity.similarity_service.SkillGraph")
@patch("src.modules.semantic_similarity.similarity_service.SanchezSimilarity")
@patch("src.modules.semantic_similarity.similarity_service.SkillMatcher")
def test_recompute_ic_similarity_passthrough(
    mock_matcher_cls, mock_sanchez_cls, mock_graph_cls, mock_precomputer_cls
):
    driver = MagicMock()
    service = SemanticSimilarityService(driver)
    service.initialize()
    
    # Setup mock precomputer behavior
    mock_precomp_instance = mock_precomputer_cls.return_value
    mock_precomp_instance.run.return_value = "mocked_report"
    
    result = service.recompute_ic_similarity()
    
    # Memastikan Precomputer diinisiasi dengan args yang benar
    mock_precomputer_cls.assert_called_once_with(
        driver=driver,
        skill_graph=mock_graph_cls.return_value,
        sanchez=mock_sanchez_cls.return_value,
        database="neo4j"
    )
    # Memastikan metode run dijalankan
    mock_precomp_instance.run.assert_called_once()
    assert result == "mocked_report"
