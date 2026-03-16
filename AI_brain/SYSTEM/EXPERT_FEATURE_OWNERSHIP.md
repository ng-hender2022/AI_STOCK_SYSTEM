# EXPERT FEATURE OWNERSHIP

Version: 1.0
Date: 2026-03-16
Status: ACTIVE

---

## PURPOSE

Maps every feature to its owning expert.
R Layer and Meta Layer use this to know which expert produces which features.

---

## V4REG — Market Regime Expert

| Feature | Type | Range |
|---|---|---|
| trend_regime_score | float | -4..+4 |
| trend_regime_score_raw | float | -4..+4 |
| vol_regime_score | float | 0..4 |
| liquidity_regime_score | float | -2..+2 |
| regime_label | str | STRONG_BEAR..STRONG_BULL |
| regime_confidence | float | 0..1 |
| trend_structure_score | float | -2..+2 |
| breadth_score | float | -2..+2 |
| momentum_score | float | -2..+2 |
| drawdown_stress_score | float | -2..0 |

**Total: 10 features**

---

## V4I — Ichimoku Expert

| Feature | Type | Range |
|---|---|---|
| ichimoku_score | float | -4..+4 |
| ichimoku_norm | float | -1..+1 |
| cloud_position | str | above/inside/below |
| cloud_position_score | float | -2/0/+2 |
| tk_signal | str | bullish/bearish/neutral |
| tk_signal_score | float | -1/0/+1 |
| chikou_confirm | str | bullish/bearish/neutral |
| chikou_confirm_score | float | -1/0/+1 |
| future_cloud | str | bullish/bearish/flat |
| future_cloud_score | float | -1/0/+1 |
| time_resonance | float | 0..1 |
| near_cycle | int | 0/9/17/26/33/42 |
| days_since_pivot | int | 0+ |
| signal_quality | int | 0..4 |

**Total: 14 features**

---

## V4MA — Moving Average Expert

| Feature | Type | Range |
|---|---|---|
| ma_score | float | -4..+4 |
| ma_norm | float | -1..+1 |
| alignment | str | all_bullish..all_bearish |
| alignment_score | float | -3..+3 |
| cross_signal | str | golden_cross/death_cross/short_cross_up/down/none |
| cross_score | float | -1..+1 |
| dist_ema10 | float | ratio |
| dist_ema20 | float | ratio |
| dist_ma50 | float | ratio |
| dist_ma100 | float | ratio |
| dist_ma200 | float | ratio |
| ema10_slope | float | ratio |
| ema20_slope | float | ratio |
| ma50_slope | float | ratio |
| ma100_slope | float | ratio |
| ma200_slope | float | ratio |
| ema10_over_ema20 | int | -1/+1 |
| ma50_over_ma100 | int | -1/+1 |
| ma100_over_ma200 | int | -1/+1 |
| ma50_over_ma200 | int | -1/+1 |
| golden_cross | bool | 0/1 |
| death_cross | bool | 0/1 |
| signal_quality | int | 0..4 |

**Total: 23 features**

---

## SUMMARY

| Expert | Feature Count | Status |
|---|---|---|
| V4REG | 10 | BUILT |
| V4I | 14 | BUILT |
| V4MA | 23 | BUILT |
| V4ADX | — | NOT STARTED |
| V4MACD | — | NOT STARTED |
| V4RSI | — | NOT STARTED |
| V4STO | — | NOT STARTED |
| V4V | — | NOT STARTED |
| V4OBV | — | NOT STARTED |
| V4ATR | — | NOT STARTED |
| V4BB | — | NOT STARTED |
| V4P | — | NOT STARTED |
| V4CANDLE | — | NOT STARTED |
| V4BR | — | NOT STARTED |
| V4RS | — | NOT STARTED |
| V4S | — | NOT STARTED |
| V4LIQ | — | NOT STARTED |

**Total features (built): 47**

---

*This file is the single source of truth for feature ownership.*
*Update when adding/modifying expert features.*
