# =============================================================
# tests/unit/test_saw_ranker.py
# WB-SAW-02 — SAWRanker
#
# Titik keputusan kritis:
#   - rank() kosong → []
#   - Pengurutan descending berdasarkan final_score
#   - Tiebreaker: NIP ascending (deterministik)
#   - _score_education: biner ≥ threshold
#   - _normalize_benefit: bounded (ketersediaan/skill) vs unbounded (pengalaman)
#   - _compute_preference_scores: Σ(w_j × r_ij) benar
# =============================================================

import pytest

from src.modules.saw.schemas import SAWCandidate
from src.modules.saw.saw_ranker import SAWRanker


# ----------------------------------------------------------
# Helper
# ----------------------------------------------------------

def _cand(
    nip: str,
    skill_score: float = 0.5,
    ketersediaan: str = "idle",
    pendidikan: str | None = "S1",
    pengalaman: float = 3.0,
) -> SAWCandidate:
    return SAWCandidate(
        nip=nip,
        nama_lengkap=f"Nama {nip}",
        skill_score=skill_score,
        skills=[],
        ketersediaan=ketersediaan,
        pendidikan=pendidikan,
        pengalaman_tahun=pengalaman,
    )


W3 = {"ketersediaan": 0.6111, "skill": 0.2778, "pengalaman": 0.1111}
W4 = {"ketersediaan": 0.5208, "pendidikan": 0.2708, "skill": 0.1458, "pengalaman": 0.0625}


# ----------------------------------------------------------
# rank()
# ----------------------------------------------------------

class TestRankEmpty:
    def test_empty_candidates_returns_empty_list(self):
        result = SAWRanker.rank([], weights=W3)
        assert result == []


class TestRankSorting:
    def test_sorted_descending_by_final_score(self):
        # Kandidat B punya skill lebih tinggi → skor lebih tinggi
        candidates = [
            _cand("001", skill_score=0.2),
            _cand("002", skill_score=0.9),
        ]
        result = SAWRanker.rank(candidates, weights=W3)
        assert result[0].nip == "002"
        assert result[1].nip == "001"
        assert result[0].final_score >= result[1].final_score

    def test_tiebreaker_nip_ascending(self):
        """Jika skor sama, NIP lebih kecil muncul duluan."""
        candidates = [
            _cand("002", skill_score=0.5, ketersediaan="idle", pengalaman=3.0),
            _cand("001", skill_score=0.5, ketersediaan="idle", pengalaman=3.0),
        ]
        result = SAWRanker.rank(candidates, weights=W3)
        assert result[0].nip == "001"

    def test_ranked_candidate_contains_score_breakdown(self):
        candidates = [_cand("001")]
        result = SAWRanker.rank(candidates, weights=W3)
        assert "ketersediaan" in result[0].score_per_criteria
        assert "skill" in result[0].score_per_criteria
        assert "pengalaman" in result[0].score_per_criteria


class TestRankWithEducation:
    def test_education_criteria_included_when_education_query_set(self):
        candidates = [
            _cand("001", pendidikan="S1"),
            _cand("002", pendidikan="D3"),
        ]
        result = SAWRanker.rank(candidates, weights=W4, education_query=["S1"])
        # 001 (S1 ≥ S1 → 1.0) harus di atas 002 (D3 < S1 → 0.0)
        assert result[0].nip == "001"


# ----------------------------------------------------------
# _score_education
# ----------------------------------------------------------

class TestScoreEducation:
    def test_talent_education_meets_threshold(self):
        assert SAWRanker._score_education("S1", ["S1"]) == 1.0

    def test_talent_education_exceeds_threshold(self):
        assert SAWRanker._score_education("S2", ["S1"]) == 1.0

    def test_talent_education_below_threshold(self):
        assert SAWRanker._score_education("D3", ["S1"]) == 0.0

    def test_no_education_query_returns_zero(self):
        assert SAWRanker._score_education("S1", None) == 0.0

    def test_empty_education_query_returns_zero(self):
        assert SAWRanker._score_education("S1", []) == 0.0

    def test_none_talent_education_returns_zero(self):
        assert SAWRanker._score_education(None, ["S1"]) == 0.0

    def test_multiple_education_query_uses_highest(self):
        # Query ["D3", "S1"] → threshold = S1 (rank 6)
        assert SAWRanker._score_education("S1", ["D3", "S1"]) == 1.0
        assert SAWRanker._score_education("D3", ["D3", "S1"]) == 0.0


# ----------------------------------------------------------
# _normalize_benefit
# ----------------------------------------------------------

class TestNormalizeBenefit:
    def test_ketersediaan_idle_normalized_to_1(self):
        # idle = 4.0, batas teoritis = 4.0
        matrix = [{"ketersediaan": 4.0}]
        norm = SAWRanker._normalize_benefit(matrix, ["ketersediaan"])
        assert norm[0]["ketersediaan"] == pytest.approx(1.0)

    def test_ketersediaan_replacable_normalized_to_half(self):
        # replacable = 2.0, batas teoritis = 4.0 → 0.5
        matrix = [{"ketersediaan": 2.0}]
        norm = SAWRanker._normalize_benefit(matrix, ["ketersediaan"])
        assert norm[0]["ketersediaan"] == pytest.approx(0.5)

    def test_skill_bounded_by_1(self):
        matrix = [{"skill": 0.8}]
        norm = SAWRanker._normalize_benefit(matrix, ["skill"])
        assert norm[0]["skill"] == pytest.approx(0.8)

    def test_pengalaman_relative_to_max(self):
        matrix = [{"pengalaman": 10.0}, {"pengalaman": 5.0}]
        norm = SAWRanker._normalize_benefit(matrix, ["pengalaman"])
        assert norm[0]["pengalaman"] == pytest.approx(1.0)
        assert norm[1]["pengalaman"] == pytest.approx(0.5)

    def test_pengalaman_all_zero_stays_zero(self):
        matrix = [{"pengalaman": 0.0}, {"pengalaman": 0.0}]
        norm = SAWRanker._normalize_benefit(matrix, ["pengalaman"])
        assert norm[0]["pengalaman"] == 0.0
        assert norm[1]["pengalaman"] == 0.0

    def test_pendidikan_bounded_binary(self):
        matrix = [{"pendidikan": 1.0}]
        norm = SAWRanker._normalize_benefit(matrix, ["pendidikan"])
        assert norm[0]["pendidikan"] == pytest.approx(1.0)


# ----------------------------------------------------------
# _compute_preference_scores
# ----------------------------------------------------------

class TestComputePreferenceScores:
    def test_single_candidate_correct_weighted_sum(self):
        candidates = [_cand("001")]
        normalized = [{"ketersediaan": 1.0, "skill": 0.5, "pengalaman": 0.3}]
        weights = {"ketersediaan": 0.6111, "skill": 0.2778, "pengalaman": 0.1111}
        active = ["ketersediaan", "skill", "pengalaman"]

        results = SAWRanker._compute_preference_scores(candidates, normalized, weights, active)

        expected = 0.6111 * 1.0 + 0.2778 * 0.5 + 0.1111 * 0.3
        assert results[0].final_score == pytest.approx(expected, abs=1e-4)

    def test_score_breakdown_keys_match_active_criteria(self):
        candidates = [_cand("001")]
        normalized = [{"ketersediaan": 1.0, "skill": 0.5}]
        weights = {"ketersediaan": 0.7, "skill": 0.3}
        active = ["ketersediaan", "skill"]

        results = SAWRanker._compute_preference_scores(candidates, normalized, weights, active)
        assert set(results[0].score_per_criteria.keys()) == {"ketersediaan", "skill"}
