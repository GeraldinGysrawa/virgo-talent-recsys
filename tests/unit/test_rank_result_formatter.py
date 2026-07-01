# =============================================================
# tests/unit/test_rank_result_formatter.py
# WB-SAW-04 — RankResultFormatter
#
# Titik keputusan kritis:
#   - format() kosong → RecommendationResult dengan message & total=0
#   - Slicing top 5 / other 50 / has_more benar
#   - _build_constraints: label concern perbankan muncul jika is_banking=True
#   - _build_constraints: label lokasi muncul jika tidak cocok
#   - _location_matches: "Tanpa Batasan" cocok dengan semua lokasi
# =============================================================

import pytest

from src.modules.saw.rank_result_formatter import RankResultFormatter
from src.modules.saw.schemas import RankedCandidate, SAWCandidate


# ----------------------------------------------------------
# Helper
# ----------------------------------------------------------

def _ranked(nip: str, score: float = 1.0) -> RankedCandidate:
    return RankedCandidate(nip=nip, nama_lengkap=f"Nama {nip}", final_score=score)


def _cand(
    nip: str,
    lokasi: list[str] | None = None,
    concern: bool = False,
) -> SAWCandidate:
    return SAWCandidate(
        nip=nip,
        nama_lengkap=f"Nama {nip}",
        skill_score=0.5,
        skills=[],
        ketersediaan="idle",
        pendidikan="S1",
        pengalaman_tahun=3.0,
        lokasi_penempatan=lokasi or [],
        concern_perbankan=concern,
    )


# ----------------------------------------------------------
# format()
# ----------------------------------------------------------

class TestFormatEmpty:
    def test_empty_returns_zero_total(self):
        result = RankResultFormatter.format([], [])
        assert result.total_candidates == 0

    def test_empty_returns_non_empty_message(self):
        result = RankResultFormatter.format([], [])
        assert result.message is not None
        assert len(result.message) > 0

    def test_empty_top_and_other_talents_are_empty_lists(self):
        result = RankResultFormatter.format([], [])
        assert result.top_talents == []
        assert result.other_talents == []

    def test_empty_has_more_is_false(self):
        result = RankResultFormatter.format([], [])
        assert result.has_more is False


class TestFormatSlicing:
    def _make_n(self, n: int):
        ranked = [_ranked(str(i), score=1.0 - i * 0.01) for i in range(n)]
        candidates = [_cand(str(i)) for i in range(n)]
        return ranked, candidates

    def test_3_candidates_all_in_top_talents(self):
        ranked, candidates = self._make_n(3)
        result = RankResultFormatter.format(ranked, candidates)
        assert len(result.top_talents) == 3
        assert len(result.other_talents) == 0
        assert result.total_candidates == 3

    def test_5_candidates_fills_top_exactly(self):
        ranked, candidates = self._make_n(5)
        result = RankResultFormatter.format(ranked, candidates)
        assert len(result.top_talents) == 5
        assert len(result.other_talents) == 0

    def test_10_candidates_splits_5_top_5_other(self):
        ranked, candidates = self._make_n(10)
        result = RankResultFormatter.format(ranked, candidates)
        assert len(result.top_talents) == 5
        assert len(result.other_talents) == 5

    def test_55_candidates_has_more_false(self):
        ranked, candidates = self._make_n(55)
        result = RankResultFormatter.format(ranked, candidates)
        assert result.has_more is False
        assert result.total_candidates == 55

    def test_56_candidates_has_more_true(self):
        ranked, candidates = self._make_n(56)
        result = RankResultFormatter.format(ranked, candidates)
        assert result.has_more is True

    def test_message_is_none_when_candidates_exist(self):
        ranked, candidates = self._make_n(1)
        result = RankResultFormatter.format(ranked, candidates)
        assert result.message is None


class TestBuildConstraints:
    def test_banking_concern_label_when_project_is_banking(self):
        candidate = _cand("001", concern=True)
        constraints = RankResultFormatter._build_constraints(
            candidate, location_query=None, is_banking_project=True
        )
        assert any("perbankan" in c.lower() for c in constraints)

    def test_no_banking_label_when_project_is_not_banking(self):
        candidate = _cand("001", concern=True)
        constraints = RankResultFormatter._build_constraints(
            candidate, location_query=None, is_banking_project=False
        )
        assert constraints == []

    def test_no_banking_label_when_no_concern(self):
        candidate = _cand("001", concern=False)
        constraints = RankResultFormatter._build_constraints(
            candidate, location_query=None, is_banking_project=True
        )
        assert constraints == []

    def test_lokasi_label_when_mismatch(self):
        candidate = _cand("001", lokasi=["Jakarta"])
        constraints = RankResultFormatter._build_constraints(
            candidate, location_query="Bandung", is_banking_project=False
        )
        assert any("Lokasi" in c or "lokasi" in c.lower() for c in constraints)

    def test_no_lokasi_label_when_match(self):
        candidate = _cand("001", lokasi=["Bandung"])
        constraints = RankResultFormatter._build_constraints(
            candidate, location_query="Bandung", is_banking_project=False
        )
        assert not any("Lokasi" in c for c in constraints)

    def test_both_banking_and_lokasi_constraints_combined(self):
        candidate = _cand("001", lokasi=["Jakarta"], concern=True)
        constraints = RankResultFormatter._build_constraints(
            candidate, location_query="Bandung", is_banking_project=True
        )
        assert len(constraints) == 2

    def test_none_candidate_returns_empty_list(self):
        constraints = RankResultFormatter._build_constraints(
            None, location_query="Bandung", is_banking_project=True
        )
        assert constraints == []


class TestLocationMatches:
    def test_tanpa_batasan_matches_any_location(self):
        assert RankResultFormatter._location_matches(["Tanpa Batasan"], "Bandung") is True

    def test_tanpa_batasan_case_insensitive(self):
        assert RankResultFormatter._location_matches(["tanpa batasan"], "Jakarta") is True

    def test_exact_match(self):
        assert RankResultFormatter._location_matches(["Bandung"], "Bandung") is True

    def test_case_insensitive_exact_match(self):
        assert RankResultFormatter._location_matches(["bandung"], "Bandung") is True

    def test_no_match(self):
        assert RankResultFormatter._location_matches(["Jakarta"], "Bandung") is False

    def test_match_in_multiple_locations(self):
        assert RankResultFormatter._location_matches(
            ["Jakarta", "Bandung", "Remote"], "Bandung"
        ) is True

    def test_empty_locations_no_match(self):
        assert RankResultFormatter._location_matches([], "Bandung") is False
