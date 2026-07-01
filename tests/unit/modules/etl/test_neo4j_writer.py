import pytest
from unittest.mock import MagicMock, call, patch

from src.modules.etl.neo4j_writer import Neo4jWriter
from src.modules.etl.transformer import TalentRecord


@pytest.fixture
def dummy_record():
    return TalentRecord(
        nip="123",
        nama_lengkap="Dummy",
        pengalaman_tahun=1.0,
        concern_perbankan=False,
        jenis_penempatan=["Bandung"],
        skill_labels=["React.js"],
        project_nama="Secret Project",
        start_date="2023-01-01",
        end_date="2023-12-31",
        pendidikan="S1",
        status_penugasan="idle"
    )


@patch("src.modules.etl.neo4j_writer.GraphDatabase")
def test_neo4j_writer_write_batch_success(mock_gdb, dummy_record):
    mock_driver = MagicMock()
    mock_gdb.driver.return_value = mock_driver
    
    writer = Neo4jWriter("bolt://dummy", "user", "pass")
    
    # Mock session
    mock_session = MagicMock()
    mock_driver.session.return_value.__enter__.return_value = mock_session
    
    # Mock tx
    mock_tx = MagicMock()
    mock_session.begin_transaction.return_value.__enter__.return_value = mock_tx
    
    skill_uri_map = {"React.js": "http://test/React.js"}
    
    results = writer.write_batch([dummy_record], skill_uri_map)
    
    assert len(results) == 1
    assert results[0].success is True
    assert results[0].nip == "123"
    
    # Verify tx.run was called multiple times (Talent, Placement, Skill, Delete Project, Merge Project)
    assert mock_tx.run.call_count >= 5


@patch("src.modules.etl.neo4j_writer.GraphDatabase")
def test_neo4j_writer_write_batch_failure(mock_gdb, dummy_record):
    mock_driver = MagicMock()
    mock_gdb.driver.return_value = mock_driver
    
    writer = Neo4jWriter("bolt://dummy", "user", "pass")
    
    mock_session = MagicMock()
    mock_driver.session.return_value.__enter__.return_value = mock_session
    
    # Mock tx to throw exception
    mock_tx = MagicMock()
    mock_session.begin_transaction.return_value.__enter__.return_value = mock_tx
    mock_tx.run.side_effect = Exception("Database is down!")
    
    results = writer.write_batch([dummy_record], {})
    
    # Harapannya kegagalan saat menulis ke db bisa tertangkap try-except
    # dan success=False tanpa membuat aplikasi berhenti (crash)
    assert len(results) == 1
    assert results[0].success is False
    assert "Database is down!" in results[0].message
