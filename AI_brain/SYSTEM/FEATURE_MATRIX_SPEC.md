# FEATURE MATRIX SPECIFICATION

Version: 2.1
Date: 2026-03-16
Status: ACTIVE | Normalization: feature_normalizer.py integrated

---

## PURPOSE

Defines the complete feature matrix that feeds into R Layer (R0-R5).
Each row = 1 symbol x 1 date. Columns = all expert sub-features + meta features + regime features.

---

## CURRENT FEATURE COUNT

| Source | Features | Status |
|---|---|---|
| Expert norm scores (1 per expert x 20) | 20 | BUILT |
| Expert sub-features (non-norm) | 85 | BUILT |
| Meta features | 25 | BUILT |
| Regime features (from market_regime) | 3 | BUILT |
| **Total** | **133** | **ALL BUILT** |

---

## R LAYER INPUT: FEATURE VECTOR

| Component | Count | Description |
|---|---|---|
| Expert norm scores | 20 | 1 per expert: `{expert}_norm` (-1..+1) |
| Expert sub-features | 85 | Flags, ratios, slopes extracted from metadata_json |
| Meta features | 25 | Group scores, alignment, conflict, counts |
| Regime features | 3 | regime_trend, regime_vol, regime_liq |
| **Total R Layer input** | **133** | |

---

## COMPLETE FEATURE LIST (133)

### V4RSI (4 sub-features)

| Column | Type | Range |
|---|---|---|
| v4rsi_norm | float | -1..+1 |
| v4rsi_slope | float | unbounded |
| v4rsi_divergence_flag | int | -1/0/+1 |
| v4rsi_center_cross_flag | int | -1/0/+1 |

### V4MACD (4 sub-features)

| Column | Type | Range |
|---|---|---|
| v4macd_norm | float | -1..+1 |
| v4macd_hist_slope | float | unbounded |
| v4macd_cross_flag | int | -1/0/+1 |
| v4macd_divergence_flag | int | -1/0/+1 |

### V4BB (5 sub-features)

| Column | Type | Range |
|---|---|---|
| v4bb_norm | float | -1..+1 |
| v4bb_width | float | 0..+inf |
| v4bb_position | float | 0..1 |
| v4bb_squeeze_flag | int | 0/1 |
| v4bb_band_walk_flag | int | 0/1 |

### V4V (6 sub-features)

| Column | Type | Range |
|---|---|---|
| v4v_norm | float | -1..+1 |
| v4v_volume_ratio_20 | float | 0..+inf |
| v4v_volume_trend | float | unbounded |
| v4v_climax_volume_flag | int | 0/1 |
| v4v_drying_volume_flag | int | 0/1 |
| v4v_expansion_flag | int | 0/1 |

### V4P (10 sub-features)

| Column | Type | Range |
|---|---|---|
| v4p_norm | float | -1..+1 |
| v4p_ret_1d | float | unbounded |
| v4p_ret_5d | float | unbounded |
| v4p_ret_10d | float | unbounded |
| v4p_ret_20d | float | unbounded |
| v4p_breakout20_flag | int | 0/1 |
| v4p_breakout60_flag | int | 0/1 |
| v4p_range_position | float | 0..1 |
| v4p_gap_ret | float | unbounded |
| v4p_trend_persistence | float | 0..1 |

### V4I (6 sub-features)

| Column | Type | Range |
|---|---|---|
| v4i_norm | float | -1..+1 |
| v4i_cloud_position_score | float | -2/0/+2 |
| v4i_tk_signal_score | float | -1/0/+1 |
| v4i_chikou_confirm_score | float | -1/0/+1 |
| v4i_future_cloud_score | float | -1/0/+1 |
| v4i_time_resonance | float | 0..1 |

### V4MA (11 sub-features)

| Column | Type | Range |
|---|---|---|
| v4ma_norm | float | -1..+1 |
| v4ma_alignment_score | float | -3..+3 |
| v4ma_slope_20 | float | ratio |
| v4ma_slope_50 | float | ratio |
| v4ma_slope_200 | float | ratio |
| v4ma_golden_cross_flag | int | 0/1 |
| v4ma_death_cross_flag | int | 0/1 |
| v4ma_dist_ma20 | float | ratio |
| v4ma_dist_ma50 | float | ratio |
| v4ma_dist_ma100 | float | ratio |
| v4ma_dist_ma200 | float | ratio |

### V4ADX (5 sub-features)

| Column | Type | Range |
|---|---|---|
| v4adx_norm | float | -1..+1 |
| v4adx_value | float | 0..100 |
| v4adx_di_plus | float | 0..100 |
| v4adx_di_minus | float | 0..100 |
| v4adx_di_spread | float | -100..+100 |

### V4STO (5 sub-features)

| Column | Type | Range |
|---|---|---|
| v4sto_norm | float | -1..+1 |
| v4sto_k | float | 0..100 |
| v4sto_d | float | 0..100 |
| v4sto_cross_flag | int | -1/0/+1 |
| v4sto_divergence_flag | int | -1/0/+1 |

### V4OBV (4 sub-features)

| Column | Type | Range |
|---|---|---|
| v4obv_norm | float | -1..+1 |
| v4obv_slope | float | unbounded |
| v4obv_divergence_flag | int | -1/0/+1 |
| v4obv_breakout_flag | int | 0/1 |

### V4ATR (5 sub-features)

| Column | Type | Range |
|---|---|---|
| v4atr_norm | float | -1..+1 |
| v4atr_pct | float | 0..+inf |
| v4atr_percentile | float | 0..1 |
| v4atr_vol_compression | float | 0..+inf |
| v4atr_expanding_flag | int | 0/1 |

### V4CANDLE (5 sub-features)

| Column | Type | Range |
|---|---|---|
| v4candle_norm | float | -1..+1 |
| v4candle_body_pct | float | 0..1 |
| v4candle_upper_wick_pct | float | 0..1 |
| v4candle_lower_wick_pct | float | 0..1 |
| v4candle_volume_confirm | float | 0..+inf |

### V4BR (6 sub-features)

| Column | Type | Range |
|---|---|---|
| v4br_norm | float | -1..+1 |
| v4br_pct_above_ma50 | float | 0..1 |
| v4br_ad_ratio | float | unbounded |
| v4br_new_high_low_ratio | float | unbounded |
| v4br_pos_divergence | int | 0/1 |
| v4br_neg_divergence | int | 0/1 |

### V4RS (5 sub-features)

| Column | Type | Range |
|---|---|---|
| v4rs_norm | float | -1..+1 |
| v4rs_5d | float | unbounded |
| v4rs_20d | float | unbounded |
| v4rs_acceleration | float | unbounded |
| v4rs_rank | float | 0..1 |

### V4REG (3 regime features)

| Column | Type | Range |
|---|---|---|
| regime_trend | float | -4..+4 |
| regime_vol | float | 0..4 |
| regime_liq | float | -2..+2 |

### V4S (5 sub-features)

| Column | Type | Range |
|---|---|---|
| v4s_norm | float | -1..+1 |
| v4s_sector_ret_20d | float | unbounded |
| v4s_sector_rank | float | 0..1 |
| v4s_sector_vs_market | float | unbounded |
| v4s_sector_momentum | float | unbounded |

### V4LIQ (4 sub-features)

| Column | Type | Range |
|---|---|---|
| v4liq_norm | float | -1..+1 |
| v4liq_avg_vol_20 | float | 0..+inf |
| v4liq_turnover_ratio | float | 0..+inf |
| v4liq_liquidity_shock | float | 0..+inf |

### V4PIVOT (4 sub-features)

| Column | Type | Range |
|---|---|---|
| v4pivot_norm | float | -1..+1 |
| v4pivot_confluence_score | float | -1..+1 |
| v4pivot_position_score | float | -2..+2 |
| v4pivot_alignment_score | float | -1..+1 |

### V4SR (5 sub-features)

| Column | Type | Range |
|---|---|---|
| v4sr_norm | float | -1..+1 |
| v4sr_dist_support | float | ratio |
| v4sr_dist_resistance | float | ratio |
| v4sr_strength | float | 0..10 |
| v4sr_breakout_flag | int | 0/1 |

### V4TREND_PATTERN (5 sub-features)

| Column | Type | Range |
|---|---|---|
| v4tp_norm | float | -1..+1 |
| v4tp_breakout_confirmed | int | 0/1 |
| v4tp_pattern_completion | float | 0..1 |
| v4tp_breakout_vol_ratio | float | 0..+inf |
| v4tp_pattern_failure | int | 0/1 |

### Meta Features (25)

| Column | Type | Range |
|---|---|---|
| avg_score | float | -1..+1 |
| trend_group_score | float | -1..+1 |
| momentum_group_score | float | -1..+1 |
| volume_group_score | float | -1..+1 |
| volatility_group_score | float | -1..+1 |
| structure_group_score | float | -1..+1 |
| context_group_score | float | -1..+1 |
| expert_conflict_score | float | 0..1 |
| expert_alignment_score | float | 0..1 |
| bullish_count | int | 0..20 |
| bearish_count | int | 0..20 |
| trend_alignment_score | float | -1..+1 |
| trend_strength_max | float | 0..1 |
| ma_alignment_pct | float | 0..1 |
| trend_persistence_avg | float | 0..1 |
| momentum_divergence_count | int | 0..20 |
| overbought_count | int | 0..20 |
| oversold_count | int | 0..20 |
| volume_pressure | float | unbounded |
| liquidity_shock_avg | float | 0..+inf |
| climax_volume_count | int | 0..20 |
| compression_count | int | 0..20 |
| bull_bear_ratio | float | 0..+inf |
| sector_momentum | float | unbounded |
| breakout_count | int | 0..20 |

---

## NORMALIZATION

Version: 2.1. All features are normalized per AI_STOCK_FEATURE_NORMALIZATION_RULEBOOK before R Layer training/prediction.

### Normalization Categories

| Category | Method | Output Range | Features |
|----------|--------|-------------|----------|
| NORM | Already normalized | -1..+1 | All 19 expert `*_norm` scores |
| A (oscillator 0..100) | (x - 50) / 50 | -1..+1 | v4adx_value, v4adx_di_plus, v4adx_di_minus, v4atr_percentile, v4br_pct_above_ma50 |
| A (oscillator 0..1) | (x - 0.5) / 0.5 | -1..+1 | v4sto_k, v4sto_d |
| C (returns) | z-score rolling 252d | -5..+5 | v4p_ret_1d/5d/10d/20d, v4p_gap_ret, v4rs_5d/20d, v4rs_acceleration, v4s_sector_ret_20d, v4s_sector_vs_market, v4s_sector_momentum, sector_momentum, v4rsi_slope, v4macd_hist_slope, v4v_volume_trend, v4obv_slope, v4ma_slope_20/50/200, v4br_new_high_low_ratio |
| D (ratios) | log(1 + x) | 0..+inf | v4v_volume_ratio_20, v4liq_liquidity_shock, v4liq_turnover_ratio, v4liq_avg_vol_20, v4atr_vol_compression, v4atr_pct, v4tp_breakout_vol_ratio, v4bb_width, volume_pressure, liquidity_shock_avg |
| E (distances) | No change (already % of price) | -0.2..+0.2 | v4ma_dist_ma20/50/100/200, v4sr_dist_support/resistance, v4tp_pattern_completion |
| F (binary flags) | No change | -1/0/+1 | All *_flag, *_divergence, *_cross, *_confirmed, *_failure features (24 total) |
| G (percent 0..1) | No change | 0..1 | v4bb_position, v4p_range_position, v4p_trend_persistence, v4candle_body/wick_pct, v4br_ad_ratio, v4rs_rank, v4i_time_resonance, expert_conflict/alignment_score, trend_alignment_score, trend_strength_max, ma_alignment_pct, trend_persistence_avg, bull_bear_ratio |
| H (bounded scores) | Divide by max | -1..+1 | v4i_cloud_position_score(/2), v4ma_alignment_score(/3), v4adx_di_spread(/100), v4pivot_position_score(/2), v4s_sector_rank(centered/7), regime_score(/4), group scores(already -1..+1) |
| H (counts) | Divide by max | 0..1 | bullish/bearish_expert_count(/20), momentum_divergence_count(/3), overbought/oversold_count(/2), compression_count(/2), breakout_count(/3), climax_volume_count(/1) |

### Anti-Leakage Rule for Z-Score

Z-score rolling statistics use **past-only data** (up to T-1). For row at date T, the mean and std are computed from the previous 252 trading days for that symbol. First 20 rows get z-score = 0 (insufficient history).

### Validation

After normalization, the pipeline verifies:
1. No NaN values (replaced with 0)
2. No infinite values (replaced with 0)
3. Z-scores clipped to [-5, +5]
4. All transformations are deterministic and reproducible

---

## DATA LEAKAGE RULE

Feature matrix for date T uses ONLY data up to close of T-1.
See: DATA_LEAKAGE_PREVENTION.md

---

## NAMING CONVENTION

All feature columns follow: `{expert_id_lowercase}_{feature_name}`

Examples:
- `v4rsi_norm`
- `v4ma_dist_ma100`
- `v4atr_vol_compression`

Exceptions:
- Regime features use bare names: `regime_trend`, `regime_vol`, `regime_liq`
- Meta features use bare names: `avg_score`, `trend_group_score`, etc.

---

## STORAGE

Sub-features are stored inside `metadata_json` in `expert_signals` and extracted
at query time by `SUB_FEATURE_MAP` (defined in `base_model.py`).

Sources:
- `signals.db -> expert_signals` (per-symbol features in metadata_json)
- `market.db -> market_regime` (market-wide regime features)

The feature matrix is assembled at query time from these sources.
Future: may materialize into a dedicated `feature_matrix` table for performance.

---

*Update this document when adding new expert features.*
*See EXPERT_FEATURE_OWNERSHIP.md for detailed feature-to-expert mapping.*
