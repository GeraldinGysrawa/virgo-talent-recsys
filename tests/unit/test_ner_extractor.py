# =============================================================
# tests/unit/test_ner_extractor.py
# WB-NER-01 · WB-NER-02 · WB-NER-03 — NERExtractor + ExtractionResult
#
# WB-NER-01: extract() happy path → ExtractionResult dengan semua field benar
# WB-NER-02: ExtractionResult.normalise_skills validator
#             flat array → nested; nested → unchanged; empty → []
# WB-NER-03: Failure paths
#             - JSON tidak valid → ValueError
#             - experience_years_min tidak konvertibel → None
#             - education bukan list → None
#             - education kosong → None
#
# Dependency mock: OllamaClient (AsyncMock) — tidak ada HTTP call nyata.
# =============================================================

from unittest.mock import AsyncMock

import pytest

from src.modules.ner.extractor import NERExtractor
from src.modules.ner.schemas import ExtractionResult


# ----------------------------------------------------------
# Helper — response JSON yang valid dari Ollama
# ----------------------------------------------------------

_VALID_JSON = (
    '{"skills":[["Python"],["PostgreSQL"]],'
    '"experience_years_min":5.0,'
    '"location":"Bandung",'
    '"is_banking_project":true,'
    '"education":["S1"]}'
)


def _make_extractor(raw_response: str) -> NERExtractor:
    mock_client = AsyncMock()
    mock_client.generate.return_value = raw_response
    return NERExtractor(client=mock_client)


# ===========================================================
# WB-NER-01 — extract() happy path
# ===========================================================

class TestExtractHappyPath:
    async def test_returns_extraction_result_instance(self):
        extractor = _make_extractor(_VALID_JSON)
        result = await extractor.extract("butuh Python senior 5 tahun Bandung perbankan")
        assert isinstance(result, ExtractionResult)

    async def test_skills_parsed_correctly(self):
        extractor = _make_extractor(_VALID_JSON)
        result = await extractor.extract("query")
        assert result.skills == [["Python"], ["PostgreSQL"]]


    async def test_experience_parsed_as_float(self):
        extractor = _make_extractor(_VALID_JSON)
        result = await extractor.extract("query")
        assert result.experience_years_min == pytest.approx(5.0)

    async def test_location_parsed(self):
        extractor = _make_extractor(_VALID_JSON)
        result = await extractor.extract("query")
        assert result.location == "Bandung"

    async def test_banking_project_flag(self):
        extractor = _make_extractor(_VALID_JSON)
        result = await extractor.extract("query")
        assert result.is_banking_project is True

    async def test_education_parsed(self):
        extractor = _make_extractor(_VALID_JSON)
        result = await extractor.extract("query")
        assert result.education == ["S1"]

    async def test_query_preserved_in_result(self):
        extractor = _make_extractor(_VALID_JSON)
        query = "butuh developer Python"
        result = await extractor.extract(query)
        assert result.query == query

    async def test_strips_markdown_code_fence(self):
        json_with_fence = f"```json\n{_VALID_JSON}\n```"
        extractor = _make_extractor(json_with_fence)
        result = await extractor.extract("query")
        assert result.skills == [["Python"], ["PostgreSQL"]]

    async def test_strips_plain_code_fence(self):
        json_with_fence = f"```\n{_VALID_JSON}\n```"
        extractor = _make_extractor(json_with_fence)
        result = await extractor.extract("query")
        assert isinstance(result, ExtractionResult)

    async def test_null_fields_become_none(self):
        null_json = (
            '{"skills":[],"experience_years_min":null,'
            '"location":null,"is_banking_project":false,"education":null}'
        )
        extractor = _make_extractor(null_json)
        result = await extractor.extract("ada talent?")
        assert result.experience_years_min is None
        assert result.location is None
        assert result.education is None
        assert result.is_banking_project is False


# ===========================================================
# WB-NER-02 — ExtractionResult.normalise_skills validator
# ===========================================================

class TestNormaliseSkillsValidator:
    def test_nested_array_unchanged(self):
        result = ExtractionResult(query="test", skills=[["Python"], ["React.js"]])
        assert result.skills == [["Python"], ["React.js"]]

    def test_flat_array_wrapped_to_nested(self):
        """LLM mengembalikan flat array → harus dikonversi ke nested AND."""
        result = ExtractionResult(query="test", skills=["Python", "React.js"])
        assert result.skills == [["Python"], ["React.js"]]

    def test_empty_list_returns_empty(self):
        result = ExtractionResult(query="test", skills=[])
        assert result.skills == []

    def test_none_skills_returns_empty(self):
        result = ExtractionResult(query="test", skills=None)
        assert result.skills == []

    def test_mixed_or_group_preserved(self):
        result = ExtractionResult(query="test", skills=[["React.js", "Vue.js"], ["Python"]])
        assert result.skills == [["React.js", "Vue.js"], ["Python"]]

    def test_single_flat_item_wrapped(self):
        result = ExtractionResult(query="test", skills=["Go"])
        assert result.skills == [["Go"]]


# ===========================================================
# WB-NER-03 — NERExtractor failure paths
# ===========================================================

class TestExtractFailurePaths:
    async def test_invalid_json_raises_value_error(self):
        extractor = _make_extractor("ini bukan JSON sama sekali")
        with pytest.raises(ValueError, match="JSON"):
            await extractor.extract("query")

    async def test_partial_json_raises_value_error(self):
        extractor = _make_extractor('{"skills": [["Python"]')  # JSON truncated
        with pytest.raises(ValueError):
            await extractor.extract("query")

    async def test_invalid_experience_string_returns_none(self):
        """LLM mengembalikan experience sebagai string tidak valid → None."""
        invalid_exp = (
            '{"skills":[],"experience_years_min":"lima tahun",'
            '"location":null,"is_banking_project":false,"education":null}'
        )
        extractor = _make_extractor(invalid_exp)
        result = await extractor.extract("query")
        assert result.experience_years_min is None

    async def test_valid_numeric_string_experience_parsed(self):
        """LLM mengembalikan "3" sebagai string → tetap dikonversi ke float."""
        str_exp = (
            '{"skills":[],"experience_years_min":"3",'
            '"location":null,"is_banking_project":false,"education":null}'
        )
        extractor = _make_extractor(str_exp)
        result = await extractor.extract("query")
        assert result.experience_years_min == pytest.approx(3.0)

    async def test_education_not_list_returns_none(self):
        """LLM mengembalikan education sebagai string → None (bukan list)."""
        bad_edu = (
            '{"skills":[],"experience_years_min":null,'
            '"location":null,"is_banking_project":false,"education":"S1"}'
        )
        extractor = _make_extractor(bad_edu)
        result = await extractor.extract("query")
        assert result.education is None

    async def test_empty_education_list_returns_none(self):
        """Education list kosong semantically = tidak disebutkan → None."""
        empty_edu = (
            '{"skills":[],"experience_years_min":null,'
            '"location":null,"is_banking_project":false,"education":[]}'
        )
        extractor = _make_extractor(empty_edu)
        result = await extractor.extract("query")
        assert result.education is None

    async def test_missing_fields_use_defaults(self):
        """JSON valid tapi beberapa field tidak ada → default dari schema."""
        minimal = '{"skills":[],"is_banking_project":false}'
        extractor = _make_extractor(minimal)
        result = await extractor.extract("query")
        assert result.experience_years_min is None
        assert result.location is None
        assert result.education is None
