# EXPERT FEATURE OWNERSHIP

Version: 2.0
Date: 2026-03-16
Status: ACTIVE

---

## PURPOSE

Maps every feature to its owning expert.
R Layer and Meta Layer use this to know which expert produces which features.

Each expert stores its full output in `metadata_json`. The sub-features listed
below are the columns extracted from `metadata_json` into the feature matrix
(defined by `SUB_FEATURE_MAP` in `base_model.py`).

---

## V4RSI — Relative Strength Index Expert

**Status: BUILT**

| Sub-Feature (matrix column) | Type | Range |
|---|---|---|
| v4rsi_norm | float | -1..+1 |
| v4rsi_slope | float | unbounded |
| v4rsi_divergence_flag | int | -1/0/+1 |
| v4rsi_center_cross_flag | int | -1/0/+1 |

**Metadata extras:** centerline_cross (int, -1/0/+1)

**Sub-features extracted: 4**

---

## V4MACD — MACD Expert

**Status: BUILT**

| Sub-Feature (matrix column) | Type | Range |
|---|---|---|
| v4macd_norm | float | -1..+1 |
| v4macd_hist_slope | float | unbounded |
| v4macd_cross_flag | int | -1/0/+1 |
| v4macd_divergence_flag | int | -1/0/+1 |

**Metadata extras:** macd_cross_flag (int, -1/0/+1)

**Sub-features extracted: 4**

---

## V4BB — Bollinger Bands Expert

**Status: BUILT**

| Sub-Feature (matrix column) | Type | Range |
|---|---|---|
| v4bb_norm | float | -1..+1 |
| v4bb_width | float | 0..+inf |
| v4bb_position | float | 0..1 |
| v4bb_squeeze_flag | int | 0/1 |
| v4bb_band_walk_flag | int | 0/1 |

**Sub-features extracted: 5**

---

## V4V — Volume Expert

**Status: BUILT**

| Sub-Feature (matrix column) | Type | Range |
|---|---|---|
| v4v_norm | float | -1..+1 |
| v4v_volume_ratio_20 | float | 0..+inf |
| v4v_volume_trend | float | unbounded |
| v4v_climax_volume_flag | int | 0/1 |
| v4v_drying_volume_flag | int | 0/1 |
| v4v_expansion_flag | int | 0/1 |

**Sub-features extracted: 6**

---

## V4P — Price Expert

**Status: BUILT**

| Sub-Feature (matrix column) | Type | Range |
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

**Metadata extras:** trend_persistence (float, 0..1), ret_1d/5d/10d/20d (float), gap_ret (float), breakout60_flag (int 0/1)

**Sub-features extracted: 10**

---

## V4I — Ichimoku Expert

**Status: BUILT**

| Sub-Feature (matrix column) | Type | Range |
|---|---|---|
| v4i_norm | float | -1..+1 |
| v4i_cloud_position_score | float | -2/0/+2 |
| v4i_tk_signal_score | float | -1/0/+1 |
| v4i_chikou_confirm_score | float | -1/0/+1 |
| v4i_future_cloud_score | float | -1/0/+1 |
| v4i_time_resonance | float | 0..1 |

**Sub-features extracted: 6**

---

## V4MA — Moving Average Expert

**Status: BUILT**

| Sub-Feature (matrix column) | Type | Range |
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

**Sub-features extracted: 11**

---

## V4ADX — Average Directional Index Expert

**Status: BUILT**

| Sub-Feature (matrix column) | Type | Range |
|---|---|---|
| v4adx_norm | float | -1..+1 |
| v4adx_value | float | 0..100 |
| v4adx_di_plus | float | 0..100 |
| v4adx_di_minus | float | 0..100 |
| v4adx_di_spread | float | -100..+100 |

**Sub-features extracted: 5**

---

## V4STO — Stochastic Expert

**Status: BUILT**

| Sub-Feature (matrix column) | Type | Range |
|---|---|---|
| v4sto_norm | float | -1..+1 |
| v4sto_k | float | 0..100 |
| v4sto_d | float | 0..100 |
| v4sto_cross_flag | int | -1/0/+1 |
| v4sto_divergence_flag | int | -1/0/+1 |

**Sub-features extracted: 5**

---

## V4OBV — On-Balance Volume Expert

**Status: BUILT**

| Sub-Feature (matrix column) | Type | Range |
|---|---|---|
| v4obv_norm | float | -1..+1 |
| v4obv_slope | float | unbounded |
| v4obv_divergence_flag | int | -1/0/+1 |
| v4obv_breakout_flag | int | 0/1 |

**Sub-features extracted: 4**

---

## V4ATR — Average True Range Expert

**Status: BUILT**

| Sub-Feature (matrix column) | Type | Range |
|---|---|---|
| v4atr_norm | float | -1..+1 |
| v4atr_pct | float | 0..+inf |
| v4atr_percentile | float | 0..1 |
| v4atr_vol_compression | float | 0..+inf |
| v4atr_expanding_flag | int | 0/1 |

**Metadata extras:** volatility_compression (float, 0..+inf, ratio of 5d/20d return std)

**Sub-features extracted: 5**

---

## V4CANDLE — Candlestick Expert

**Status: BUILT**

| Sub-Feature (matrix column) | Type | Range |
|---|---|---|
| v4candle_norm | float | -1..+1 |
| v4candle_body_pct | float | 0..1 |
| v4candle_upper_wick_pct | float | 0..1 |
| v4candle_lower_wick_pct | float | 0..1 |
| v4candle_volume_confirm | float | 0..+inf |

**Sub-features extracted: 5**

---

## V4BR — Breadth Expert

**Status: BUILT**

| Sub-Feature (matrix column) | Type | Range |
|---|---|---|
| v4br_norm | float | -1..+1 |
| v4br_pct_above_ma50 | float | 0..1 |
| v4br_ad_ratio | float | unbounded |
| v4br_new_high_low_ratio | float | unbounded |
| v4br_pos_divergence | int | 0/1 |
| v4br_neg_divergence | int | 0/1 |

**Sub-features extracted: 6**

---

## V4RS — Relative Strength Expert

**Status: BUILT**

| Sub-Feature (matrix column) | Type | Range |
|---|---|---|
| v4rs_norm | float | -1..+1 |
| v4rs_5d | float | unbounded |
| v4rs_20d | float | unbounded |
| v4rs_acceleration | float | unbounded |
| v4rs_rank | float | 0..1 |

**Sub-features extracted: 5**

---

## V4REG — Market Regime Expert

**Status: BUILT**

Features stored in `market_regime` table (market-wide, same for all symbols on a given date).

| Sub-Feature (matrix column) | Type | Range |
|---|---|---|
| regime_trend | float | -4..+4 |
| regime_vol | float | 0..4 |
| regime_liq | float | -2..+2 |

**Sub-features extracted: 3**

---

## V4S — Sector Expert

**Status: BUILT**

| Sub-Feature (matrix column) | Type | Range |
|---|---|---|
| v4s_norm | float | -1..+1 |
| v4s_sector_ret_20d | float | unbounded |
| v4s_sector_rank | float | 0..1 |
| v4s_sector_vs_market | float | unbounded |
| v4s_sector_momentum | float | unbounded |

**Sub-features extracted: 5**

---

## V4LIQ — Liquidity Expert

**Status: BUILT**

| Sub-Feature (matrix column) | Type | Range |
|---|---|---|
| v4liq_norm | float | -1..+1 |
| v4liq_avg_vol_20 | float | 0..+inf |
| v4liq_turnover_ratio | float | 0..+inf |
| v4liq_liquidity_shock | float | 0..+inf |

**Metadata extras:** liquidity_shock (float, ratio of today value / ADTV20)

**Sub-features extracted: 4**

---

## V4PIVOT — Pivot Point Expert

**Status: BUILT**

| Sub-Feature (matrix column) | Type | Range |
|---|---|---|
| v4pivot_norm | float | -1..+1 |
| v4pivot_confluence_score | float | -1..+1 |
| v4pivot_position_score | float | -2..+2 |
| v4pivot_alignment_score | float | -1..+1 |

**Sub-features extracted: 4**

---

## V4SR — Support/Resistance Expert

**Status: BUILT**

| Sub-Feature (matrix column) | Type | Range |
|---|---|---|
| v4sr_norm | float | -1..+1 |
| v4sr_dist_support | float | ratio |
| v4sr_dist_resistance | float | ratio |
| v4sr_strength | float | 0..10 |
| v4sr_breakout_flag | int | 0/1 |

**Sub-features extracted: 5**

---

## V4TREND_PATTERN — Trend Pattern Expert

**Status: BUILT**

| Sub-Feature (matrix column) | Type | Range |
|---|---|---|
| v4tp_norm | float | -1..+1 |
| v4tp_breakout_confirmed | int | 0/1 |
| v4tp_pattern_completion | float | 0..1 |
| v4tp_breakout_vol_ratio | float | 0..+inf |
| v4tp_pattern_failure | int | 0/1 |

**Sub-features extracted: 5**

---

## META FEATURES (25)

Computed by the Meta Layer from expert sub-features. Not owned by any single expert.

| Meta Feature | Type | Range |
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

**Total meta features: 25**

---

## SUMMARY

| Expert | Sub-Features Extracted | Status |
|---|---|---|
| V4RSI | 4 | BUILT |
| V4MACD | 4 | BUILT |
| V4BB | 5 | BUILT |
| V4V | 6 | BUILT |
| V4P | 10 | BUILT |
| V4I | 6 | BUILT |
| V4MA | 11 | BUILT |
| V4ADX | 5 | BUILT |
| V4STO | 5 | BUILT |
| V4OBV | 4 | BUILT |
| V4ATR | 5 | BUILT |
| V4CANDLE | 5 | BUILT |
| V4BR | 6 | BUILT |
| V4RS | 5 | BUILT |
| V4REG | 3 | BUILT |
| V4S | 5 | BUILT |
| V4LIQ | 4 | BUILT |
| V4PIVOT | 4 | BUILT |
| V4SR | 5 | BUILT |
| V4TREND_PATTERN | 5 | BUILT |
| **Norms (1 per expert)** | **20** | |
| **Sub-features (non-norm)** | **85** | |
| **Meta features** | **25** | |
| **Regime features** | **3** | |
| **TOTAL** | **133** | |

---

*This file is the single source of truth for feature ownership.*
*Update when adding/modifying expert features.*
