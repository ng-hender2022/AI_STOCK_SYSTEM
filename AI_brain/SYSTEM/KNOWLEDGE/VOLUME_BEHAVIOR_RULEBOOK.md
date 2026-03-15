
# VOLUME_BEHAVIOR_RULEBOOK

SYSTEM:
AI_STOCK KNOWLEDGE MODULE

MODULE NAME:
VOLUME_BEHAVIOR_RULEBOOK

SOURCE:
The Art and Science of Technical Analysis – Adam Grimes (2012)

PURPOSE:
Define how AI interprets market participation through volume behavior.
Volume is used as contextual information, not as a standalone signal.

---

# 1. CORE PRINCIPLE

Volume measures market participation and commitment.

high_volume = strong participation
low_volume  = weak participation

However:

volume_confirmation is not mandatory

Some valid price signals occur with or without volume confirmation.

AI rule:

volume = contextual signal
not primary signal

---

# 2. IMPULSE VS PULLBACK VOLUME

In trends:

Impulse → high participation
Pullback → reduced participation

Typical pattern:

trend_move_volume > pullback_volume

Pullbacks normally occur with lighter volume.

AI rule:

healthy_trend =
    impulse_volume > pullback_volume

Feature:

volume_impulse_ratio

---

# 3. BREAKOUT VOLUME BEHAVIOR

Strong breakouts usually show:

momentum
volume expansion
market interest

AI breakout rule:

breakout_strength =
    price_momentum
AND volume_ratio > 1.5

Weak breakout:

breakout
AND volume_ratio < 1

→ high probability of failure.

---

# 4. VOLUME IN TREND CONTINUATION

Trend continuation often shows:

volume expansion during trend leg
volume contraction during pullback

AI rule:

trend_continuation_signal =
    impulse_volume_high
AND pullback_volume_low

Feature:

volume_trend_structure

---

# 5. VOLUME IN CONSOLIDATION

In consolidation:

volume typically decreases

Reason:

market participants waiting for new information

AI feature:

volume_compression

Rule:

consolidation_zone =
    low_range
AND declining_volume

---

# 6. VOLUME IN FAILED BREAKOUTS

False breakout often occurs when:

breakout momentum weak
OR volume participation low

Another failure pattern:

breakout
→ strong counter-move

AI rule:

breakout_failure_probability =
    breakout
AND low_volume
AND strong_reversal

---

# 7. VOLUME CLIMAX

Climax move characteristics:

rapid price acceleration
extreme participation
trend exhaustion

Often occurs near:

major highs
major lows

AI feature:

volume_spike
range_spike

Rule:

possible_exhaustion =
    volume_spike
AND price_parabolic

---

# 8. ACCUMULATION / DISTRIBUTION CONTEXT

Inside ranges:

large participants may accumulate
or distribute positions

Volume patterns may indicate participation.

However:

volume patterns alone
do not guarantee accumulation

Therefore AI must combine:

price structure
volume behavior
context

---

# 9. VOLUME FEATURE SET FOR AI

Recommended features:

volume_ratio
volume_ma_ratio
volume_impulse_ratio
volume_pullback_ratio
volume_spike_flag
volume_decay
volume_trend_structure

---

# 10. RELATION WITH OTHER RULEBOOKS

Volume module must integrate with:

PRICE_ACTION_RULEBOOK
BREAKOUT_STRUCTURE_RULEBOOK
MARKET_REGIME_RULEBOOK
ICHIMOKU_RULEBOOK

Volume alone should never produce signals.

---

# 11. ROLE IN AI_STOCK ARCHITECTURE

market data
→ V4D / V4H volume features
→ volume_behavior_rulebook
→ R1 reasoning
→ X1 decision

Volume acts as participation signal supporting price structure.

---

# 12. FINAL PRINCIPLE

AI must interpret volume in this order:

1 trend context
2 price structure
3 breakout behavior
4 volume participation

Volume confirms market activity but price structure remains primary.
