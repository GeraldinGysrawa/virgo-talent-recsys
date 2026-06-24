import pytest
from unittest.mock import MagicMock
from datetime import datetime

from src.modules.etl.transformer import Transformer, TalentRecord


@pytest.fixture
def mock_normalizer():
    normalizer = MagicMock()
    # Mock return value for normalize_batch
    # Pura-pura 'React.js' adalah canonical dari 'React'
    def mock_normalize_batch(labels):
        from src.modules.etl.skill_normalizer import NormalizeResult
        res = []
        for l in labels:
            if l.lower() == "react":
                res.append(NormalizeResult(l, "React.js", "exact", 1.0))
            else:
                res.append(NormalizeResult(l, None, "not_found", 0.0))
        return res
    normalizer.normalize_batch.side_effect = mock_normalize_batch
    return normalizer


def test_transformer_clean_row(mock_normalizer):
    transformer = Transformer(normalizer=mock_normalizer)
    
    raw_row = {
        "nip": " 123 ",
        "nama_lengkap": "Budi Santoso",
        "pengalaman": " 3.5 ",
        "concern_perbankan": "Ya",
        "jenis_penempatan": " remote, jakarta ",
        "teknologi": "React, Angular",
        "project": "ProjA",
        "start_date": "15/01/2023",
        "end_date": "16-02-2023",
        "pendidikan": " s1 ",
        "status_penugasan": " IDLE "
    }
    
    records = transformer.transform([raw_row])
    assert len(records) == 1
    
    record = records[0]
    assert record.nip == "123"
    assert record.pengalaman_tahun == 3.5
    assert record.concern_perbankan is True
    assert record.jenis_penempatan == ["Remote", "Jakarta"]
    
    assert record.skill_labels == ["React.js"]
    assert record.skill_raw == ["React", "Angular"]
    assert record.skill_not_found == ["Angular"]
    
    assert record.start_date == "2023-01-15"
    assert record.end_date == "2023-02-16"
    assert record.pendidikan == "S1"
    assert record.status_penugasan == "idle"


def test_transformer_invalid_data(mock_normalizer):
    transformer = Transformer(normalizer=mock_normalizer)
    
    raw_row = {
        "nip": "321",
        "nama_lengkap": "Andi",
        "pengalaman": "bukan angka",
        "concern_perbankan": "salah",
        "jenis_penempatan": "tidak jelas",
    }
    
    # Karena sekarang transformer melonggarkan validasi penempatan,
    # baris tidak dibuang (len records == 1) dan diteruskan ke Validator.
    records = transformer.transform([raw_row])
    assert len(records) == 1
    
    record = records[0]
    assert record.pengalaman_tahun == 0.0
    assert record.concern_perbankan is False
    assert record.jenis_penempatan == ["tidak jelas"]


def test_parse_date_serial():
    transformer = Transformer()
    
    # Angka serial dari format tanggal di excel/sheets (misalnya 45000 = 15 Maret 2023)
    # (Tepatnya: 1899-12-30 + 45000 days = 2023-03-15)
    date_iso = transformer._parse_date(45000, "123")
    assert date_iso == "2023-03-15"
    
    # Empty date format ditangani aman
    assert transformer._parse_date("", "123") is None
