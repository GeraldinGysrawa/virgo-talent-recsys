import pytest
from unittest.mock import MagicMock, patch

from src.modules.semantic_similarity.ic_precompute_v2 import ICPrecomputer


@pytest.fixture
def mock_driver():
    driver = MagicMock()
    session = MagicMock()
    # Support for `with driver.session(...) as session:`
    driver.session.return_value.__enter__.return_value = session
    return driver


@pytest.fixture
def mock_graph():
    graph = MagicMock()
    graph.all_uris.return_value = ["uri1", "uri2", "uri3"]
    return graph


@pytest.fixture
def mock_sanchez():
    sanchez = MagicMock()
    sanchez.similarity_by_uri.return_value = 0.75
    return sanchez


def test_run_success_and_delete_old_data(mock_driver, mock_graph, mock_sanchez):
    # Memastikan run() mengeksekusi penghapusan data lama, iterasi uri, dan menulis hasilnya.
    precomputer = ICPrecomputer(mock_driver, mock_graph, mock_sanchez)
    
    report = precomputer.run()
    
    session = mock_driver.session.return_value.__enter__.return_value
    
    # Verifikasi penghapusan (DELETE lama) dipanggil pertama kali
    assert session.run.call_count >= 1
    delete_call = session.run.call_args_list[0]
    assert "DELETE r" in delete_call[0][0]
    
    # 3 URIs -> 3 kombinasi pasangan (1-2, 1-3, 2-3)
    assert report.total_nodes == 3
    assert report.total_pairs == 3
    assert report.similarity_written == 3
    assert len(report.errors) == 0
    
    # similarity_by_uri dipanggil untuk semua pasangan
    assert mock_sanchez.similarity_by_uri.call_count == 3
    
    # Verifikasi penulisan batch. 
    # Karena _BATCH_SIZE default (500) > 3, maka _write_similarity_batch hanya dipanggil di akhir iterasi
    write_call = session.run.call_args_list[1]
    assert "MERGE (a)-[r:SKILL_SIMILARITY]->(b)" in write_call[0][0]
    assert len(write_call[1]["rows"]) == 3


def test_batching_mechanism(mock_driver, mock_graph, mock_sanchez):
    # Memastikan mekanisme batching berjalan dengan baik saat data melebihi _BATCH_SIZE
    mock_graph.all_uris.return_value = ["u1", "u2", "u3", "u4"] # 4 URIs -> 6 pasangan
    
    precomputer = ICPrecomputer(mock_driver, mock_graph, mock_sanchez)
    
    # Patching _BATCH_SIZE agar test berjalan cepat dengan ukuran batch kecil
    with patch("src.modules.semantic_similarity.ic_precompute_v2._BATCH_SIZE", 4):
        report = precomputer.run()
        
    assert report.total_pairs == 6
    assert report.similarity_written == 6
    
    session = mock_driver.session.return_value.__enter__.return_value
    
    # 1st call: DELETE
    # 2nd call: MERGE (batch pertama berisi 4 item)
    # 3rd call: MERGE (batch kedua sisa 2 item)
    assert session.run.call_count == 3
    
    call2 = session.run.call_args_list[1]
    call3 = session.run.call_args_list[2]
    
    assert len(call2[1]["rows"]) == 4
    assert len(call3[1]["rows"]) == 2


def test_empty_uris(mock_driver, mock_graph, mock_sanchez):
    # Edge case jika daftar URI kosong tidak crash dan tidak memanggil _write
    mock_graph.all_uris.return_value = []
    precomputer = ICPrecomputer(mock_driver, mock_graph, mock_sanchez)
    
    report = precomputer.run()
    
    assert report.total_nodes == 0
    assert report.total_pairs == 0
    assert report.similarity_written == 0
    
    session = mock_driver.session.return_value.__enter__.return_value
    # Tetap memanggil fungsi _clear_old_data(), tapi tidak memanggil MERGE (batch penulisan)
    assert session.run.call_count == 1
    assert "DELETE r" in session.run.call_args_list[0][0][0]


def test_single_uri(mock_driver, mock_graph, mock_sanchez):
    # Edge case jika daftar hanya 1 URI -> 0 kombinasi
    mock_graph.all_uris.return_value = ["uri1"]
    precomputer = ICPrecomputer(mock_driver, mock_graph, mock_sanchez)
    
    report = precomputer.run()
    
    assert report.total_nodes == 1
    assert report.total_pairs == 0
    assert report.similarity_written == 0
    
    session = mock_driver.session.return_value.__enter__.return_value
    assert session.run.call_count == 1


def test_write_error_handling(mock_driver, mock_graph, mock_sanchez):
    # Memastikan exception pada session.run (database timeout, dll) tertangkap dalam array errors
    mock_graph.all_uris.return_value = ["u1", "u2"]
    precomputer = ICPrecomputer(mock_driver, mock_graph, mock_sanchez)
    
    session = mock_driver.session.return_value.__enter__.return_value
    
    def session_run_side_effect(*args, **kwargs):
        if "MERGE" in args[0]:
            raise Exception("Mocked database error")
        return MagicMock()
        
    session.run.side_effect = session_run_side_effect
    
    report = precomputer.run()
    
    assert report.total_pairs == 1
    assert report.similarity_written == 0
    assert len(report.errors) == 1
    assert "Mocked database error" in report.errors[0]["error"]
