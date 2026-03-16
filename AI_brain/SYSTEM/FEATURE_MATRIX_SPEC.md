# FEATURE MATRIX SPECIFICATION

Version: 1.0
Date: 2026-03-16
Status: ACTIVE

---

## PURPOSE

Defines the complete feature matrix that feeds into R Layer (R0-R5).
Each row = 1 symbol x 1 date. Columns = all expert features.

---

## CURRENT FEATURE COUNT

| Source | Features | Status |
|---|---|---|
| V4REG (Regime) | 10 | BUILT |
| V4I (Ichimoku) | 14 | BUILT |
| V4MA (Moving Average) | 23 | BUILT |
| V4ADX — V4LIQ (14 experts) | TBD | NOT STARTED |
| V4PIVOT (Pivot Point) | 9 | NOT STARTED |
| V4SR (Support/Resistance) | 11 | NOT STARTED |
| V4TREND_PATTERN (Trend Pattern) | 11 | NOT STARTED |
| **Total (built)** | **47** | |
| **Total (planned, all 20 experts)** | **78+** | |

## R LAYER INPUT: NORMALIZED FEATURE VECTOR

For R Layer, each expert produces a **norm score** (-1..+1):

| Component | Count | Description |
|---|---|---|
| Expert norm scores | 20 | 1 per expert: {expert}_norm = score / 4 |
| Meta features | 11 | Group scores, alignment, conflict, regime |
| Regime scores | 3 | trend_regime, vol_regime, liquidity_regime |
| **Total R Layer input** | **34** | |

---

## FEATURE MATRIX SCHEMA

```
symbol              TEXT        — stock symbol
date                DATE        — feature date T
snapshot_time       TEXT        — 'EOD'

-- V4REG features (market-wide, same for all symbols on a given date)
v4reg_trend_regime_score        REAL
v4reg_vol_regime_score          REAL
v4reg_liquidity_regime_score    REAL
v4reg_regime_confidence         REAL
v4reg_trend_structure_score     REAL
v4reg_breadth_score             REAL
v4reg_momentum_score            REAL
v4reg_drawdown_stress_score     REAL

-- V4I features (per-symbol)
v4i_ichimoku_score              REAL
v4i_ichimoku_norm               REAL
v4i_cloud_position_score        REAL
v4i_tk_signal_score             REAL
v4i_chikou_confirm_score        REAL
v4i_future_cloud_score          REAL
v4i_time_resonance              REAL
v4i_signal_quality              INTEGER

-- V4MA features (per-symbol)
v4ma_ma_score                   REAL
v4ma_ma_norm                    REAL
v4ma_alignment_score            REAL
v4ma_cross_score                REAL
v4ma_dist_ema10                 REAL
v4ma_dist_ema20                 REAL
v4ma_dist_ma50                  REAL
v4ma_dist_ma100                 REAL
v4ma_dist_ma200                 REAL
v4ma_ema10_slope                REAL
v4ma_ema20_slope                REAL
v4ma_ma50_slope                 REAL
v4ma_ma100_slope                REAL
v4ma_ma200_slope                REAL
v4ma_ema10_over_ema20           INTEGER
v4ma_ma50_over_ma100            INTEGER
v4ma_ma100_over_ma200           INTEGER
v4ma_ma50_over_ma200            INTEGER
v4ma_golden_cross               INTEGER
v4ma_death_cross                INTEGER
v4ma_signal_quality             INTEGER

-- V4PIVOT features (per-symbol)
v4pivot_pivot_score             REAL
v4pivot_pivot_norm              REAL
v4pivot_position_score          REAL
v4pivot_confluence_score        REAL
v4pivot_alignment_score         REAL
v4pivot_signal_quality          INTEGER

-- V4SR features (per-symbol)
v4sr_sr_score                   REAL
v4sr_sr_norm                    REAL
v4sr_position_score             REAL
v4sr_strength_score             REAL
v4sr_dist_nearest_support       REAL
v4sr_dist_nearest_resistance    REAL
v4sr_signal_quality             INTEGER

-- V4TREND_PATTERN features (per-symbol)
v4tp_pattern_score              REAL
v4tp_pattern_norm               REAL
v4tp_confirmation_score         REAL
v4tp_target_score               REAL
v4tp_target_distance_pct        REAL
v4tp_breakout_volume_ratio      REAL
v4tp_pattern_failure            INTEGER
v4tp_signal_quality             INTEGER

-- (remaining 14 experts will add columns when built)
```

---

## DATA LEAKAGE RULE

Feature matrix for date T uses ONLY data up to close of T-1.
See: DATA_LEAKAGE_PREVENTION.md

---

## NAMING CONVENTION

All feature columns follow: `{expert_id_lowercase}_{feature_name}`

Examples:
- `v4reg_trend_regime_score`
- `v4i_ichimoku_norm`
- `v4ma_dist_ma100`

---

## STORAGE

Feature matrix is assembled at query time from:
- `signals.db → expert_signals` (per-symbol features in metadata_json)
- `market.db → market_regime` (market-wide features)

Future: may materialize into a dedicated `feature_matrix` table for performance.

---

*Update this document when adding new expert features.*
*See EXPERT_FEATURE_OWNERSHIP.md for detailed feature-to-expert mapping.*
