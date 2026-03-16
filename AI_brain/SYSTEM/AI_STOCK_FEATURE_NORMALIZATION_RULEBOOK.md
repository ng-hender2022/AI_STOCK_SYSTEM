# AI_STOCK_FEATURE_NORMALIZATION_RULEBOOK.md

## Purpose

This document defines the **feature normalization protocol** for the AI_STOCK system.

The system will use **124 features** produced by 20 experts plus meta-layer context.

Normalization ensures:

- fair feature importance
- stable model training
- reduced scale bias
- better generalization across market regimes

This rulebook must be applied before any model training.

Applicable models:

- Random Forest
- LightGBM
- XGBoost
- CatBoost

---

# 1. Normalization Pipeline

Feature processing order must be:

Experts → Raw Features  
↓  
Feature Normalization  
↓  
Feature Matrix (124 features)  
↓  
Model Training

Raw features must **never be passed directly to models**.

---

# 2. Normalization Categories

All features must belong to one of the following normalization categories.

---

# Category A: Oscillators

Examples:

- RSI
- Stochastic
- oscillator-based scores

Raw range:

0 → 100

Normalization formula:

x_norm = (x − 50) / 50

Resulting range:

-1 → +1

Example:

RSI = 70  
RSI_norm = (70 − 50) / 50 = 0.40

---

# Category B: Percentiles

Examples:

- ATR percentile
- liquidity percentile
- RS rank
- sector rank percentile

Raw range:

0 → 1

Normalization:

No change.

x_norm = x

---

# Category C: Returns

Examples:

- ret_1d
- ret_5d
- ret_10d
- ret_20d
- rs_5d
- rs_20d

Normalization method:

Z-score normalization.

Formula:

z = (x − mean) / std

Where:

mean = rolling mean (252 days)  
std = rolling std (252 days)

Expected normalized range:

-3 → +3

---

# Category D: Ratios

Examples:

- volume_ratio_5
- volume_ratio_20
- liquidity_shock
- volatility_compression
- turnover ratios

These features are right-skewed.

Apply log transform.

Formula:

x_norm = log(1 + x)

Example:

volume_ratio = 5

x_norm = log(6)

---

# Category E: Distances

Examples:

- dist_ma20
- dist_ma50
- sr_distance
- pivot distance

Normalization:

Percentage of price.

Formula:

distance = (value − reference) / reference

Expected range:

-0.2 → +0.2

No further scaling required.

---

# Category F: Binary Flags

Examples:

- breakout_flag
- cross_flag
- divergence_flag
- squeeze_flag
- pattern_detected

Allowed values:

-1  
0  
1

Normalization:

No change.

---

# Category G: Percent-Based Structure

Examples:

- body_pct
- wick_pct
- bb_position
- ma_alignment_pct

Range:

0 → 1

Normalization:

No change.

---

# Category H: Regime Scores

Examples:

- trend_regime_score
- liquidity_regime_score
- volatility_regime_code

Normalization:

Divide by maximum possible value.

Example:

trend_regime_norm = trend_regime_score / 4

Range:

-1 → +1

---

# 3. Meta Feature Normalization

Meta layer features must also be normalized.

---

## Trend Context

trend_score_avg → divide by 4

trend_alignment_score → already 0..1

trend_strength_max → divide by 4

ma_alignment_pct → 0..1

trend_persistence_avg → 0..1

---

## Momentum Context

momentum_score_avg → divide by 4

momentum_divergence_count → divide by expert_count

overbought_count → divide by oscillator_count

oversold_count → divide by oscillator_count

---

## Volume Context

volume_pressure → log normalized

market_volume_ratio → log normalized

liquidity_shock_avg → log normalized

climax_volume_count → divide by universe size

---

## Volatility Context

volatility_score → divide by max score

compression_count → divide by expert count

volatility_regime_mode → normalized to 0..1

---

## Market Strength

market_strength → divide by expert_count

bull_bear_ratio → normalize to -1..1

expert_agreement_pct → 0..1

sector_momentum → z-score

sector_dispersion → z-score

---

## Price Structure

breakout_count → divide by universe size

sr_test_count → divide by universe size

pattern_active_count → divide by universe size

new_high_52w_count → divide by universe size

---

# 4. Expected Feature Matrix Distribution

After normalization:

Most features should lie in:

-3 → +3

Preferred concentration:

-1 → +1

This ensures stable model splits.

---

# 5. Feature Validation Tests

Normalization pipeline must verify:

1. No NaN values
2. No infinite values
3. Feature range sanity
4. Consistent scaling across symbols
5. Rolling normalization uses only past data

Future data leakage is strictly forbidden.

---

# 6. Anti-Leakage Rule

Rolling statistics must be computed using **past-only data**.

Example:

Incorrect:

mean = mean(return_252 including future)

Correct:

mean = rolling_mean(return_252 up to t-1)

---

# 7. Final Feature Matrix

Final expected structure:

Experts features: ~99  
Meta features: 25  

Total:

124 normalized features

---

# 8. Key Principle

Models must learn from **information**, not from **numerical scale differences**.

All features must therefore be normalized before entering the model pipeline.