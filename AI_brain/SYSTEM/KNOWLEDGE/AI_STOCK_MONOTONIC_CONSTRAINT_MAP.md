# AI_STOCK_MONOTONIC_CONSTRAINT_MAP.md

## Purpose

This document defines **monotonic constraints** for the CatBoost model
used in the AI_STOCK system (R7 layer).

Monotonic constraints encode financial domain knowledge directly into
the machine learning model to reduce overfitting and stabilize
predictions.

Applicable model: **R7 CatBoost**

------------------------------------------------------------------------

# 1. Constraint Definition

  Value   Meaning
  ------- ---------------------------------------------
  1       Prediction increases when feature increases
  -1      Prediction decreases when feature increases
  0       No constraint

Example:

trend_persistence ↑ → bullish probability ↑

Constraint:

trend_persistence = 1

------------------------------------------------------------------------

# 2. Positive Monotonic Features

These features should increase bullish probability when their value
increases.

## Trend Strength

trend_persistence\
ma_alignment_score\
trend_strength_max

Constraint: **1**

Reason: Stronger trends increase continuation probability.

------------------------------------------------------------------------

## Momentum Strength

rs_rank\
sector_momentum\
momentum_score_avg

Constraint: **1**

Reason: Strong momentum often supports price continuation.

------------------------------------------------------------------------

## Volume Expansion

volume_ratio_5\
volume_ratio_20\
volume_pressure

Constraint: **1**

Reason: Breakouts are more reliable with strong volume.

------------------------------------------------------------------------

## Liquidity

liquidity_shock\
liquidity_shock_avg

Constraint: **1**

Reason: Higher liquidity supports price movement.

------------------------------------------------------------------------

# 3. Negative Monotonic Features

These features should decrease bullish probability when their value
increases.

## Volatility Expansion

atr_pct\
volatility_percentile

Constraint: **-1**

Reason: High volatility often indicates unstable market conditions.

------------------------------------------------------------------------

## Bollinger Expansion

bb_width

Constraint: **-1**

Reason: Wide bands indicate volatility already expanded.

------------------------------------------------------------------------

## Distance From Mean

extreme_distance_from_ma200\
extreme_distance_from_ma50

Constraint: **-1**

Reason: Price too far from averages often mean-reverts.

------------------------------------------------------------------------

# 4. Neutral Features

These features should not have constraints.

## Oscillators

RSI\
Stochastic\
MACD histogram

Constraint: **0**

Reason: Oscillators behave differently across regimes.

------------------------------------------------------------------------

## Pattern Detection

candle_pattern_code\
pattern_type_code\
pattern_completion

Constraint: **0**

Reason: Patterns are nonlinear signals.

------------------------------------------------------------------------

## Breakout Flags

breakout20_flag\
breakout60_flag

Constraint: **0**

Reason: Breakouts can succeed or fail depending on context.

------------------------------------------------------------------------

# 5. Meta Layer Constraints

## Positive

trend_score_avg\
trend_alignment_score\
expert_agreement_pct

Constraint: **1**

------------------------------------------------------------------------

## Negative

volatility_score

Constraint: **-1**

------------------------------------------------------------------------

# 6. Example CatBoost Implementation

``` python
monotone_constraints = {
    "trend_persistence": 1,
    "ma_alignment_score": 1,
    "rs_rank": 1,
    "volume_ratio_5": 1,
    "volume_ratio_20": 1,
    "liquidity_shock": 1,
    "atr_pct": -1,
    "volatility_percentile": -1,
    "bb_width": -1,
    "RSI": 0,
    "macd_hist_slope": 0,
    "breakout20_flag": 0
}
```

------------------------------------------------------------------------

# 7. Constraint Coverage

Total features: **124**

Recommended constrained features: **15--20**

This ensures domain knowledge enforcement without over-restricting the
model.

------------------------------------------------------------------------

# 8. Benefits

Applying monotonic constraints provides:

-   Reduced overfitting
-   Stable predictions
-   Better interpretability
-   Financial logic alignment

------------------------------------------------------------------------

# 9. Integration Into AI_STOCK Pipeline

Experts → Feature Matrix\
↓\
Feature Normalization\
↓\
Monotonic Constraint Mapping\
↓\
CatBoost Training (R7)\
↓\
Model Evaluation\
↓\
Master Model Selector\
↓\
X1 Decision Engine

------------------------------------------------------------------------

# 10. Key Principle

Machine learning models should respect **financial market structure**.
Monotonic constraints encode domain knowledge directly into the model.
