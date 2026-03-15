
# PATTERN_STRUCTURE_RULEBOOK

SYSTEM:
AI_STOCK KNOWLEDGE MODULE

MODULE NAME:
PATTERN_STRUCTURE_RULEBOOK

PRIMARY SOURCE:
Technical Analysis of Stock Trends – Edwards & Magee (9th Edition)

PURPOSE:
Define how AI detects and interprets classical chart patterns based on market structure.

Patterns represent the interaction between supply and demand and become valid signals only after breakout confirmation.

---

# 1. CORE PRINCIPLE

Price patterns represent supply–demand structure.

pattern_detected = price_structure

However:

pattern_valid = pattern_detected AND breakout_confirmation

AI must never trade based only on pattern shape without breakout.

---

# 2. PATTERN CATEGORIES

Patterns fall into two groups:

Reversal patterns
Continuation patterns

---

# 3. MAJOR REVERSAL PATTERNS

These patterns indicate potential trend reversal.

## 3.1 Head and Shoulders

Structure:

left_shoulder
head
right_shoulder
neckline

Detection logic:

head > left_shoulder_high
head > right_shoulder_high

Breakout confirmation:

close < neckline

Target estimation:

target_price = neckline - (head - neckline)

---

## 3.2 Inverse Head and Shoulders

Structure:

left_trough
head
right_trough

Confirmation:

close > neckline

Target:

target_price = neckline + (neckline - head)

---

## 3.3 Double Top

Structure:

peak1 ≈ peak2

Confirmation:

close < support_between_peaks

AI rule:

abs(peak1 - peak2) < tolerance

---

## 3.4 Double Bottom

Structure:

trough1 ≈ trough2

Confirmation:

close > resistance_between_troughs

---

## 3.5 Triple Top / Triple Bottom

Structure:

three equal highs or lows

Confirmation occurs when support/resistance breaks.

---

# 4. CONTINUATION PATTERNS

Continuation patterns indicate pause in existing trend.

## 4.1 Triangle

Types:

ascending
descending
symmetrical

Detection:

series_of_lower_highs
series_of_higher_lows

Breakout:

price exits triangle boundary

Target:

triangle_height projected from breakout.

---

## 4.2 Flag

Structure:

sharp impulse move
small parallel consolidation

AI logic:

flagpole_move > threshold

continuation expected after breakout.

---

## 4.3 Pennant

Similar to flag but consolidation converges.

Structure:

small symmetrical triangle after impulse move.

---

## 4.4 Rectangle

Structure:

horizontal support and resistance.

Detection:

multiple touches of upper and lower boundaries.

Breakout direction determines continuation.

---

## 4.5 Wedge

Structure:

converging price movement with slope.

Types:

rising wedge
falling wedge

Breakout usually opposite wedge slope.

---

# 5. BREAKOUT CONFIRMATION RULES

Patterns are not valid until breakout occurs.

AI rule:

valid_pattern =
    pattern_detected
AND breakout_candle
AND momentum_confirmation

Optional confirmation:

volume_ratio > 1.5

---

# 6. FALSE BREAKOUT FILTER

False breakout probability increases when:

volume_low
breakout_range_small
price_returns_inside_pattern

AI rule:

if breakout AND quick_reversal:
    mark_false_breakout

---

# 7. PATTERN TARGET PROJECTION

Common target estimation:

target = pattern_height

Examples:

head_shoulders_target = head_height
triangle_target = base_height
rectangle_target = range_height

---

# 8. PATTERN FEATURE SET FOR AI

Recommended features:

pattern_type
pattern_height
pattern_duration
breakout_strength
volume_breakout_ratio
pattern_symmetry_score

---

# 9. ROLE IN AI_STOCK ARCHITECTURE

market data
→ V4D / V4H feature extraction
→ pattern detection
→ pattern_structure_rulebook
→ R1 reasoning
→ X1 decision

---

# 10. FINAL PRINCIPLE

Pattern analysis must follow this hierarchy:

1 price structure
2 breakout confirmation
3 volume participation
4 trend context

Pattern shape alone is insufficient for signal generation.
