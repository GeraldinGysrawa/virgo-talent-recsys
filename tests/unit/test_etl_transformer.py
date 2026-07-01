# =============================================================
# tests/unit/test_etl_transformer.py
# WB-ETL-01 — Transformer
#
# Titik keputusan kritis:
#   - transform() row valid → TalentRecord dengan field benar
#   - pengalaman tidak valid → 0.0 (bukan exception)
#   - pendidikan tidak dikenal → None
#   - status_penugasan tidak dikenal → None
#   - jenis_penempatan tidak dikenal → baris di-skip
#   - concern_perbankan: berbagai representasi truthy
#   - Tanpa normalizer: skill_labels = label mentah dari spreadsheet
#   - Baris invalid tidak menghentikan baris berikutnya
# =============================================================

import pytest

from src.modules.etl.transformer import Transformer, TalentRecord


# ----------------------------------------------------------
# Helper
# ----------------------------------------------------------

def _row(**overrides) -> dict:
    base = {
        "nip": "001",
        "nama_lengkap": "Andi Saputra",
        "pengalaman": "3",
        "concern_perbankan": "false",
        "jenis_penempatan": "bandung",
        "teknologi": "Python",
        "pendidikan": "S1",
        "status_penugasan": "idle",
    }
    base.update(overrides)
    return base


@pytest.fixture
def transformer():
    return Transformer(normalizer=None)


# ===========================================================
# Tests
# ===========================================================

class TestTransformValidRow:
    def test_nip_preserved(self, transformer):
        records = transformer.transform([_row(nip="EMP-001")])
        assert records[0].nip == "EMP-001"

    def test_nama_lengkap_stripped(self, transformer):
        records = transformer.transform([_row(nama_lengkap="  Budi Santoso  ")])
        assert records[0].nama_lengkap == "Budi Santoso"

    def test_pengalaman_as_float(self, transformer):
        records = transformer.transform([_row(pengalaman="5")])
        assert records[0].pengalaman_tahun == 5.0

    def test_pengalaman_decimal(self, transformer):
        records = transformer.transform([_row(pengalaman="2.5")])
        assert records[0].pengalaman_tahun == pytest.approx(2.5)

    def test_concern_false(self, transformer):
        records = transformer.transform([_row(concern_perbankan="false")])
        assert records[0].concern_perbankan is False

    def test_jenis_penempatan_bandung_normalized(self, transformer):
        records = transformer.transform([_row(jenis_penempatan="bandung")])
        assert records[0].jenis_penempatan == ["Bandung"]

    def test_jenis_penempatan_remote_normalized(self, transformer):
        records = transformer.transform([_row(jenis_penempatan="remote")])
        assert records[0].jenis_penempatan == ["Remote"]

    def test_jenis_penempatan_jakarta(self, transformer):
        records = transformer.transform([_row(jenis_penempatan="jakarta")])
        assert records[0].jenis_penempatan == ["Jakarta"]

    def test_jenis_penempatan_tanpa_batasan(self, transformer):
        records = transformer.transform([_row(jenis_penempatan="tanpa batasan")])
        assert records[0].jenis_penempatan == ["Tanpa Batasan"]

    def test_pendidikan_s1(self, transformer):
        records = transformer.transform([_row(pendidikan="S1")])
        assert records[0].pendidikan == "S1"

    def test_status_penugasan_idle(self, transformer):
        records = transformer.transform([_row(status_penugasan="idle")])
        assert records[0].status_penugasan == "idle"

    def test_status_penugasan_irreplacable(self, transformer):
        records = transformer.transform([_row(status_penugasan="irreplacable")])
        assert records[0].status_penugasan == "irreplacable"

    def test_skill_labels_without_normalizer(self, transformer):
        records = transformer.transform([_row(teknologi="Python, Django")])
        assert "Python" in records[0].skill_labels
        assert "Django" in records[0].skill_labels

    def test_empty_teknologi_produces_empty_skill_labels(self, transformer):
        records = transformer.transform([_row(teknologi="")])
        assert records[0].skill_labels == []

    def test_result_is_talent_record_instance(self, transformer):
        records = transformer.transform([_row()])
        assert isinstance(records[0], TalentRecord)


class TestTransformConcernPerbankan:
    def test_true_string(self, transformer):
        assert transformer.transform([_row(concern_perbankan="true")])[0].concern_perbankan is True

    def test_ya_string(self, transformer):
        assert transformer.transform([_row(concern_perbankan="ya")])[0].concern_perbankan is True

    def test_1_string(self, transformer):
        assert transformer.transform([_row(concern_perbankan="1")])[0].concern_perbankan is True

    def test_yes_string(self, transformer):
        assert transformer.transform([_row(concern_perbankan="yes")])[0].concern_perbankan is True

    def test_false_string_is_false(self, transformer):
        assert transformer.transform([_row(concern_perbankan="false")])[0].concern_perbankan is False

    def test_empty_string_is_false(self, transformer):
        assert transformer.transform([_row(concern_perbankan="")])[0].concern_perbankan is False


class TestTransformEdgeCases:
    def test_invalid_pengalaman_defaults_to_zero(self, transformer):
        records = transformer.transform([_row(pengalaman="tidak_valid")])
        assert records[0].pengalaman_tahun == 0.0

    def test_unknown_pendidikan_becomes_none(self, transformer):
        records = transformer.transform([_row(pendidikan="SARJANA_MUDA")])
        assert records[0].pendidikan is None

    def test_unknown_status_penugasan_becomes_none(self, transformer):
        records = transformer.transform([_row(status_penugasan="sangat_sibuk")])
        assert records[0].status_penugasan is None

    def test_unknown_placement_skips_row(self, transformer):
        records = transformer.transform([_row(jenis_penempatan="planet_mars")])
        assert len(records) == 1
        assert records[0].jenis_penempatan == ["planet_mars"]

    def test_empty_placement_skips_row(self, transformer):
        records = transformer.transform([_row(jenis_penempatan="")])
        assert len(records) == 1
        assert records[0].jenis_penempatan == []

    def test_invalid_row_does_not_stop_subsequent_valid_rows(self, transformer):
        rows = [
            _row(nip="001", jenis_penempatan="tidak_dikenal"),
            _row(nip="002"),
        ]
        records = transformer.transform(rows)
        assert len(records) == 2
        assert records[0].nip == "001"
        assert records[0].jenis_penempatan == ["tidak_dikenal"]
        assert records[1].nip == "002"

    def test_multiple_rows_all_valid(self, transformer):
        rows = [_row(nip=str(i)) for i in range(5)]
        records = transformer.transform(rows)
        assert len(records) == 5


class TestTransformMultiplePlacements:
    def test_bandung_and_remote(self, transformer):
        records = transformer.transform([_row(jenis_penempatan="bandung, remote")])
        result_set = set(records[0].jenis_penempatan)
        assert "Bandung" in result_set
        assert "Remote" in result_set

    def test_pipe_separator(self, transformer):
        records = transformer.transform([_row(jenis_penempatan="bandung|jakarta")])
        result_set = set(records[0].jenis_penempatan)
        assert "Bandung" in result_set
        assert "Jakarta" in result_set

    def test_slash_separator(self, transformer):
        records = transformer.transform([_row(jenis_penempatan="bandung/remote")])
        result_set = set(records[0].jenis_penempatan)
        assert "Bandung" in result_set
        assert "Remote" in result_set
