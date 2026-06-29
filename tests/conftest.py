# =============================================================
# tests/conftest.py
# Shared fixtures untuk seluruh test suite Virgo ReqSys
# =============================================================
from pathlib import Path

import pytest

# Path ke fixture TTL (digunakan oleh test_etl_validator.py)
FIXTURE_TTL = Path(__file__).parent / "fixtures" / "test_ontology.ttl"
