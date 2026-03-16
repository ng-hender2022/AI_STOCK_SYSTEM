"""
Feature Normalizer
Normalizes raw features before feeding to R Layer models.

Categories per AI_STOCK_FEATURE_NORMALIZATION_RULEBOOK:
  A: Oscillators (0..100) → (x-50)/50
  B: Percentiles (0..1) → no change
  C: Returns → z-score rolling 252d
  D: Ratios (right-skewed) → log(1+x)
  E: Distances (% of price) → no change
  F: Binary flags (-1/0/1) → no change
  G: Percent-based (0..1) → no change
  H: Regime/bounded scores → divide by max

Anti-leakage: rolling stats use only past data (up to T-1).
"""

import numpy as np
import pandas as pd

# ──────────────────────────────────────────────────────────────
# Category assignments for every feature
# ──────────────────────────────────────────────────────────────

# Category A: Oscillators, raw 0..100 → (x - 50) / 50
CAT_A_100 = {
    "v4adx_value",
    "v4adx_di_plus",
    "v4adx_di_minus",
    "v4atr_percentile",
    "v4br_pct_above_ma50",
}

# Category A variant: Oscillators, raw 0..1 → (x - 0.5) / 0.5
CAT_A_01 = {
    "v4sto_k",
    "v4sto_d",
}

# Category C: Returns → z-score rolling 252d
CAT_C = {
    "v4p_ret_1d",
    "v4p_ret_5d",
    "v4p_ret_10d",
    "v4p_ret_20d",
    "v4p_gap_ret",
    "v4rs_5d",
    "v4rs_20d",
    "v4rs_acceleration",
    "v4s_sector_ret_20d",
    "v4s_sector_vs_market",
    "v4s_sector_momentum",
    "sector_momentum",       # meta feature
    "v4rsi_slope",
    "v4macd_hist_slope",
    "v4v_volume_trend",
    "v4obv_slope",
    "v4ma_slope_20",
    "v4ma_slope_50",
    "v4ma_slope_200",
    "v4br_new_high_low_ratio",
}

# Category D: Ratios → log(1 + x), input must be >= 0
CAT_D = {
    "v4v_volume_ratio_20",
    "v4liq_liquidity_shock",
    "v4liq_turnover_ratio",
    "v4liq_avg_vol_20",
    "v4atr_vol_compression",
    "v4atr_pct",
    "v4tp_breakout_vol_ratio",
    "v4bb_width",
    "volume_pressure",       # meta feature
    "liquidity_shock_avg",   # meta feature
}

# Category E: Distances (already % of price) → no change
CAT_E = {
    "v4ma_dist_ma20",
    "v4ma_dist_ma50",
    "v4ma_dist_ma100",
    "v4ma_dist_ma200",
    "v4sr_dist_support",
    "v4sr_dist_resistance",
    "v4tp_pattern_completion",
}

# Category F: Binary flags → no change
CAT_F = {
    "v4rsi_divergence_flag",
    "v4rsi_center_cross_flag",
    "v4macd_cross_flag",
    "v4macd_divergence_flag",
    "v4bb_squeeze_flag",
    "v4bb_band_walk_flag",
    "v4v_climax_volume_flag",
    "v4v_drying_volume_flag",
    "v4v_expansion_flag",
    "v4p_breakout20_flag",
    "v4p_breakout60_flag",
    "v4sto_cross_flag",
    "v4sto_divergence_flag",
    "v4obv_divergence_flag",
    "v4obv_breakout_flag",
    "v4atr_expanding_flag",
    "v4candle_volume_confirm",
    "v4br_pos_divergence",
    "v4br_neg_divergence",
    "v4ma_golden_cross_flag",
    "v4ma_death_cross_flag",
    "v4sr_breakout_flag",
    "v4tp_breakout_confirmed",
    "v4tp_pattern_failure",
}

# Category G: Percent-based (0..1) → no change
CAT_G = {
    "v4bb_position",
    "v4p_range_position",
    "v4p_trend_persistence",
    "v4candle_body_pct",
    "v4candle_upper_wick_pct",
    "v4candle_lower_wick_pct",
    "v4br_ad_ratio",
    "v4rs_rank",
    "v4i_time_resonance",
    "expert_conflict_score",
    "expert_alignment_score",
    "trend_alignment_score",
    "trend_strength_max",
    "ma_alignment_pct",
    "trend_persistence_avg",
    "bull_bear_ratio",
}

# Category H: Bounded scores → divide by max value
# Format: feature_name → divisor
CAT_H = {
    # Expert norms are already -1..+1, no change needed
    # Ichimoku sub-scores
    "v4i_cloud_position_score": 2.0,    # -2..+2
    "v4i_tk_signal_score": 1.0,         # -1..+1 (already)
    "v4i_chikou_confirm_score": 1.0,    # -1..+1 (already)
    "v4i_future_cloud_score": 1.0,      # -1..+1 (already)
    # MA
    "v4ma_alignment_score": 3.0,        # -3..+3
    # ADX
    "v4adx_di_spread": 100.0,           # -100..+100
    # Pivot
    "v4pivot_confluence_score": 1.0,     # -1..+1 (already)
    "v4pivot_position_score": 2.0,      # -2..+2
    "v4pivot_alignment_score": 1.0,     # -1..+1 (already)
    # SR
    "v4sr_strength": 1.0,              # 0..1 (already)
    # Sector rank → centered and scaled
    "v4s_sector_rank": 7.0,            # 1..14, will center first
    # Regime
    "regime_score": 4.0,               # -4..+4
    # Meta group scores (already -1..+1 from norm averaging)
    "avg_score": 1.0,
    "trend_group_score": 1.0,
    "momentum_group_score": 1.0,
    "volume_group_score": 1.0,
    "volatility_group_score": 1.0,
    "structure_group_score": 1.0,
    "context_group_score": 1.0,
}

# Category H-count: Integer counts → divide by max
CAT_H_COUNT = {
    "bullish_expert_count": 20.0,
    "bearish_expert_count": 20.0,
    "momentum_divergence_count": 3.0,
    "overbought_count": 2.0,
    "oversold_count": 2.0,
    "climax_volume_count": 1.0,
    "compression_count": 2.0,
    "breakout_count": 3.0,
}

# Expert norms — already normalized -1..+1, no change
EXPERT_NORMS = {col for col in [
    "v4i_norm", "v4ma_norm", "v4adx_norm", "v4macd_norm", "v4rsi_norm",
    "v4sto_norm", "v4v_norm", "v4obv_norm", "v4atr_norm", "v4bb_norm",
    "v4p_norm", "v4candle_norm", "v4br_norm", "v4rs_norm", "v4s_norm",
    "v4liq_norm", "v4pivot_norm", "v4sr_norm", "v4trend_pattern_norm",
]}

# All passthrough features (no normalization needed)
NO_CHANGE = CAT_E | CAT_F | CAT_G | EXPERT_NORMS

# Z-score rolling window
ZSCORE_WINDOW = 252
ZSCORE_MIN_PERIODS = 20


class FeatureNormalizer:
    """
    Normalize feature matrix per AI_STOCK_FEATURE_NORMALIZATION_RULEBOOK.

    Usage:
        normalizer = FeatureNormalizer()
        X_norm = normalizer.normalize(X, dates)

    Anti-leakage: z-score uses expanding/rolling window on sorted dates,
    computed per-symbol using only past data.
    """

    def normalize(self, df: pd.DataFrame, date_col: str = "date",
                  symbol_col: str = "symbol") -> pd.DataFrame:
        """
        Normalize all feature columns in-place.

        Args:
            df: DataFrame with columns: symbol, date, + feature columns.
                Must be sorted by date for correct rolling z-score.
            date_col: name of date column (excluded from normalization)
            symbol_col: name of symbol column (excluded from normalization)

        Returns:
            Normalized DataFrame (copy, original not modified).
        """
        if df.empty:
            return df.copy()

        result = df.copy()

        # Identify feature columns
        non_feature = {date_col, symbol_col, "snapshot_time", "created_at",
                       "feature_date", "close_t", "target_return", "target_label"}
        feature_cols = [c for c in result.columns if c not in non_feature]

        # Sort by date for correct rolling computation
        if date_col in result.columns:
            result = result.sort_values([date_col, symbol_col]).reset_index(drop=True)

        for col in feature_cols:
            if col not in result.columns:
                continue

            if col in NO_CHANGE:
                # Already normalized
                continue

            elif col in CAT_A_100:
                # Oscillators 0..100 → (x - 50) / 50
                result[col] = (result[col] - 50.0) / 50.0

            elif col in CAT_A_01:
                # Oscillators 0..1 → (x - 0.5) / 0.5
                result[col] = (result[col] - 0.5) / 0.5

            elif col in CAT_C:
                # Returns → z-score rolling 252d per symbol
                result[col] = self._rolling_zscore(
                    result, col, date_col, symbol_col
                )

            elif col in CAT_D:
                # Ratios → log(1 + x), clamp x >= 0
                result[col] = np.log1p(result[col].clip(lower=0.0))

            elif col in CAT_H:
                divisor = CAT_H[col]
                if col == "v4s_sector_rank":
                    # Center first: 1..14 → centered at 7.5, then /7
                    result[col] = (result[col] - 7.5) / 7.0
                elif divisor != 1.0:
                    result[col] = result[col] / divisor

            elif col in CAT_H_COUNT:
                divisor = CAT_H_COUNT[col]
                result[col] = result[col] / divisor

            # else: unknown feature, leave as-is (norm scores, etc.)

        # Final validation
        self._validate(result, feature_cols)

        return result

    def _rolling_zscore(
        self, df: pd.DataFrame, col: str,
        date_col: str, symbol_col: str,
    ) -> pd.Series:
        """
        Compute rolling z-score per symbol using only past data.
        Uses expanding window with min_periods for early dates,
        capped at ZSCORE_WINDOW lookback.

        Anti-leakage: for row at index i, stats use only rows 0..i-1.
        """
        result = pd.Series(0.0, index=df.index, dtype=float)

        if symbol_col not in df.columns:
            # No symbol column, compute globally
            shifted = df[col].shift(1)  # exclude current row
            roll_mean = shifted.expanding(min_periods=ZSCORE_MIN_PERIODS).mean()
            roll_std = shifted.expanding(min_periods=ZSCORE_MIN_PERIODS).std()
            roll_std = roll_std.clip(lower=1e-8)
            result = (df[col] - roll_mean) / roll_std
            return result.clip(-5, 5).fillna(0.0)

        for sym, group in df.groupby(symbol_col):
            idx = group.index
            vals = group[col].values.astype(float)
            n = len(vals)
            zscores = np.zeros(n, dtype=float)

            # Use expanding window with past-only data
            for i in range(n):
                if i < ZSCORE_MIN_PERIODS:
                    zscores[i] = 0.0  # insufficient history
                    continue
                # Window: last ZSCORE_WINDOW values before current
                start = max(0, i - ZSCORE_WINDOW)
                window = vals[start:i]  # excludes current (anti-leakage)
                mean = np.mean(window)
                std = np.std(window, ddof=1)
                if std < 1e-8:
                    zscores[i] = 0.0
                else:
                    zscores[i] = (vals[i] - mean) / std

            result.iloc[idx] = np.clip(zscores, -5, 5)

        return result.fillna(0.0)

    def _validate(self, df: pd.DataFrame, feature_cols: list[str]) -> None:
        """Validate: no NaN, no inf, range sanity."""
        for col in feature_cols:
            if col not in df.columns:
                continue
            series = df[col]

            # Replace NaN/inf with 0
            mask_nan = series.isna()
            mask_inf = np.isinf(series.values) if series.dtype != object else pd.Series(False, index=series.index)
            bad = mask_nan | mask_inf
            if bad.any():
                df[col] = series.where(~bad, 0.0)

    def get_category(self, feature_name: str) -> str:
        """Return the normalization category for a feature (for documentation)."""
        if feature_name in EXPERT_NORMS:
            return "NORM (already -1..+1)"
        if feature_name in CAT_A_100:
            return "A (oscillator 0..100 → -1..+1)"
        if feature_name in CAT_A_01:
            return "A (oscillator 0..1 → -1..+1)"
        if feature_name in CAT_C:
            return "C (return → z-score rolling 252d)"
        if feature_name in CAT_D:
            return "D (ratio → log(1+x))"
        if feature_name in CAT_E:
            return "E (distance → no change)"
        if feature_name in CAT_F:
            return "F (binary flag → no change)"
        if feature_name in CAT_G:
            return "G (percent 0..1 → no change)"
        if feature_name in CAT_H:
            return f"H (bounded → /{CAT_H[feature_name]})"
        if feature_name in CAT_H_COUNT:
            return f"H (count → /{CAT_H_COUNT[feature_name]})"
        return "PASSTHROUGH"
