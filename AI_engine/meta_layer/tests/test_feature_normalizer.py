"""
Tests for FeatureNormalizer.

Validates:
1. No future data leakage in z-score
2. All features in expected range after normalization
3. No NaN/inf in output
4. Category assignments cover all features
"""

import numpy as np
import pandas as pd
import pytest
import sys
sys.path.insert(0, r"D:\AI")

from AI_engine.meta_layer.feature_normalizer import (
    FeatureNormalizer,
    CAT_A_100, CAT_A_01, CAT_C, CAT_D, CAT_E, CAT_F, CAT_G,
    CAT_H, CAT_H_COUNT, EXPERT_NORMS, NO_CHANGE,
)
from AI_engine.r_layer.base_model import SUB_FEATURE_MAP


@pytest.fixture
def normalizer():
    return FeatureNormalizer()


@pytest.fixture
def sample_df():
    """Create a sample DataFrame with all feature categories."""
    np.random.seed(42)
    n = 300  # 300 rows, enough for rolling z-score
    dates = pd.date_range("2024-01-01", periods=n // 3, freq="B")
    symbols = ["FPT", "VNM", "HPG"]

    rows = []
    for d in dates:
        for s in symbols:
            rows.append({"symbol": s, "date": str(d.date())})

    df = pd.DataFrame(rows)

    # Category A (0..100)
    df["v4adx_value"] = np.random.uniform(10, 50, n)
    df["v4adx_di_plus"] = np.random.uniform(10, 40, n)
    df["v4adx_di_minus"] = np.random.uniform(10, 40, n)
    df["v4atr_percentile"] = np.random.uniform(0, 100, n)
    df["v4br_pct_above_ma50"] = np.random.uniform(10, 90, n)

    # Category A (0..1)
    df["v4sto_k"] = np.random.uniform(0, 1, n)
    df["v4sto_d"] = np.random.uniform(0, 1, n)

    # Category C (returns)
    df["v4p_ret_1d"] = np.random.normal(0, 0.02, n)
    df["v4p_ret_5d"] = np.random.normal(0, 0.04, n)
    df["v4rs_5d"] = np.random.normal(0, 0.03, n)
    df["v4macd_hist_slope"] = np.random.normal(0, 0.001, n)

    # Category D (ratios)
    df["v4v_volume_ratio_20"] = np.random.lognormal(0, 0.5, n)
    df["v4liq_liquidity_shock"] = np.random.lognormal(0, 0.3, n)
    df["v4bb_width"] = np.random.uniform(0.02, 0.15, n)

    # Category E (distances)
    df["v4ma_dist_ma20"] = np.random.normal(0, 0.05, n)
    df["v4ma_dist_ma50"] = np.random.normal(0, 0.1, n)

    # Category F (flags)
    df["v4rsi_divergence_flag"] = np.random.choice([-1, 0, 1], n)
    df["v4macd_cross_flag"] = np.random.choice([-1, 0, 1], n)
    df["v4p_breakout20_flag"] = np.random.choice([0, 1], n)

    # Category G (percent 0..1)
    df["v4bb_position"] = np.random.uniform(0, 1, n)
    df["v4p_range_position"] = np.random.uniform(0, 1, n)
    df["v4candle_body_pct"] = np.random.uniform(0, 1, n)

    # Category H (bounded)
    df["v4i_cloud_position_score"] = np.random.choice([-2, -1, 0, 1, 2], n).astype(float)
    df["v4ma_alignment_score"] = np.random.uniform(-3, 3, n)
    df["regime_score"] = np.random.uniform(-4, 4, n)
    df["v4s_sector_rank"] = np.random.uniform(1, 14, n)

    # Category H-count
    df["bullish_expert_count"] = np.random.randint(0, 20, n)
    df["overbought_count"] = np.random.randint(0, 3, n)

    # Expert norms
    df["v4rsi_norm"] = np.random.uniform(-1, 1, n)
    df["v4ma_norm"] = np.random.uniform(-1, 1, n)

    # Meta features
    df["avg_score"] = np.random.uniform(-1, 1, n)
    df["volume_pressure"] = np.random.lognormal(0, 0.3, n)
    df["bull_bear_ratio"] = np.random.uniform(0, 1, n)

    return df


class TestNoFutureLeakage:
    """Test that z-score normalization uses only past data."""

    def test_zscore_uses_past_only(self, normalizer):
        """For each row, z-score should only depend on earlier rows."""
        n = 100
        df = pd.DataFrame({
            "symbol": ["FPT"] * n,
            "date": [f"2024-{i//20+1:02d}-{i%20+1:02d}" for i in range(n)],
            "v4p_ret_1d": np.random.normal(0, 0.02, n),
        })

        result = normalizer.normalize(df)

        # Change future values and re-normalize — past rows should be unchanged
        df2 = df.copy()
        df2.loc[50:, "v4p_ret_1d"] = 999.0  # extreme future values
        result2 = normalizer.normalize(df2)

        # First 50 rows should be identical (they don't see future)
        # Allow tiny float differences
        diff = (result["v4p_ret_1d"].iloc[:50] - result2["v4p_ret_1d"].iloc[:50]).abs()
        assert diff.max() < 1e-10, f"Future data leaked! Max diff: {diff.max()}"

    def test_zscore_insufficient_history_returns_zero(self, normalizer):
        """Early rows with insufficient history should get z-score = 0."""
        df = pd.DataFrame({
            "symbol": ["FPT"] * 30,
            "date": [f"2024-01-{i+1:02d}" for i in range(30)],
            "v4p_ret_1d": np.random.normal(0, 0.02, 30),
        })

        result = normalizer.normalize(df)

        # First ZSCORE_MIN_PERIODS rows should be 0
        from AI_engine.meta_layer.feature_normalizer import ZSCORE_MIN_PERIODS
        assert (result["v4p_ret_1d"].iloc[:ZSCORE_MIN_PERIODS] == 0.0).all()


class TestFeatureRanges:
    """Test that normalized features are in expected ranges."""

    def test_cat_a_range(self, normalizer, sample_df):
        result = normalizer.normalize(sample_df)
        for col in ["v4adx_value", "v4atr_percentile", "v4br_pct_above_ma50"]:
            assert result[col].min() >= -1.0 - 1e-6, f"{col} below -1"
            assert result[col].max() <= 1.0 + 1e-6, f"{col} above +1"

    def test_cat_a_01_range(self, normalizer, sample_df):
        result = normalizer.normalize(sample_df)
        for col in ["v4sto_k", "v4sto_d"]:
            assert result[col].min() >= -1.0 - 1e-6, f"{col} below -1"
            assert result[col].max() <= 1.0 + 1e-6, f"{col} above +1"

    def test_cat_c_zscore_clipped(self, normalizer, sample_df):
        result = normalizer.normalize(sample_df)
        for col in ["v4p_ret_1d", "v4p_ret_5d", "v4rs_5d"]:
            assert result[col].min() >= -5.0 - 1e-6, f"{col} below -5"
            assert result[col].max() <= 5.0 + 1e-6, f"{col} above +5"

    def test_cat_d_non_negative(self, normalizer, sample_df):
        result = normalizer.normalize(sample_df)
        for col in ["v4v_volume_ratio_20", "v4liq_liquidity_shock", "v4bb_width"]:
            assert result[col].min() >= 0.0 - 1e-6, f"{col} below 0 after log"

    def test_cat_f_unchanged(self, normalizer, sample_df):
        result = normalizer.normalize(sample_df)
        for col in ["v4rsi_divergence_flag", "v4macd_cross_flag", "v4p_breakout20_flag"]:
            assert set(result[col].unique()).issubset({-1, 0, 1}), f"{col} has unexpected values"

    def test_cat_h_regime_range(self, normalizer, sample_df):
        result = normalizer.normalize(sample_df)
        assert result["regime_score"].min() >= -1.0 - 1e-6
        assert result["regime_score"].max() <= 1.0 + 1e-6

    def test_cat_h_count_range(self, normalizer, sample_df):
        result = normalizer.normalize(sample_df)
        assert result["bullish_expert_count"].min() >= 0.0 - 1e-6
        assert result["bullish_expert_count"].max() <= 1.0 + 1e-6


class TestNoNaNInf:
    """Test that output has no NaN or inf values."""

    def test_no_nan(self, normalizer, sample_df):
        result = normalizer.normalize(sample_df)
        for col in result.columns:
            if col in ("symbol", "date"):
                continue
            assert not result[col].isna().any(), f"{col} has NaN values"

    def test_no_inf(self, normalizer, sample_df):
        result = normalizer.normalize(sample_df)
        for col in result.columns:
            if col in ("symbol", "date"):
                continue
            if result[col].dtype in (float, np.float64, np.float32):
                assert not np.isinf(result[col].values).any(), f"{col} has inf values"

    def test_handles_zero_std(self, normalizer):
        """Z-score with constant values should not produce NaN."""
        df = pd.DataFrame({
            "symbol": ["FPT"] * 50,
            "date": [f"2024-{i//20+1:02d}-{i%20+1:02d}" for i in range(50)],
            "v4p_ret_1d": [0.01] * 50,  # constant → std=0
        })
        result = normalizer.normalize(df)
        assert not result["v4p_ret_1d"].isna().any()


class TestCategoryCoverage:
    """Test that all features in SUB_FEATURE_MAP have a category assigned."""

    def test_all_sub_features_categorized(self, normalizer):
        """Every sub-feature from SUB_FEATURE_MAP should have a normalization category."""
        all_categorized = (
            CAT_A_100 | CAT_A_01 | CAT_C | CAT_D | CAT_E | CAT_F | CAT_G
            | set(CAT_H.keys()) | set(CAT_H_COUNT.keys()) | EXPERT_NORMS
        )

        uncategorized = []
        for expert_id, features in SUB_FEATURE_MAP.items():
            for _, col_name, _ in features:
                if col_name not in all_categorized:
                    cat = normalizer.get_category(col_name)
                    if cat == "PASSTHROUGH":
                        uncategorized.append(col_name)

        if uncategorized:
            print(f"Uncategorized features: {uncategorized}")
        # Allow some passthrough (expert norms matched by suffix)
        truly_missing = [f for f in uncategorized if not f.endswith("_norm")]
        assert len(truly_missing) == 0, f"Features missing category: {truly_missing}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
