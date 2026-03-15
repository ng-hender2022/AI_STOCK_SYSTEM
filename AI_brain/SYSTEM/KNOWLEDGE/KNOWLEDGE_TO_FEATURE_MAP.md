# KNOWLEDGE_TO_FEATURE_MAP

SYSTEM:
AI_STOCK KNOWLEDGE MODULE

MODULE NAME:
KNOWLEDGE_TO_FEATURE_MAP

PURPOSE:
Map AI_STOCK rulebooks into concrete machine-learning features for V4D and V4H.

PRINCIPLE:
Rulebook text is not used directly by models.
Rulebook logic must be transformed into numeric or categorical features.

PIPELINE:
RULEBOOK
→ FEATURE MAP
→ V4D / V4H FEATURE ENGINEERING
→ MODEL TRAINING
→ R1 REASONING
→ X1 DECISION

---

# 1. GLOBAL PRINCIPLE

Each rulebook contributes one or more of the following:

- structural features
- momentum features
- volume features
- pattern flags
- regime flags
- confidence / quality scores

Feature types:

- binary flags
- continuous ratios
- categorical labels
- rolling statistics
- composite scores

---

# 2. PRICE_ACTION_RULEBOOK → FEATURES

Source concepts:

- market structure
- impulse / correction
- pullback
- momentum
- breakout
- reversal
- exhaustion

Mapped features:

## 2.1 Structure
- higher_high_flag
- higher_low_flag
- lower_high_flag
- lower_low_flag
- market_structure_label

## 2.2 Trend
- trend_strength_score
- directional_consistency
- trend_leg_length
- trend_slope

## 2.3 Pullback
- pullback_depth_pct
- pullback_duration_bars
- pullback_volume_ratio
- valid_pullback_flag

## 2.4 Momentum
- body_percent
- range_percent
- upper_wick_ratio
- lower_wick_ratio
- momentum_score

## 2.5 Breakout
- breakout_flag
- breakout_strength
- follow_through_flag
- false_breakout_flag

## 2.6 Reversal / Exhaustion
- structure_break_flag
- momentum_shift_flag
- trend_exhaustion_score
- reversal_probability_score

---

# 3. VOLUME_BEHAVIOR_RULEBOOK → FEATURES

Source concepts:

- impulse vs pullback volume
- breakout volume
- consolidation volume
- volume climax
- participation strength

Mapped features:

## 3.1 Core Volume
- volume_ratio
- volume_ma_ratio
- volume_zscore
- volume_spike_flag

## 3.2 Trend Participation
- impulse_volume_ratio
- pullback_volume_ratio
- volume_trend_structure
- healthy_trend_volume_flag

## 3.3 Breakout Participation
- breakout_volume_ratio
- low_volume_breakout_flag
- breakout_failure_volume_flag

## 3.4 Consolidation / Climax
- volume_compression_score
- volume_decay_score
- volume_climax_flag

---

# 4. PATTERN_STRUCTURE_RULEBOOK → FEATURES

Source concepts:

- head and shoulders
- double top / bottom
- triangles
- flags
- pennants
- rectangles
- wedges
- breakout confirmation

Mapped features:

## 4.1 Pattern Type Flags
- head_shoulders_flag
- inverse_head_shoulders_flag
- double_top_flag
- double_bottom_flag
- triple_top_flag
- triple_bottom_flag
- triangle_flag
- flag_pattern_flag
- pennant_flag
- rectangle_flag
- wedge_flag

## 4.2 Pattern Shape Metrics
- pattern_height_pct
- pattern_duration_bars
- pattern_symmetry_score
- pattern_tightness_score

## 4.3 Pattern Breakout
- pattern_breakout_flag
- pattern_breakout_strength
- pattern_target_distance_pct
- pattern_false_breakout_flag

---

# 5. CANDLESTICK_RULEBOOK → FEATURES

Source concepts:

- hammer
- shooting star
- doji
- spinning top
- engulfing
- harami
- morning star
- evening star
- windows / gaps

Mapped features:

## 5.1 Candle Geometry
- body_percent
- upper_shadow_ratio
- lower_shadow_ratio
- candle_range_pct
- gap_up_flag
- gap_down_flag
- gap_size_pct

## 5.2 Single Candle Flags
- hammer_flag
- shooting_star_flag
- doji_flag
- spinning_top_flag

## 5.3 Multi-Candle Flags
- bullish_engulfing_flag
- bearish_engulfing_flag
- harami_flag
- morning_star_flag
- evening_star_flag

## 5.4 Candle Quality
- candle_pattern_strength
- candle_reversal_score
- candle_indecision_score

---

# 6. MARKET_REGIME_RULEBOOK → FEATURES

Source concepts:

- trend regime
- range regime
- transition regime
- volatility state

Mapped features:

## 6.1 Regime Labels
- trend_regime_flag
- range_regime_flag
- transition_regime_flag
- regime_label

## 6.2 Regime Inputs
- trend_strength_score
- range_width_pct
- breakout_frequency
- false_breakout_rate
- volatility_level
- volatility_expansion_flag

## 6.3 Regime Context
- regime_confidence_score
- regime_shift_warning_flag

---

# 7. AI_STOCK_SIGNAL_HIERARCHY → FEATURES / LOGIC

Source concepts:

- regime first
- structure second
- signal third
- volume confirmation fourth
- probability evaluation fifth

This rulebook does not mainly create raw features.
It defines feature usage priority and composite reasoning logic.

Mapped outputs:

- regime_compatible_signal_flag
- structure_compatible_signal_flag
- volume_confirmed_signal_flag
- final_signal_confidence
- signal_priority_rank

---

# 8. ICHIMOKU_RULEBOOK / ICHIMOKU_FEATURE_MAP → FEATURES

Source concepts:

- price vs cloud
- tenkan / kijun relation
- future cloud
- chikou confirmation
- time cycles
- equilibrium stretch

Mapped features:

## 8.1 Core Lines
- tenkan
- kijun
- span_a
- span_b
- chikou

## 8.2 Structure
- price_vs_cloud
- cloud_thickness
- future_cloud_direction
- cloud_twist_flag

## 8.3 TK Logic
- tenkan_vs_kijun
- tk_spread
- tk_cross_up
- tk_cross_down
- days_since_tk_cross

## 8.4 Distance / Equilibrium
- dist_close_kijun
- dist_close_cloud
- equilibrium_stretch_score

## 8.5 Chikou / Time
- chikou_vs_price
- chikou_vs_cloud
- near_9_flag
- near_26_flag
- time_resonance_score

## 8.6 Composite
- bullish_alignment_flag
- bearish_alignment_flag
- continuation_setup_score
- trend_failure_risk

---

# 9. FEATURE DEPLOYMENT BY ENGINE

## 9.1 V4D (Daily Engine)

Recommended priority features:

- market_structure_label
- trend_strength_score
- breakout_flag
- false_breakout_flag
- pullback_depth_pct
- momentum_score
- volume_ratio
- volume_spike_flag
- trend_regime_flag
- range_regime_flag
- transition_regime_flag
- bullish_engulfing_flag
- bearish_engulfing_flag
- pattern_breakout_flag
- pattern_target_distance_pct
- price_vs_cloud
- tenkan_vs_kijun
- bullish_alignment_flag
- bearish_alignment_flag

## 9.2 V4H (Intraday Engine)

Recommended priority features:

- return_1
- return_3
- body_percent
- upper_shadow_ratio
- lower_shadow_ratio
- volume_ratio
- breakout_flag
- false_breakout_flag
- momentum_score
- candle_reversal_score
- hammer_flag
- shooting_star_flag
- bullish_engulfing_flag
- bearish_engulfing_flag
- trend_regime_flag
- range_regime_flag
- transition_regime_flag
- vnindex_return
- sector_return
- market_breadth_score

---

# 10. FEATURE ENGINEERING IMPLEMENTATION RULES

## 10.1 Naming
Use consistent suffixes:

- _flag       → binary
- _score      → continuous score
- _ratio      → normalized ratio
- _pct        → percentage distance
- _label      → categorical label

## 10.2 Storage
All engineered features should be stored in database feature tables.

V4D:
- features table in market_learning.db

V4H:
- snapshot_features table in intraday_learning.db

## 10.3 Reproducibility
Every composite feature must be traceable back to:

- raw price / volume data
- deterministic formula
- documented rulebook source

---

# 11. COMPOSITE FEATURE EXAMPLES

## 11.1 Breakout Quality Score
breakout_quality_score =
    breakout_flag
    + breakout_strength
    + breakout_volume_ratio
    + follow_through_flag
    - false_breakout_flag

## 11.2 Reversal Setup Score
reversal_setup_score =
    structure_break_flag
    + candle_reversal_score
    + momentum_shift_flag
    + volume_spike_flag

## 11.3 Regime Confidence Score
regime_confidence_score =
    trend_strength_score
    + range_width_pct
    + volatility_level
    + breakout_frequency_consistency

---

# 12. FINAL PRINCIPLE

AI_STOCK should never stop at qualitative knowledge.

Required conversion path:

text rule
→ measurable condition
→ feature column
→ model input
→ reasoning signal

Without feature mapping, rulebooks remain static documentation.
With feature mapping, rulebooks become learnable system intelligence.
