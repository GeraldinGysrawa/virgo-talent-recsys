# =============================================================
# src/modules/saw/saw_service.py
# Modul SAW — Increment 3: Simple Additive Weighting
#
# Tanggung Jawab:
#   Orchestrator utama modul SAW (GRASP Controller).
#   Mengkoordinasi seluruh langkah perankingan multi-kriteria:
#   1. Ambil profil talenta via TalentRepository
#   2. Merge skill_score dari input dengan profil
#   3. Filter hard exclusion (irreplaceable)
#   4. Tentukan kriteria aktif (n=3 atau n=4)
#   5. Hitung bobot ROC
#   6. Jalankan SAW ranking
#   7. Format hasil dengan label constraint
#
# Catatan:
#   - SAWService tidak mengetahui detail Neo4j sama sekali;
#     akses data sepenuhnya didelegasikan ke TalentRepository.
#   - Stateless — diinstansiasi per request oleh caller
#     (router sementara; akan digantikan RecommendationRouter).
# =============================================================

from __future__ import annotations

from loguru import logger

from src.modules.saw.schemas import (
    SAWRankRequest,
    TalentProfile,
    SAWCandidate,
    RecommendationResult,
    _EXCLUDED_STATUS,
)
from src.modules.saw.talent_repository import TalentRepository
from src.modules.saw.roc_weight_calculator import ROCWeightCalculator
from src.modules.saw.saw_ranker import SAWRanker
from src.modules.saw.rank_result_formatter import RankResultFormatter


class SAWService:
    """
    Orchestrator utama modul SAW (GRASP Controller).

    Menerima TalentScoreInput[] dari n8n (output /similarity/rank),
    mengambil profil lengkap via TalentRepository, lalu menjalankan
    SAW multi-kriteria dengan bobot ROC.

    Parameters
    ----------
    repository : TalentRepository
        Repository akses data talenta dari Neo4j.
        Seluruh urusan database berhenti di sini.
    """

    def __init__(self, repository: TalentRepository) -> None:
        self._repository = repository

    def rank(self, request: SAWRankRequest) -> RecommendationResult:
        """
        Menjalankan seluruh alur perankingan SAW.

        Parameters
        ----------
        request : SAWRankRequest
            Request body dari endpoint POST /saw/rank.

        Returns
        -------
        RecommendationResult
            Hasil rekomendasi dengan top 5 talenta dan label constraint.
        """
        # ── 1. Ambil daftar NIP dari input ────────────────────
        nip_list = [ts.nip for ts in request.talent_scores]
        logger.info(
            f"SAWService: menerima {len(nip_list)} talenta untuk diranking."
        )

        # ── 2. Ambil profil talenta via repository ────────────
        profiles = self._repository.get_by_nips(nip_list)
        logger.info(
            f"SAWService: {len(profiles)} profil ditemukan "
            f"dari {len(nip_list)} NIP yang diminta."
        )

        # ── 3. Merge skill_score + profil → SAWCandidate ──────
        skill_score_map: dict[str, float] = {
            ts.nip: ts.skill_score for ts in request.talent_scores
        }
        candidates = self._merge_candidates(profiles, skill_score_map)

        # ── 4. Filter hard exclusion (irreplaceable) ──────────
        before_filter = len(candidates)
        candidates = [
            c for c in candidates
            if c.ketersediaan != _EXCLUDED_STATUS
        ]
        filtered_count = before_filter - len(candidates)
        if filtered_count > 0:
            logger.info(
                f"SAWService: {filtered_count} talenta dikeluarkan "
                f"(status '{_EXCLUDED_STATUS}')."
            )

        # ── 5. Cek apakah ada kandidat tersisa ────────────────
        if not candidates:
            logger.warning(
                "SAWService: tidak ada kandidat tersisa setelah filter. "
                "Mengembalikan pesan informatif."
            )
            return RankResultFormatter.format(
                ranked_candidates=[],
                candidates_data=[],
                location_query=request.location,
                is_banking_project=request.is_banking_project,
            )

        # ── 6. Tentukan kriteria aktif ────────────────────────
        education_query = request.education
        has_education = (
            education_query is not None and len(education_query) > 0
        )
        n_criteria = 4 if has_education else 3
        logger.info(
            f"SAWService: {n_criteria} kriteria aktif "
            f"({'dengan' if has_education else 'tanpa'} pendidikan)."
        )

        # ── 7. Hitung bobot ROC ───────────────────────────────
        weights = ROCWeightCalculator.get_weights(n_criteria)

        # ── 8. Jalankan SAW ranking ───────────────────────────
        ranked = SAWRanker.rank(
            candidates=candidates,
            weights=weights,
            education_query=education_query,
        )

        # ── 9. Format hasil dengan label constraint ───────────
        result = RankResultFormatter.format(
            ranked_candidates=ranked,
            candidates_data=candidates,
            location_query=request.location,
            is_banking_project=request.is_banking_project,
        )

        logger.info(
            f"SAWService: selesai. "
            f"{result.total_candidates} kandidat diranking, "
            f"menampilkan top {len(result.top_talents)}."
        )
        return result

    # ----------------------------------------------------------
    # Private — Merge skill_score + profil
    # ----------------------------------------------------------

    @staticmethod
    def _merge_candidates(
        profiles: list[TalentProfile],
        skill_score_map: dict[str, float],
    ) -> list[SAWCandidate]:
        """
        Menggabungkan profil Neo4j dengan skill_score dari input n8n.

        Parameters
        ----------
        profiles : list[TalentProfile]
            Profil talenta dari Neo4j.
        skill_score_map : dict[str, float]
            Mapping NIP → skill_score dari TalentScoreInput.

        Returns
        -------
        list[SAWCandidate]
            Kandidat SAW yang siap untuk diranking.
        """
        candidates: list[SAWCandidate] = []

        for profile in profiles:
            skill_score = skill_score_map.get(profile.nip, 0.0)

            candidates.append(
                SAWCandidate(
                    nip=profile.nip,
                    nama_lengkap=profile.nama_lengkap,
                    skill_score=skill_score,
                    ketersediaan=profile.ketersediaan,
                    pendidikan=profile.pendidikan,
                    pengalaman_tahun=profile.pengalaman_tahun,
                    lokasi_penempatan=profile.lokasi_penempatan,
                    concern_perbankan=profile.concern_perbankan,
                )
            )

        return candidates
