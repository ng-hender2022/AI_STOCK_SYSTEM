
# PRICE_ACTION_RULEBOOK_FOR_AI

SYSTEM:
AI_STOCK KNOWLEDGE MODULE

MODULE NAME:
PRICE_ACTION_RULEBOOK

SOURCE:
The Art and Science of Technical Analysis – Adam Grimes (2012)

PURPOSE:
Provide structured market behavior logic for AI interpretation of price movement.
This module defines market behavior rules, not indicators.

---

# 1. MARKET STRUCTURE

Market always exists in one of three states:

- UPTREND
- DOWNTREND
- RANGE

AI must classify market structure before interpreting signals.

## 1.1 Uptrend

Definition:

Higher High (HH)  
Higher Low (HL)

Structure:

HL → HH → HL → HH

AI detection rule:

trend_up =
    last_high > previous_high
AND last_low > previous_low

Supporting conditions:

close > moving_average  
momentum_positive

---

## 1.2 Downtrend

Definition:

Lower High (LH)  
Lower Low (LL)

Structure:

LH → LL → LH → LL

AI detection rule:

trend_down =
    last_high < previous_high
AND last_low < previous_low

Supporting conditions:

close < moving_average  
momentum_negative

---

## 1.3 Range

Definition:

Price oscillates between support and resistance.

AI rule:

range_market =
    no higher highs
AND no lower lows

---

# 2. IMPULSE AND CORRECTION

Price movement consists of two phases:

Impulse → Correction

Structure:

Impulse → Pullback → Impulse

Impulse characteristics:

- large candles
- range expansion
- volume expansion

AI features:

- body_percent
- range_percent
- volume_ratio

Impulse detection:

impulse_move =
    body_percent > 0.6
AND range_percent > average_range

---

# 3. PULLBACK LOGIC

Pullback is temporary correction during trend.

Uptrend example:

Impulse Up → Pullback → Continuation

AI features:

- pullback_depth
- pullback_duration
- pullback_volume

Rules:

valid_pullback =
    pullback_depth < 50% of impulse
AND pullback_duration < 10 bars

Deep pullback:

pullback_depth > 70%
→ risk of trend failure

---

# 4. MOMENTUM

Momentum measures strength of move.

Strong momentum indicators:

- large candle body
- small wicks
- high volume
- range expansion

AI features:

- body_percent
- upper_wick_ratio
- lower_wick_ratio
- volume_ratio
- range_percent

Momentum rule:

momentum_strong =
    body_percent > 0.7
AND volume_ratio > 1.5

Weak momentum:

- body shrinking
- volume declining
- range contraction

---

# 5. BREAKOUT

Breakout occurs when price exits a range or structure.

Valid breakout conditions:

- range expansion
- volume expansion
- follow-through candle

AI breakout rule:

breakout_valid =
    close > resistance
AND volume_ratio > 1.5

Follow-through requirement:

next_bar_close > breakout_bar_close

False breakout:

breakout
AND rapid return inside range

AI detection:

false_breakout =
    breakout
AND close < resistance within 3 bars

---

# 6. TREND FAILURE

Trend ends when structure breaks.

Uptrend failure:

HL breaks

Structure:

HH → HL → HH → HL  
↓  
break HL

AI rule:

trend_failure =
    close < previous_HL

Downtrend failure:

close > previous_LH

---

# 7. REVERSAL

Reversal sequence:

trend weakening → structure break → momentum shift

AI features:

- structure_break_flag
- momentum_shift_flag

Reversal rule:

reversal_probability_high =
    structure_break
AND momentum_strong_opposite

---

# 8. EXHAUSTION

Trend exhaustion occurs when trend continues but momentum weakens.

Signs:

- shrinking candles
- lower volume
- multiple failed breakouts

AI features:

- momentum_decay
- range_decay
- volume_decay

Rule:

trend_exhaustion =
    momentum_decay
AND range_decay

---

# 9. MULTI-TIMEFRAME CONTEXT

Signal interpretation depends on higher timeframe.

Example:

daily trend = up  
intraday = pullback

Interpretation:

bullish continuation

AI logic:

if daily_trend == up  
and intraday_pullback == true  
→ bullish setup

Mapping to AI_STOCK architecture:

V4D → daily context  
V4H → intraday structure

---

# 10. CONTEXT PRIORITY RULE

Most important principle:

Context > Signal

Meaning:

A signal must match market context.

AI rule:

signal_valid =
    signal
AND context_alignment

---

# 11. RISK / REWARD PRINCIPLE

Trade must have positive reward-risk ratio.

Definition:

RR = expected_move / stop_distance

AI rule:

trade_valid =
    RR > 2

---

# 12. FEATURE LIST FOR AI IMPLEMENTATION

Recommended feature set:

- market_structure
- trend_strength
- pullback_depth
- pullback_duration
- breakout_flag
- false_breakout_flag
- momentum_score
- trend_exhaustion_score
- reversal_probability

---

# 13. RELATION WITH OTHER KNOWLEDGE MODULES

Price Action rulebook integrates with:

- ICHIMOKU_RULEBOOK
- VOLUME_RULEBOOK
- MARKET_REGIME_RULEBOOK
- SECTOR_ROTATION_RULEBOOK

---

# 14. ROLE IN AI_STOCK ARCHITECTURE

DATA
→ V4D
→ V4H
→ PRICE_ACTION_RULEBOOK
→ R1 reasoning
→ X1 decision

---

# 15. FINAL PRINCIPLE

AI must evaluate market in this order:

1. market structure
2. trend strength
3. pullback / continuation
4. breakout
5. momentum
6. reversal probability

Signal evaluation must always start with structure.
