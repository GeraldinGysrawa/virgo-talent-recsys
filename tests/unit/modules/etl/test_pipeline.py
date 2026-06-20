import pytest
from unittest.mock import MagicMock, patch

from src.modules.etl.pipeline import ETLPipeline, ETLConfig
from src.modules.etl.transformer import TalentRecord
from src.modules.etl.validator import ValidationResult
from src.modules.etl.neo4j_writer import WriteResult


@pytest.fixture
def config():
    return ETLConfig(
        credentials_path="dummy.json",
        spreadsheet_id="dummy_id"
    )


@patch('src.modules.etl.pipeline.SheetsReader')
@patch('src.modules.etl.pipeline.OntologyValidator')
@patch('src.modules.etl.pipeline.SkillNormalizer')
@patch('src.modules.etl.pipeline.Transformer')
@patch('src.modules.etl.pipeline.Neo4jWriter')
def test_pipeline_run_success(mock_writer_cls, mock_transformer_cls, mock_normalizer_cls, mock_validator_cls, mock_reader_cls, config):
    # Memastikan eksekusi linear dari tahapan pipeline berjalan baik
    
    # Setup reader
    mock_reader = mock_reader_cls.return_value
    mock_reader.fetch_all.return_value = [{"nip": "123"}]
    
    # Setup validator
    mock_validator = mock_validator_cls.return_value
    mock_onto = MagicMock()
    mock_cls = MagicMock()
    mock_cls.name = "React"
    mock_cls.label = ["React.js"]
    mock_cls.iri = "http://test/react"
    mock_onto.classes.return_value = [mock_cls]
    mock_validator._onto = mock_onto
    
    val_res = ValidationResult(nip="123", is_valid=True)
    mock_validator.validate.return_value = val_res
    
    # Setup transformer
    mock_transformer = mock_transformer_cls.return_value
    record = TalentRecord(nip="123", nama_lengkap="Andi", pengalaman_tahun=1.0, concern_perbankan=False)
    mock_transformer.transform.return_value = [record]
    
    # Setup writer
    mock_writer = mock_writer_cls.return_value
    mock_writer.write_batch.return_value = [WriteResult(nip="123", success=True)]
    
    pipeline = ETLPipeline(config)
    report = pipeline.run()
    
    assert report.total_rows == 1
    assert report.transformed_ok == 1
    assert report.validated_ok == 1
    assert report.written_ok == 1
    assert len(report.validation_errors) == 0
    assert len(report.write_errors) == 0


@patch('src.modules.etl.pipeline.SheetsReader')
def test_pipeline_empty_sheets(mock_reader_cls, config):
    # Eksekusi harus langsung return jika di awal data mentah tidak ditemukan
    mock_reader = mock_reader_cls.return_value
    mock_reader.fetch_all.return_value = []
    
    pipeline = ETLPipeline(config)
    report = pipeline.run()
    
    assert report.total_rows == 0
    assert report.transformed_ok == 0
    assert report.validated_ok == 0
    assert report.written_ok == 0
