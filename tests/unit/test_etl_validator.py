# =============================================================
# tests/unit/test_etl_validator.py
# WB-ETL-02 — OntologyValidator
#
# Titik keputusan kritis:
#   - Validasi struktural: NIP kosong → is_valid=False
#   - Validasi struktural: placement tidak dikenal → is_valid=False
#   - Validasi skill: label tidak dikenal → warning, is_valid tetap True
#   - Record valid lolos validasi struktural
#
# Dependency: file TTL minimal (tests/fixtures/test_ontology.ttl)
# owlready2 + rdflib diperlukan — tidak dapat di-pure-mock.
# Reasoner (HermiT) dijalankan jika Java tersedia; jika tidak,
# hasilnya adalah warning saja (is_valid tidak berubah).
# =============================================================

from pathlib import Path

import pytest

from src.modules.etl.transformer import TalentRecord

# Guard: skip seluruh modul jika owlready2 tidak tersedia
owlready2 = pytest.importorskip("owlready2", reason="owlready2 tidak terinstal")

from src.modules.etl.validator import OntologyValidator

FIXTURE_TTL = Path(__file__).parent.parent / "fixtures" / "test_ontology.ttl"


# ----------------------------------------------------------
# Helper
# ----------------------------------------------------------

def _record(**overrides) -> TalentRecord:
    base = dict(
        nip="001",
        nama_lengkap="Andi Saputra",
        pengalaman_tahun=3.0,
        concern_perbankan=False,
        jenis_penempatan=["Bandung"],
        skill_labels=["Python"],
    )
    base.update(overrides)
    return TalentRecord(**base)


@pytest.fixture(scope="module")
def validator():
    return OntologyValidator(FIXTURE_TTL)


# ===========================================================
# Tests
# ===========================================================

class TestOntologyValidatorLoad:
    def test_fixture_ttl_exists(self):
        assert FIXTURE_TTL.exists(), f"Fixture TTL tidak ditemukan: {FIXTURE_TTL}"

    def test_validator_loads_without_error(self):
        v = OntologyValidator(FIXTURE_TTL)
        assert v is not None

    def test_skill_label_indexed(self):
        v = OntologyValidator(FIXTURE_TTL)
        # "Python" ada di TTL sebagai rdfs:label
        cls = v.get_skill_class("Python")
        assert cls is not None

    def test_nonexistent_ttl_raises_file_not_found(self):
        with pytest.raises(FileNotFoundError):
            OntologyValidator("/path/tidak/ada/file.ttl")


class TestValidateValidRecord:
    def test_valid_record_passes(self, validator):
        record = _record()
        result = validator.validate(record)
        assert result.is_valid is True

    def test_valid_record_has_no_errors(self, validator):
        record = _record()
        result = validator.validate(record)
        assert result.errors == []

    def test_valid_bandung_placement(self, validator):
        record = _record(jenis_penempatan=["Bandung"])
        result = validator.validate(record)
        assert result.is_valid is True

    def test_valid_remote_placement(self, validator):
        record = _record(jenis_penempatan=["Remote"])
        result = validator.validate(record)
        assert result.is_valid is True

    def test_valid_tanpa_batasan_placement(self, validator):
        record = _record(jenis_penempatan=["Tanpa Batasan"])
        result = validator.validate(record)
        assert result.is_valid is True

    def test_valid_jakarta_placement(self, validator):
        record = _record(jenis_penempatan=["Jakarta"])
        result = validator.validate(record)
        assert result.is_valid is True


class TestValidateNIP:
    def test_empty_nip_fails(self, validator):
        record = _record(nip="")
        result = validator.validate(record)
        assert result.is_valid is False

    def test_whitespace_nip_fails(self, validator):
        record = _record(nip="   ")
        result = validator.validate(record)
        assert result.is_valid is False

    def test_nip_error_message_mentions_nip(self, validator):
        record = _record(nip="")
        result = validator.validate(record)
        assert any("NIP" in e for e in result.errors)


class TestValidatePlacement:
    def test_unknown_placement_fails(self, validator):
        record = _record(jenis_penempatan=["planet_mars"])
        result = validator.validate(record)
        assert result.is_valid is False

    def test_unknown_placement_error_mentions_penempatan(self, validator):
        record = _record(jenis_penempatan=["unknown_city"])
        result = validator.validate(record)
        assert any("Penempatan" in e or "penempatan" in e.lower() for e in result.errors)

    def test_empty_placement_list_fails(self, validator):
        record = _record(jenis_penempatan=[])
        result = validator.validate(record)
        assert result.is_valid is False


class TestValidateSkills:
    def test_known_skill_produces_no_warning(self, validator):
        record = _record(skill_labels=["Python"])
        result = validator.validate(record)
        assert not any("Python" in w for w in result.warnings)

    def test_unknown_skill_produces_warning_not_error(self, validator):
        record = _record(skill_labels=["CobolSkillXYZ99"])
        result = validator.validate(record)
        assert result.is_valid is True
        assert any("CobolSkillXYZ99" in w for w in result.warnings)

    def test_no_skills_still_valid(self, validator):
        record = _record(skill_labels=[])
        result = validator.validate(record)
        assert result.is_valid is True

    def test_validation_result_has_nip(self, validator):
        record = _record(nip="NIP-TEST-007")
        result = validator.validate(record)
        assert result.nip == "NIP-TEST-007"
