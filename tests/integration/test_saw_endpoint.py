# =============================================================
# tests/integration/test_saw_endpoint.py
# WB-SAW-05 — POST /saw/rank endpoint (hybrid gray-box)
#
# Strategi: TestClient dengan minimal FastAPI app (hanya SAW router),
# driver di-inject via app.state tanpa lifespan Neo4j/Ollama.
# Driver Neo4j di-mock sehingga tidak memerlukan database nyata.
#
# Titik keputusan kritis:
#   - 503 jika neo4j_driver belum diinisialisasi
#   - 200 + schema RecommendationResult yang valid jika driver tersedia
#   - Integrasi SAWService ↔ TalentRepository ↔ endpoint routing
# =============================================================

from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.routes.saw import router as saw_router


# ----------------------------------------------------------
# Fixtures
# ----------------------------------------------------------

@pytest.fixture(scope="module")
def test_app() -> FastAPI:
    """Minimal FastAPI app dengan hanya SAW router (tanpa lifespan)."""
    app = FastAPI()
    app.include_router(saw_router)
    return app


@pytest.fixture
def client_no_driver(test_app):
    """Client tanpa Neo4j driver → endpoint harus return 503."""
    test_app.state.neo4j_driver = None
    return TestClient(test_app, raise_server_exceptions=False)


@pytest.fixture
def client_with_driver(test_app):
    """
    Client dengan mock Neo4j driver.
    Session di-mock agar TalentRepository.get_by_nips() mengembalikan
    satu profil talenta tanpa koneksi database nyata.
    """
    mock_driver = MagicMock()

    # Representasi satu record dari Neo4j
    record_data = {
        "nip": "001",
        "nama_lengkap": "Andi Saputra",
        "ketersediaan": "idle",
        "pendidikan": "S1",
        "pengalaman_tahun": 3.0,
        "concern_perbankan": False,
        "lokasi_penempatan": ["Bandung"],
    }

    class FakeRecord:
        def __getitem__(self, key):
            return record_data[key]

    mock_session = MagicMock()
    mock_session.run.return_value = [FakeRecord()]
    mock_driver.session.return_value.__enter__ = MagicMock(return_value=mock_session)
    mock_driver.session.return_value.__exit__ = MagicMock(return_value=False)

    test_app.state.neo4j_driver = mock_driver
    return TestClient(test_app, raise_server_exceptions=False)


_VALID_PAYLOAD = {
    "talent_scores": [
        {"nip": "001", "nama_lengkap": "Andi Saputra", "skill_score": 0.85, "skills": ["Python"]}
    ],
    "location": "Bandung",
    "is_banking_project": False,
    "education": None,
}


# ----------------------------------------------------------
# Tests — 503 tanpa driver
# ----------------------------------------------------------

class TestSAWEndpointNoDriver:
    def test_returns_503_when_driver_none(self, client_no_driver):
        response = client_no_driver.post("/saw/rank", json=_VALID_PAYLOAD)
        assert response.status_code == 503

    def test_error_detail_mentions_neo4j(self, client_no_driver):
        response = client_no_driver.post("/saw/rank", json=_VALID_PAYLOAD)
        body = response.json()
        assert "detail" in body


# ----------------------------------------------------------
# Tests — 200 dengan driver (mock)
# ----------------------------------------------------------

class TestSAWEndpointWithDriver:
    def test_returns_200_ok(self, client_with_driver):
        response = client_with_driver.post("/saw/rank", json=_VALID_PAYLOAD)
        assert response.status_code == 200

    def test_response_contains_recommendation_result_fields(self, client_with_driver):
        response = client_with_driver.post("/saw/rank", json=_VALID_PAYLOAD)
        data = response.json()
        assert "top_talents" in data
        assert "other_talents" in data
        assert "has_more" in data
        assert "total_candidates" in data

    def test_single_valid_talent_appears_in_top_talents(self, client_with_driver):
        response = client_with_driver.post("/saw/rank", json=_VALID_PAYLOAD)
        data = response.json()
        assert data["total_candidates"] == 1
        assert len(data["top_talents"]) == 1
        assert data["top_talents"][0]["nip"] == "001"

    def test_talent_has_score_breakdown(self, client_with_driver):
        response = client_with_driver.post("/saw/rank", json=_VALID_PAYLOAD)
        top = response.json()["top_talents"][0]
        assert "score_breakdown" in top
        assert isinstance(top["score_breakdown"], dict)
        assert "ketersediaan" in top["score_breakdown"]

    def test_final_score_between_0_and_1(self, client_with_driver):
        response = client_with_driver.post("/saw/rank", json=_VALID_PAYLOAD)
        top = response.json()["top_talents"][0]
        assert 0.0 <= top["final_score"] <= 1.0

    def test_with_education_query_includes_pendidikan_in_breakdown(self, client_with_driver):
        payload = {**_VALID_PAYLOAD, "education": ["S1"]}
        response = client_with_driver.post("/saw/rank", json=payload)
        top = response.json()["top_talents"][0]
        assert "pendidikan" in top["score_breakdown"]

    def test_invalid_body_returns_422(self, client_with_driver):
        response = client_with_driver.post("/saw/rank", json={"bad": "data"})
        assert response.status_code == 422
