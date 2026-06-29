# =============================================================
# src/api/routes/recommendations.py
# Endpoint FastAPI untuk rekomendasi talenta end-to-end
#
# POST /recommendations
#   Input : kalimat natural dari pengguna (query)
#   Output: RecommendationResult (top 5 talenta + constraint labels)
#
# Alur (sesuai Root Sequence Diagram):
#   1. NERExtractor.extract(query)          → ExtractionResult
#   2. SemanticSimilarityService.rank_talents(skills) → list[TalentSkillScore]
#   3. _build_saw_request(extraction, scores)         → SAWRankRequest
#   4. SAWService.rank(saw_request)          → RecommendationResult
#
# Dependency Injection:
#   Ketiga service diinisialisasi sekali di lifespan (main.py) dan
#   disimpan di app.state. FastAPI menyuntikkannya sebagai parameter
#   fungsi per-request via Depends() — parameter visibility, bukan
#   attribute visibility.
# =============================================================

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from loguru import logger
from pydantic import BaseModel, Field

from src.core.ollama_client import OllamaConnectionError, OllamaResponseError
from src.modules.ner.extractor import NERExtractor
from src.modules.ner.schemas import ExtractionResult
from src.modules.semantic_similarity.similarity_service import SemanticSimilarityService
from src.modules.semantic_similarity.matcher import TalentSkillScore
from src.modules.saw.saw_service import SAWService
from src.modules.saw.schemas import (
    SAWRankRequest,
    TalentScoreInput,
    RecommendationResult,
)

router = APIRouter(prefix="/recommendation-talent", tags=["Recommendations"])


# Request Schema

class RecommendationRequest(BaseModel):
    """Body request untuk endpoint rekomendasi talenta end-to-end."""

    query: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="Kalimat kebutuhan talenta dari Tim Sales / Tim TD.",
        examples=["Butuh senior React.js min 3 tahun di Bandung, proyek perbankan"],
    )


# Dependency Providers

def _get_ner_extractor(request: Request) -> NERExtractor:
    """
    Mengambil instance NERExtractor singleton dari app.state.
    Diinisialisasi sekali saat startup di lifespan main.py.
    """
    extractor = getattr(request.app.state, "ner_extractor", None)
    if extractor is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="NER extractor belum diinisialisasi.",
        )
    return extractor


def _get_similarity_service(request: Request) -> SemanticSimilarityService:
    """
    Mengambil instance SemanticSimilarityService singleton dari app.state.
    Objek berat ini diinisialisasi sekali dan memuat knowledge graph ke memori.
    """
    service = getattr(request.app.state, "similarity_service", None)
    if service is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Semantic similarity service belum diinisialisasi.",
        )
    return service


def _get_saw_service(request: Request) -> SAWService:
    """
    Mengambil instance SAWService singleton dari app.state.
    Diinisialisasi sekali saat startup bersama TalentRepository-nya.
    """
    service = getattr(request.app.state, "saw_service", None)
    if service is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="SAW service belum diinisialisasi.",
        )
    return service


#  Helper

def _build_saw_request(
    extraction: ExtractionResult,
    scores: list[TalentSkillScore],
) -> SAWRankRequest:
    """
    Merakit SAWRankRequest dari output NER + output Semantic Similarity.

    Sesuai Root SD — RR memanggil dirinya sendiri untuk menggabungkan:
      - talent_scores  : slim projection dari TalentSkillScore → TalentScoreInput
      - location       : dari ExtractionResult.location
      - is_banking_project: dari ExtractionResult.is_banking_project
      - education      : dari ExtractionResult.education
    """
    talent_scores = [
        TalentScoreInput(
            nip=s.nip,
            nama_lengkap=s.nama_lengkap,
            skill_score=s.skill_score,
            skills=s.talent_skills,
            match_details=[
                {
                    "required_skill": d.required_skill,
                    "best_match_skill": d.best_match_skill,
                    "similarity_score": d.similarity_score,
                }
                for d in s.match_details
            ],
        )
        for s in scores
    ]
    return SAWRankRequest(
        talent_scores=talent_scores,
        location=extraction.location,
        is_banking_project=extraction.is_banking_project,
        education=extraction.education,
    )


# Endpoint untuk rekomendasi talenta end-to-end

@router.post(
    "",
    response_model=RecommendationResult,
    status_code=status.HTTP_200_OK,
    summary="Rekomendasi talenta end-to-end",
    description=(
        "Menerima kalimat natural kebutuhan talenta, lalu secara otomatis "
        "menjalankan seluruh pipeline: ekstraksi entitas (NER), perhitungan "
        "kemiripan semantik skill, dan perankingan multi-kriteria SAW. "
        "Mengembalikan top 5 talenta yang direkomendasikan."
    ),
)
async def recommend(
    body: RecommendationRequest,
    # Dependency Injection via app.state + Depends()
    ner_extractor: NERExtractor = Depends(_get_ner_extractor),
    similarity_service: SemanticSimilarityService = Depends(_get_similarity_service),
    saw_service: SAWService = Depends(_get_saw_service),
) -> RecommendationResult:
    """
    Endpoint utama rekomendasi talenta — UC-REC-01.

    Mengikuti alur Root Sequence Diagram secara literal:
      RR → NE: extract(query)
      RR → SIM: rank_talents(skills)
      RR → RR: _build_saw_request(extraction, scores)
      RR → SAW: rank(saw_request)
    """
    logger.info(f"POST /recommendations/query — query='{body.query}'")

    # RR → NE: extract(query)
    try:
        extraction: ExtractionResult = await ner_extractor.extract(body.query)
    except OllamaConnectionError as exc:
        logger.error(f"Ollama tidak dapat dijangkau | {exc}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Layanan Ollama tidak dapat dijangkau. Pastikan VPN aktif dan coba lagi.",
        )
    except OllamaResponseError as exc:
        logger.error(f"Respons Ollama tidak valid | {exc}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Respons dari Ollama tidak dapat diproses.",
        )
    except ValueError as exc:
        logger.error(f"Parsing respons NER gagal | {exc}")
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Gagal memproses respons NER: {exc}",
        )

    logger.info(
        f"NER selesai | skills={extraction.skills} "
        f"location={extraction.location} education={extraction.education}"
    )

    # RR → SIM: rank_talents(ExtractionResult.skills)
    try:
        scores, _ = similarity_service.rank_talents(
            extraction.skills
        )
    except Exception as exc:
        logger.exception("Semantic similarity ranking gagal.")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Semantic similarity error: {exc}",
        )

    logger.info(f"Semantic selesai | {len(scores)} talenta diranking.")

    if not scores:
        logger.warning("Tidak ada kandidat dari modul Semantic yang memenuhi threshold (scores kosong). Melewati tahap SAW.")
        return RecommendationResult(
            message=(
                "Tidak ditemukan talenta yang memenuhi kriteria skill tersebut "
                "(atau skill tidak terdaftar di sistem dengan tingkat kemiripan yang cukup)."
            ),
            top_talents=[],
            other_talents=[],
            has_more=False,
            total_candidates=0,
        )

    # RR → RR: _build_saw_request(...)
    saw_request: SAWRankRequest = _build_saw_request(extraction, scores)

    logger.info(
        f"SAWRankRequest dibangun | "
        f"{len(saw_request.talent_scores)} talent_scores, "
        f"location={saw_request.location}, "
        f"banking={saw_request.is_banking_project}, "
        f"education={saw_request.education}"
    )

    # RR → SAW: rank(SAWRankRequest) 
    try:
        result: RecommendationResult = saw_service.rank(saw_request)
    except Exception as exc:
        logger.exception("SAW ranking gagal.")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"SAW ranking error: {exc}",
        )

    logger.info(
        f"Rekomendasi selesai | total={result.total_candidates} "
        f"top={len(result.top_talents)}"
    )
    return result
