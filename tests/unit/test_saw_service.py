# =============================================================
# tests/unit/test_saw_service.py
# WB-SAW-03 — SAWService
#
# Titik keputusan kritis:
#   - rank() memanggil repository.get_by_nips() dengan NIP yang benar
#   - Filter hard exclusion: "irreplacable" dibuang sebelum ranking
#   - Seleksi kriteria: 4 kriteria jika ada education, 3 jika tidak
#   - Kandidat kosong setelah filter → RecommendationResult dengan message
# =============================================================

from unittest.mock import MagicMock

import pytest

from src.modules.saw.saw_service import SAWService
from src.modules.saw.schemas import (
    SAWRankRequest,
    TalentProfile,
    TalentScoreInput,
)


# ----------------------------------------------------------
# Helper
# ----------------------------------------------------------

def _request(nips: list[str], education: list[str] | None = None) -> SAWRankRequest:
    return SAWRankRequest(
        talent_scores=[
            TalentScoreInput(nip=nip, nama_lengkap=f"Nama {nip}", skill_score=0.8, skills=[])
            for nip in nips
        ],
        location=None,
        is_banking_project=False,
        education=education,
    )


def _profile(
    nip: str,
    ketersediaan: str = "idle",
    pendidikan: str | None = "S1",
    pengalaman: float = 3.0,
) -> TalentProfile:
    return TalentProfile(
        nip=nip,
        nama_lengkap=f"Nama {nip}",
        ketersediaan=ketersediaan,
        pendidikan=pendidikan,
        pengalaman_tahun=pengalaman,
    )


# ----------------------------------------------------------
# Tests
# ----------------------------------------------------------

class TestSAWServiceRepository:
    def setup_method(self):
        self.mock_repo = MagicMock()
        self.service = SAWService(repository=self.mock_repo)

    def test_rank_calls_get_by_nips_with_correct_nips(self):
        self.mock_repo.get_by_nips.return_value = []
        self.service.rank(_request(["001", "002", "003"]))
        self.mock_repo.get_by_nips.assert_called_once_with(["001", "002", "003"])

    def test_rank_calls_repository_once_per_request(self):
        self.mock_repo.get_by_nips.return_value = []
        self.service.rank(_request(["001"]))
        assert self.mock_repo.get_by_nips.call_count == 1


class TestSAWServiceFilter:
    def setup_method(self):
        self.mock_repo = MagicMock()
        self.service = SAWService(repository=self.mock_repo)

    def test_irreplacable_excluded_from_ranking(self):
        self.mock_repo.get_by_nips.return_value = [
            _profile("001", ketersediaan="idle"),
            _profile("002", ketersediaan="irreplacable"),
            _profile("003", ketersediaan="replacable"),
        ]
        result = self.service.rank(_request(["001", "002", "003"]))
        nips_in_result = {t.nip for t in result.top_talents + result.other_talents}
        assert "002" not in nips_in_result
        assert result.total_candidates == 2

    def test_transferable_and_replacable_included(self):
        self.mock_repo.get_by_nips.return_value = [
            _profile("001", ketersediaan="transferable"),
            _profile("002", ketersediaan="replacable"),
        ]
        result = self.service.rank(_request(["001", "002"]))
        assert result.total_candidates == 2

    def test_all_irreplacable_returns_message(self):
        self.mock_repo.get_by_nips.return_value = [
            _profile("001", ketersediaan="irreplacable"),
        ]
        result = self.service.rank(_request(["001"]))
        assert result.total_candidates == 0
        assert result.message is not None
        assert len(result.top_talents) == 0

    def test_no_profiles_found_returns_message(self):
        self.mock_repo.get_by_nips.return_value = []
        result = self.service.rank(_request(["001"]))
        assert result.total_candidates == 0
        assert result.message is not None


class TestSAWServiceCriteriaSelection:
    def setup_method(self):
        self.mock_repo = MagicMock()
        self.service = SAWService(repository=self.mock_repo)

    def _setup_one_talent(self):
        self.mock_repo.get_by_nips.return_value = [
            _profile("001", ketersediaan="idle", pendidikan="S1", pengalaman=3.0)
        ]

    def test_four_criteria_when_education_present(self):
        self._setup_one_talent()
        result = self.service.rank(_request(["001"], education=["S1"]))
        top = result.top_talents[0]
        assert "pendidikan" in top.score_breakdown

    def test_three_criteria_when_no_education(self):
        self._setup_one_talent()
        result = self.service.rank(_request(["001"], education=None))
        top = result.top_talents[0]
        assert "pendidikan" not in top.score_breakdown

    def test_three_criteria_when_education_empty_list(self):
        self._setup_one_talent()
        result = self.service.rank(_request(["001"], education=[]))
        top = result.top_talents[0]
        assert "pendidikan" not in top.score_breakdown

    def test_result_always_has_ketersediaan_skill_pengalaman(self):
        self._setup_one_talent()
        result = self.service.rank(_request(["001"]))
        top = result.top_talents[0]
        assert "ketersediaan" in top.score_breakdown
        assert "skill" in top.score_breakdown
        assert "pengalaman" in top.score_breakdown
