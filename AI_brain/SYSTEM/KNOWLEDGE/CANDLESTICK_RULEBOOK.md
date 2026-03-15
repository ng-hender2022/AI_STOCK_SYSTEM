
# CANDLESTICK_RULEBOOK

SYSTEM:
AI_STOCK KNOWLEDGE MODULE

MODULE NAME:
CANDLESTICK_RULEBOOK

PRIMARY SOURCE:
The Candlestick Course – Steve Nison (2003)

PURPOSE:
Define how AI detects and interprets candlestick signals that represent short‑term shifts
in supply and demand. Candlesticks provide early sentiment signals but must be interpreted
within trend and market structure context.

---

# 1. CORE PRINCIPLE

Candlestick charts display the battle between buyers and sellers using:

open
high
low
close

Key interpretation:

bull_control  = close near high
bear_control  = close near low
indecision    = small real body

Candlestick signals alone are insufficient. They must be combined with:

trend context
support/resistance
volume behavior

---

# 2. BASIC CANDLE FEATURES

AI must extract the following features from each candle:

body_size
upper_shadow_length
lower_shadow_length
body_percent
upper_shadow_ratio
lower_shadow_ratio
gap_up
gap_down

Derived metrics:

body_percent = abs(close - open) / (high - low)

upper_shadow_ratio = (high - max(open, close)) / (high - low)

lower_shadow_ratio = (min(open, close) - low) / (high - low)

---

# 3. SINGLE CANDLE SIGNALS

## 3.1 Hammer

Structure:

small body
long lower shadow
little or no upper shadow

AI rule:

hammer =
    lower_shadow_ratio > 0.6
AND body_percent < 0.3
AND upper_shadow_ratio < 0.2

Interpretation:

potential bullish reversal after decline

---

## 3.2 Shooting Star

Structure:

small body
long upper shadow

AI rule:

shooting_star =
    upper_shadow_ratio > 0.6
AND body_percent < 0.3

Interpretation:

possible bearish reversal after uptrend

---

## 3.3 Doji

Structure:

open ≈ close

AI rule:

doji =
    body_percent < 0.05

Interpretation:

market indecision

---

## 3.4 Spinning Top

Structure:

small body
upper and lower shadows

AI rule:

spinning_top =
    body_percent < 0.25
AND upper_shadow_ratio > 0.25
AND lower_shadow_ratio > 0.25

Interpretation:

indecision during trend

---

# 4. TWO CANDLE PATTERNS

## 4.1 Bullish Engulfing

Structure:

second candle body fully engulfs previous body

AI rule:

bullish_engulfing =
    previous_close < previous_open
AND close > open
AND close > previous_open
AND open < previous_close

Interpretation:

bullish reversal

---

## 4.2 Bearish Engulfing

Structure:

bearish candle engulfing prior bullish candle

AI rule:

bearish_engulfing =
    previous_close > previous_open
AND close < open
AND open > previous_close
AND close < previous_open

Interpretation:

bearish reversal

---

## 4.3 Harami

Structure:

small candle within prior candle body

AI rule:

harami =
    high < previous_high
AND low > previous_low

Interpretation:

trend pause or possible reversal

---

# 5. THREE CANDLE PATTERNS

## 5.1 Morning Star

Structure:

bearish candle
small indecision candle
strong bullish candle

AI rule:

morning_star =
    strong_bearish_candle
AND small_body_candle
AND strong_bullish_candle

Interpretation:

bullish reversal pattern

---

## 5.2 Evening Star

Structure:

bullish candle
indecision candle
bearish candle

AI rule:

evening_star =
    strong_bullish_candle
AND small_body_candle
AND strong_bearish_candle

Interpretation:

bearish reversal pattern

---

# 6. WINDOW (GAP) SIGNALS

Rising window:

gap_up between candles

Interpretation:

bullish continuation

Falling window:

gap_down between candles

Interpretation:

bearish continuation

AI features:

gap_size
gap_direction

---

# 7. CANDLESTICK CONTEXT RULE

Candlestick signals must be filtered by market context.

AI rule:

valid_candle_signal =
    candlestick_pattern
AND support_resistance_context
AND trend_alignment

Optional confirmation:

volume_ratio > 1.2

---

# 8. FALSE SIGNAL FILTER

Signals are weak when:

trend strongly opposite
volume extremely low
pattern appears inside noisy consolidation

AI rule:

if signal AND weak_context:
    mark_low_confidence

---

# 9. FEATURE SET FOR AI

Recommended features:

body_percent
upper_shadow_ratio
lower_shadow_ratio
gap_size
gap_direction
pattern_type
pattern_strength

---

# 10. ROLE IN AI_STOCK ARCHITECTURE

market data
→ V4H candle feature extraction
→ candlestick_rulebook
→ R1 reasoning
→ X1 decision

Candlestick signals act as early sentiment indicators.

---

# 11. FINAL PRINCIPLE

Candlestick analysis hierarchy:

1 trend structure
2 support/resistance
3 candlestick signal
4 volume confirmation

Candlesticks provide early signals but must be confirmed by broader market structure.
