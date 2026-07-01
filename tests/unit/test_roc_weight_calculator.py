# =============================================================
# tests/unit/test_roc_weight_calculator.py
# WB-SAW-01 — ROCWeightCalculator
#
# Titik keputusan kritis:
#   - get_weights(4): nilai dan jumlah bobot benar
#   - get_weights(3): nilai dan jumlah bobot benar
#   - get_weights(n ≠ 3/4): harus raise ValueError
#   - _compute_roc(n): formula konsisten dengan konstanta hardcoded
# =============================================================

import pytest

from src.modules.saw.roc_weight_calculator import ROCWeightCalculator


class TestGetWeights4Criteria:
    def test_returns_four_keys(self):
        w = ROCWeightCalculator.get_weights(4)
        assert set(w.keys()) == {"ketersediaan", "pendidikan", "skill", "pengalaman"}

    def test_ketersediaan_value(self):
        w = ROCWeightCalculator.get_weights(4)
        assert w["ketersediaan"] == pytest.approx(0.5208, abs=1e-4)

    def test_pendidikan_value(self):
        w = ROCWeightCalculator.get_weights(4)
        assert w["pendidikan"] == pytest.approx(0.2708, abs=1e-4)

    def test_skill_value(self):
        w = ROCWeightCalculator.get_weights(4)
        assert w["skill"] == pytest.approx(0.1458, abs=1e-4)

    def test_pengalaman_value(self):
        w = ROCWeightCalculator.get_weights(4)
        assert w["pengalaman"] == pytest.approx(0.0625, abs=1e-4)

    def test_sum_equals_one(self):
        w = ROCWeightCalculator.get_weights(4)
        assert sum(w.values()) == pytest.approx(1.0, abs=1e-4)

    def test_returns_copy_not_reference(self):
        """Modifikasi dict hasil tidak boleh merusak konstanta internal."""
        w = ROCWeightCalculator.get_weights(4)
        w["ketersediaan"] = 99.0
        w2 = ROCWeightCalculator.get_weights(4)
        assert w2["ketersediaan"] == pytest.approx(0.5208, abs=1e-4)


class TestGetWeights3Criteria:
    def test_returns_three_keys(self):
        w = ROCWeightCalculator.get_weights(3)
        assert set(w.keys()) == {"ketersediaan", "skill", "pengalaman"}

    def test_ketersediaan_value(self):
        w = ROCWeightCalculator.get_weights(3)
        assert w["ketersediaan"] == pytest.approx(0.6111, abs=1e-4)

    def test_skill_value(self):
        w = ROCWeightCalculator.get_weights(3)
        assert w["skill"] == pytest.approx(0.2778, abs=1e-4)

    def test_pengalaman_value(self):
        w = ROCWeightCalculator.get_weights(3)
        assert w["pengalaman"] == pytest.approx(0.1111, abs=1e-4)

    def test_sum_equals_one(self):
        w = ROCWeightCalculator.get_weights(3)
        assert sum(w.values()) == pytest.approx(1.0, abs=1e-4)


class TestGetWeightsInvalidInput:
    def test_raises_value_error_for_n_2(self):
        with pytest.raises(ValueError, match="3 atau 4"):
            ROCWeightCalculator.get_weights(2)

    def test_raises_value_error_for_n_5(self):
        with pytest.raises(ValueError):
            ROCWeightCalculator.get_weights(5)

    def test_raises_value_error_for_n_0(self):
        with pytest.raises(ValueError):
            ROCWeightCalculator.get_weights(0)


class TestComputeROC:
    def test_compute_roc_4_consistent_with_hardcoded(self):
        """Formula _compute_roc(4) harus menghasilkan nilai sama dengan konstanta."""
        roc = ROCWeightCalculator._compute_roc(4)
        expected = [0.5208, 0.2708, 0.1458, 0.0625]
        assert len(roc) == 4
        for got, exp in zip(roc, expected):
            assert got == pytest.approx(exp, abs=1e-4)

    def test_compute_roc_3_consistent_with_hardcoded(self):
        roc = ROCWeightCalculator._compute_roc(3)
        expected = [0.6111, 0.2778, 0.1111]
        assert len(roc) == 3
        for got, exp in zip(roc, expected):
            assert got == pytest.approx(exp, abs=1e-4)

    def test_compute_roc_weights_sum_to_1(self):
        for n in (3, 4):
            roc = ROCWeightCalculator._compute_roc(n)
            assert sum(roc) == pytest.approx(1.0, abs=1e-3)
