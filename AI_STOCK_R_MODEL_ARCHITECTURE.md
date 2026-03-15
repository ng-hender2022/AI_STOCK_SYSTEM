# AI_STOCK_R_MODEL_ARCHITECTURE

Version: 1.0  
Scope: R-model layer architecture for AI_STOCK  
Target path suggestion: `D:\AI\ai_brain\SYSTEM\AI_STOCK_R_MODEL_ARCHITECTURE.md`

---

# 1. Purpose

This document defines the full **R-model architecture** for the AI_STOCK system.

The goal of the R-layer is to convert the normalized feature pipeline into **multiple research views** of the market, using different model families, and then expose those views in a standardized form for the X1 decision engine.

This design extends the existing pipeline:

Market Data → Experts → Meta Layer → Conflict Layer → Feature Matrix → R1 Research AI → X1 Decision Engine

by explicitly expanding the “R1 Research AI” block into a **multi-model research hub**.

The foundation remains consistent with the current signal pipeline philosophy:

- Experts are deterministic and rulebook-based
- Meta Layer performs signal normalization
- Conflict Layer captures disagreement patterns
- R-layer performs machine learning research
- X1 performs final portfolio decision making

This is aligned with the current AI_STOCK signal pipeline architecture. fileciteturn0file0

---

# 2. Core Architecture Philosophy

The AI_STOCK system should not rely on a single research model.

Instead, the system should use a **portfolio of research models**, where each model family learns the market from a different perspective.

## 2.1 Why multiple R-models are needed

Different model families have different strengths:

- Linear models capture stable factor relationships and macro exposure
- Random Forest captures robust nonlinear rule interactions
- Gradient Boosting captures fine-grained tabular patterns with high predictive power
- Regime models capture market state transitions
- Sector models capture cross-stock heterogeneity across sectors and ecosystems

Therefore, the R-layer is defined as a **Research Model Hub**, not a single model.

## 2.2 Division of responsibility

- **Experts** generate raw rulebook signals
- **Meta Layer** converts expert outputs into numeric features
- **Conflict Layer** measures expert disagreement
- **Feature Matrix** becomes the common input to the R-models
- **R-models** produce research outputs and probabilities
- **MASTER SUMMARY** aggregates all research outputs into a standardized schema
- **X1** consumes the MASTER SUMMARY and makes final portfolio decisions

---

# 3. Full Pipeline Placement

```text
MARKET DATA
    ↓
EXPERT LAYER
    ↓
META LAYER
    ↓
CONFLICT LAYER
    ↓
FEATURE MATRIX
    ├─ R0_BASELINE
    ├─ R1_LINEAR
    ├─ R2_RF
    ├─ R3_GBDT
    ├─ R4_REGIME
    └─ R5_SECTOR
           ↓
      MASTER SUMMARY
           ↓
     X1 DECISION ENGINE
```

This preserves the original pipeline semantics while expanding the learning layer into multiple research engines. fileciteturn0file0

---

# 4. Standard Naming Convention

All research models should follow this naming format:

```text
R{index}_{MODEL_TYPE}
```

Official names:

- `R0_BASELINE`
- `R1_LINEAR`
- `R2_RF`
- `R3_GBDT`
- `R4_REGIME`
- `R5_SECTOR`
- `X1_META_DECISION`

Optional future expansion:

- `R6_SEQUENCE`
- `R7_EVENT`
- `R8_RELATIVE_STRENGTH`
- `R9_ALPHA_FACTORY`

---

# 5. R-Model Specifications

# 5.1 R0_BASELINE

## Purpose

R0_BASELINE is the simplest benchmark model.

It exists for:

- sanity check
- benchmark comparison
- debugging the pipeline
- preventing false confidence from more complex models

## Recommended model types

- Logistic Regression
- Simple scorecard model
- Simple weighted expert-signal baseline

## Typical inputs

- core Meta features
- core Conflict features
- basic market context

## Typical outputs

- `r0_baseline_prob_up`
- `r0_baseline_expected_return`
- `r0_baseline_direction`

## Design note

R0_BASELINE must always be cheap, stable, and interpretable.

---

# 5.2 R1_LINEAR

## Purpose

R1_LINEAR captures linear and factor-like relationships.

It should answer questions like:

- How much does market direction explain stock direction?
- How much does breadth matter?
- How much does sector momentum matter?
- How much does macro exposure matter?

## Recommended model types

- Linear Regression
- Logistic Regression
- Regularized linear models (L1 / L2 / Elastic Net)

## Typical feature categories

- VNINDEX return
- breadth score
- sector return
- trend score
- liquidity score
- simple expert features

## Typical outputs

- `r1_linear_prob_up`
- `r1_linear_expected_return`
- `r1_linear_confidence`

## Strengths

- fast
- stable
- interpretable
- strong baseline for factor-style learning

## Weaknesses

- limited nonlinear capacity

---

# 5.3 R2_RF

## Purpose

R2_RF captures robust nonlinear relationships among signals.

It is especially useful for noisy and rule-rich market data where multiple indicators interact.

## Recommended model types

- Random Forest Classifier
- Random Forest Regressor

## Typical feature categories

- MACD signals
- RSI state
- MA trend
- volume signal
- regime score
- conflict features
- market context

## Typical outputs

- `r2_rf_prob_up`
- `r2_rf_expected_return`
- `r2_rf_confidence`
- `r2_rf_feature_importance_snapshot`

## Strengths

- robust to noise
- strong with mixed nonlinear features
- good baseline nonlinear learner

## Weaknesses

- may be less sharp than GBDT
- harder to calibrate precisely

---

# 5.4 R3_GBDT

## Purpose

R3_GBDT is the main high-accuracy tabular prediction engine.

This model should be considered the primary machine learning research model for structured features.

## Recommended model types

- LightGBM
- XGBoost
- CatBoost

## Typical feature categories

- all Meta features
- all Conflict features
- market context
- sector context
- regime scores
- liquidity and breadth features

## Typical outputs

- `r3_gbdt_prob_up`
- `r3_gbdt_expected_return`
- `r3_gbdt_confidence`
- `r3_gbdt_feature_importance_snapshot`

## Strengths

- usually strongest on structured data
- captures fine interaction patterns
- efficient for retraining

## Weaknesses

- can overfit if not constrained properly
- needs careful validation and calibration

---

# 5.5 R4_REGIME

## Purpose

R4_REGIME estimates the current market regime in a **stable numeric form**.

It does not primarily predict stock direction.

Its main job is to produce a consistent market-state signal that other models and X1 can use.

## Recommended outputs

- `r4_trend_regime_score` in range `-4 ... +4`
- `r4_vol_regime_score` in range `0 ... 4`
- `r4_liquidity_regime_score` in range `-2 ... +2`
- `r4_regime_confidence`
- `r4_regime_state_text`

## Why numeric regime is required

A numeric regime score is easier to use than a text label because:

- ML models can consume it directly
- X1 can use thresholds and sizing formulas
- smoothing and stability control are easier
- transition logic becomes clearer

Detailed scoring design is defined in Section 10.

---

# 5.6 R5_SECTOR

## Purpose

R5_SECTOR captures sector-specific and ecosystem-specific behavior.

This is important for the Vietnam market because signal behavior differs strongly across sectors:

- banks
- securities brokers
- oil and gas
- real estate
- industrials
- speculative midcaps

## Recommended model types

- sector-specific GBDT
- sector-specific RF
- ranking models
- relative performance models

## Typical outputs

- `r5_sector_score`
- `r5_sector_rank`
- `r5_sector_alpha_score`
- `r5_sector_confidence`

## Design note

R5 should not replace the general models.
It should add sector-local context that global models may miss.

---

# 6. MASTER SUMMARY Layer

# 6.1 Purpose

MASTER SUMMARY is the standardized aggregation layer between the R-model hub and X1.

It is the **official research output schema** of the system.

X1 should read MASTER SUMMARY rather than reading each R-model separately.

## 6.2 Responsibilities

MASTER SUMMARY must:

- collect standardized outputs from all R-models
- calculate agreement / disagreement metrics
- expose market and sector context
- expose a final summarized research view per symbol-date
- provide a stable contract for X1

## 6.3 Example fields

Identity:

- `trade_date`
- `symbol`
- `timeframe`
- `prediction_horizon`

Raw R outputs:

- `r0_baseline_prob_up`
- `r1_linear_prob_up`
- `r2_rf_prob_up`
- `r3_gbdt_prob_up`
- `r4_trend_regime_score`
- `r4_vol_regime_score`
- `r4_liquidity_regime_score`
- `r5_sector_score`

Aggregate fields:

- `agg_avg_prob_up`
- `agg_median_prob_up`
- `agg_prob_dispersion`
- `agg_agreement_score`
- `agg_disagreement_score`
- `agg_bullish_model_count`
- `agg_bearish_model_count`

Summary fields:

- `summary_direction`
- `summary_strength`
- `summary_confidence`
- `summary_risk_state`
- `summary_x1_ready_flag`

## 6.4 Why this layer matters

MASTER SUMMARY makes the system modular.

You can improve or swap individual R-models without breaking X1, as long as the MASTER SUMMARY contract remains stable.

---

# 7. X1_META_DECISION

## Purpose

X1 is the final portfolio decision engine.

It does not replace research.
It consumes research.

## Inputs

X1 should read from MASTER SUMMARY:

- model probabilities
- agreement metrics
- regime scores
- sector scores
- conflict scores
- risk state

## Responsibilities

- position sizing
- entry filtering
- exit filtering
- portfolio allocation
- risk adjustment
- cash exposure control

## Example decision logic

```text
If summary_direction = bullish
and summary_confidence > 0.65
and agg_agreement_score > 0.70
and r4_trend_regime_score >= +1
and summary_risk_state != crisis
→ candidate long
```

```text
If bullish but regime <= -2
→ reduce size heavily or block entry
```

---

# 8. Recommended Build Order

The R-layer should be built in this sequence:

1. `R0_BASELINE`
2. `R1_LINEAR`
3. `R2_RF`
4. `R3_GBDT`
5. `R4_REGIME`
6. `R5_SECTOR`
7. `MASTER SUMMARY`
8. `X1_META_DECISION`

## Why this order

- baseline first for benchmarking
- linear first for interpretability and debugging
- RF next for robust nonlinear baseline
- GBDT next for stronger tabular accuracy
- regime after stable market feature flow exists
- sector after base architecture is stable
- X1 only after R outputs are stable and trustworthy

---

# 9. Storage / Folder Structure Recommendation

Suggested structure:

```text
D:\AI
│
├─ ai_engine
│   ├─ r_models
│   │   ├─ R0_BASELINE
│   │   ├─ R1_LINEAR
│   │   ├─ R2_RF
│   │   ├─ R3_GBDT
│   │   ├─ R4_REGIME
│   │   └─ R5_SECTOR
│   │
│   ├─ master_summary
│   └─ x1_decision
│
├─ ai_data
│   ├─ feature_matrix
│   ├─ model_outputs
│   ├─ master_summary
│   └─ x1_outputs
│
└─ ai_brain
    └─ SYSTEM
```

Suggested output storage:

```text
D:\AI\ai_data\model_outputs\R0_BASELINE\
D:\AI\ai_data\model_outputs\R1_LINEAR\
D:\AI\ai_data\model_outputs\R2_RF\
D:\AI\ai_data\model_outputs\R3_GBDT\
D:\AI\ai_data\model_outputs\R4_REGIME\
D:\AI\ai_data\model_outputs\R5_SECTOR\
D:\AI\ai_data\master_summary\
```

---

# 10. R4_REGIME Scoring Formula (Rulebook + ML Hybrid)

# 10.1 Objective

R4_REGIME must estimate a stable **trend regime score** for the Vietnam market in range:

```text
-4 to +4
```

This score should be:

- interpretable
- stable
- resistant to noisy single-day shocks
- responsive to real regime transitions
- usable both by models and by X1

The regime engine should be a **hybrid**:

- **Rulebook Layer** for interpretability and stability
- **ML Layer** for pattern refinement and probability estimation

## Final output set

R4 should produce:

- `r4_trend_regime_score_raw`
- `r4_trend_regime_score_smooth`
- `r4_vol_regime_score`
- `r4_liquidity_regime_score`
- `r4_regime_confidence`
- `r4_regime_state_text`

Where `r4_trend_regime_score_smooth` is the main field used by downstream systems.

---

# 10.2 Numeric Regime Map

## Trend regime semantic mapping

| Score | State | Meaning |
|---|---|---|
| +4 | Strong Bull Expansion | strong trend, breadth strong, pullbacks shallow |
| +3 | Bull Trend | established uptrend |
| +2 | Bull Recovery | rebound / recovery phase |
| +1 | Early Bull / Mild Bull | positive but not fully confirmed |
| 0 | Neutral / Sideway | mixed market |
| -1 | Mild Bear | weak market / fragile structure |
| -2 | Bear Trend | established downtrend |
| -3 | Bear Acceleration | aggressive selloff trend |
| -4 | Panic / Crisis | crash-like regime |

---

# 10.3 R4 Hybrid Design

R4 should combine two sub-layers:

## A. Rulebook regime layer

Produces:

- `rule_trend_regime_score`
- `rule_vol_regime_score`
- `rule_liquidity_regime_score`
- `rule_regime_confidence`

This layer is deterministic.

## B. ML regime layer

Produces:

- `ml_prob_regime_pos4`
- `ml_prob_regime_pos3`
- ...
- `ml_prob_regime_neg4`
- `ml_expected_regime_score`
- `ml_regime_confidence`

This layer is a classification / ordinal-regression style model.

## C. Hybrid fusion layer

Produces final:

```text
final_trend_regime_raw
= w_rule * rule_trend_regime_score
+ w_ml   * ml_expected_regime_score
```

Recommended default:

```text
w_rule = 0.60
w_ml   = 0.40
```

Why heavier rule weight:

- higher interpretability
- more stable during early deployment
- safer for VN market where noise and regime flipping can be severe

---

# 10.4 Rulebook Inputs

R4 rulebook should use market-level features only.

Recommended inputs:

## Trend features

- VNINDEX close vs MA20
- VNINDEX close vs MA50
- VNINDEX close vs MA200
- slope of MA20
- slope of MA50
- 20-day return
- 60-day return
- drawdown from rolling high

## Breadth features

- % stocks above MA20
- % stocks above MA50
- advance/decline ratio
- sector breadth score

## Volatility features

- VNINDEX ATR / close
- rolling realized volatility
- intraday range expansion score

## Liquidity features

- total market volume vs MA20 volume
- value traded vs MA20
- foreign net flow normalized
- margin/liquidity proxy if available

---

# 10.5 Rulebook Trend Regime Score Formula

Use a weighted component score first.

## Component scores

### A. Trend structure score (range -2 to +2)

Suggested rule:

```text
+2 if close > MA20 > MA50 > MA200 and MA20 slope > 0 and MA50 slope > 0
+1 if close > MA20 and MA20 > MA50 and medium trend positive
 0 if mixed / crossing
-1 if close < MA20 and MA20 < MA50 and medium trend weak
-2 if close < MA20 < MA50 < MA200 and MA20 slope < 0 and MA50 slope < 0
```

### B. Breadth score (range -2 to +2)

Suggested rule:

```text
+2 if %above_MA50 >= 70% and A/D strong
+1 if breadth positive but not dominant
 0 if mixed breadth
-1 if weak breadth
-2 if %above_MA50 <= 25% and A/D weak
```

### C. Momentum / return score (range -2 to +2)

Suggested rule:

```text
+2 if 20d return strong positive and 60d return positive
+1 if short-term positive recovery
 0 if flat
-1 if weak negative trend
-2 if 20d and 60d both clearly negative
```

### D. Drawdown stress score (range -2 to 0)

Suggested rule:

```text
 0 if drawdown from 120d high < 5%
-1 if drawdown between 5% and 12%
-2 if drawdown > 12%
```

## Weighted combination

```text
rule_core_score
= 0.40 * trend_structure_score
+ 0.25 * breadth_score
+ 0.20 * momentum_score
+ 0.15 * drawdown_stress_score
```

This gives a score roughly in `[-2, +2]`.

Scale to `[-4, +4]`:

```text
rule_trend_regime_score = round(2 * rule_core_score)
```

Then clamp:

```text
rule_trend_regime_score = min(+4, max(-4, rule_trend_regime_score))
```

---

# 10.6 Panic Override Rules

The VN market can move into panic faster than trend formulas can respond.

Therefore R4 must include crisis overrides.

## Panic override to -4

Set regime to `-4` if any strong panic condition occurs, for example:

- VNINDEX one-day drop exceeds extreme threshold
- market breadth collapses below panic threshold
- multiple consecutive wide-range selloff days
- volume spike with broad-based liquidation

Suggested logic:

```text
If
    one_day_return <= panic_drop_threshold
and breadth_score <= -2
and vol_regime_score >= 3
→ force rule_trend_regime_score = -4
```

## Blowoff override to +4

Use more conservatively.

```text
If
    trend_structure_score = +2
and breadth_score = +2
and momentum_score = +2
and liquidity positive
→ allow +4
```

---

# 10.7 ML Regime Layer

The ML regime layer should refine regime recognition.

## Possible target definition

The target can be created using future rolling outcomes, for example:

- future 20-day return bucket
- future drawdown bucket
- future breadth persistence

Then map outcomes into ordinal regime classes from `-4` to `+4`.

## Recommended model options

- LightGBM multiclass classifier
- ordinal classification model
- Random Forest classifier

## Recommended inputs

- all rulebook regime inputs
- broader market context
- sector dispersion
- volatility and liquidity indicators
- conflict aggregate metrics if relevant

## ML output

The model should output:

```text
P(regime=-4), P(-3), ..., P(+4)
```

Then compute expected regime score:

```text
ml_expected_regime_score
= Σ [ regime_value_i * probability_i ]
```

Where `regime_value_i ∈ {-4,-3,-2,-1,0,+1,+2,+3,+4}`.

---

# 10.8 Hybrid Fusion Formula

Final raw regime score before smoothing:

```text
final_trend_regime_raw
= 0.60 * rule_trend_regime_score
+ 0.40 * ml_expected_regime_score
```

Optional confidence-adjusted fusion:

```text
effective_w_rule = 0.60 + 0.20 * (1 - ml_regime_confidence)
effective_w_ml   = 1 - effective_w_rule
```

Meaning:

- when ML confidence is low, trust the rulebook more
- when ML confidence rises, allow ML to influence more

Then clamp to `[-4, +4]`.

---

# 10.9 Smoothing Formula

Regime must be stable.

Use a smoothing step:

```text
r4_trend_regime_score_smooth_t
= α * final_trend_regime_raw_t
+ (1 - α) * r4_trend_regime_score_smooth_{t-1}
```

Recommended default:

```text
α = 0.30
```

Then apply a bounded step-change rule:

```text
max daily change = 1 score unit
```

This prevents unstable jumps like `+3 → -2` in one day unless panic override is triggered.

## Final publication score

For external consumption:

```text
r4_trend_regime_score = round(r4_trend_regime_score_smooth)
```

while keeping the unsmoothed and smoothed float values in storage.

---

# 10.10 Volatility Regime Score

Separate volatility regime from trend regime.

Recommended scale:

| Score | Meaning |
|---|---|
| 0 | very low vol |
| 1 | normal vol |
| 2 | elevated vol |
| 3 | high vol |
| 4 | extreme vol |

## Rulebook method

Use percentile bucket of:

- rolling ATR / close
- realized volatility
- intraday range expansion

Example:

```text
bottom 20% percentile → 0
20-40% → 1
40-65% → 2
65-85% → 3
85-100% → 4
```

---

# 10.11 Liquidity Regime Score

Recommended scale:

| Score | Meaning |
|---|---|
| +2 | liquidity expansion |
| +1 | healthy liquidity |
| 0 | neutral |
| -1 | tightening |
| -2 | stressed liquidity |

## Rulebook method

Use a weighted combination of:

- market traded value vs MA20
- breadth participation
- foreign flow normalized
- turnover persistence

Example simplified rule:

```text
+2 if value_traded >> MA20 and breadth positive
+1 if healthy liquidity
 0 if neutral
-1 if below normal and narrowing
-2 if strong contraction with weak breadth
```

---

# 10.12 Confidence Formula

R4 should publish a confidence score in range `0 to 1`.

Suggested hybrid confidence:

```text
r4_regime_confidence
= 0.40 * rule_consistency
+ 0.35 * ml_regime_confidence
+ 0.25 * regime_persistence
```

Where:

- `rule_consistency` measures whether trend/breadth/momentum agree
- `ml_regime_confidence` can be top-class probability or margin between top two probabilities
- `regime_persistence` measures stability over recent days

---

# 10.13 Recommended Use in Downstream Layers

## As feature input to R2 / R3 / R5

Use:

- `r4_trend_regime_score`
- `r4_vol_regime_score`
- `r4_liquidity_regime_score`
- `r4_regime_confidence`

## In MASTER SUMMARY

Store:

- `r4_trend_regime_score_raw`
- `r4_trend_regime_score_smooth`
- `r4_trend_regime_score`
- `r4_vol_regime_score`
- `r4_liquidity_regime_score`
- `r4_regime_confidence`
- `r4_regime_state_text`

## In X1 decision rules

Example:

```text
If r4_trend_regime_score <= -3
→ block aggressive long entries
```

```text
If r4_trend_regime_score >= +2 and r4_vol_regime_score <= 2
→ allow larger risk budget
```

```text
If r4_trend_regime_score = 0
→ require stronger model agreement before entry
```

---

# 11. Minimum Viable Implementation

For a practical first version, implement:

## Phase 1

- rulebook-only trend regime score `-4 ... +4`
- volatility regime score `0 ... 4`
- liquidity regime score `-2 ... +2`
- smoothing and panic override

## Phase 2

- ML multiclass regime model
- hybrid fusion
- confidence calibration

## Phase 3

- integrate sector-level regime variants
- improve regime transition logic
- expose regime transition events into MASTER SUMMARY

---

# 12. Final Architecture Summary

The final AI_STOCK research architecture is:

```text
MARKET DATA
    ↓
EXPERT LAYER
    ↓
META LAYER
    ↓
CONFLICT LAYER
    ↓
FEATURE MATRIX
    ├─ R0_BASELINE
    ├─ R1_LINEAR
    ├─ R2_RF
    ├─ R3_GBDT
    ├─ R4_REGIME
    └─ R5_SECTOR
           ↓
      MASTER SUMMARY
           ↓
     X1_META_DECISION
           ↓
     PORTFOLIO OUTPUT
```

Key principles:

- Experts are deterministic
- Research is multi-model
- Regime is numeric and stable
- MASTER SUMMARY is the official research contract
- X1 consumes summarized research, not raw model internals

This architecture is fully consistent with the current AI_STOCK signal pipeline philosophy while providing a stronger and more scalable learning layer. fileciteturn0file0

