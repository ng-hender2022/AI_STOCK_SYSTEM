# V4TREND_PATTERN RULEBOOK — Trend Pattern Expert

Expert ID: V4TREND_PATTERN
Scale: -4 to +4
Generated: 2026-03-16
Status: ACTIVE

Primary Source:
- Edwards & Magee — Technical Analysis of Stock Trends (9th Edition)

---

## 1. CORE PRINCIPLE

Price patterns represent supply-demand structure in the market.
A pattern is NOT valid until confirmed by breakout + volume.

```
valid_pattern = pattern_shape AND breakout_confirmation AND volume_participation
```

---

## 2. CONTINUATION PATTERNS

### 2.1 Flag

**Structure**:
- Sharp impulse move (flagpole): minimum 5% move in <= 5 bars
- Small parallel consolidation: 3-5 bars minimum, 8 bars maximum
- Consolidation slopes against the prior trend

**Detection logic**:
```
bull_flag:
    flagpole_return >= +5% in <= 5 bars
    consolidation: lower highs AND lower lows (3-5 bars)
    consolidation_range < 50% of flagpole

bear_flag:
    flagpole_return <= -5% in <= 5 bars
    consolidation: higher highs AND higher lows (3-5 bars)
    consolidation_range < 50% of flagpole
```

**Breakout confirmation**:
```
close breaks above flag high (bull) or below flag low (bear)
volume_at_breakout > 1.3 * avg_volume_20
```

**Target (measuring technique)**:
```
target = breakout_price ± flagpole_distance
```

---

### 2.2 Pennant

**Structure**:
- Sharp impulse move (same as flag)
- Converging consolidation (small symmetrical triangle): 5-15 bars
- Decreasing volume during consolidation

**Detection logic**:
```
lower_highs AND higher_lows (converging)
duration: 5-15 bars
volume_declining during consolidation
```

**Target**: Same as flag (flagpole projection).

---

### 2.3 Triangle — Ascending

**Structure**:
- Flat resistance (horizontal upper boundary)
- Rising support (higher lows)
- Minimum 4 touches total (2 upper + 2 lower)
- Duration: 10-40 bars

**Detection**:
```
upper_touches: highs within 0.5% of resistance level (>= 2)
lower_touches: rising lows (>= 2)
```

**Breakout**: Close above flat resistance with volume.
**Bias**: Bullish (usually breaks up).
**Target**: Pattern height added to breakout point.

---

### 2.4 Triangle — Descending

**Structure**:
- Flat support (horizontal lower boundary)
- Falling resistance (lower highs)
- Minimum 4 touches total

**Bias**: Bearish (usually breaks down).
**Target**: Pattern height subtracted from breakout point.

---

### 2.5 Triangle — Symmetrical

**Structure**:
- Converging upper and lower boundaries
- Lower highs AND higher lows
- Minimum 4 touches

**Bias**: Neutral (breaks in direction of prior trend).
**Target**: Base width projected from breakout.

---

## 3. REVERSAL PATTERNS

### 3.1 Head and Shoulders (Top)

**Structure**:
```
left_shoulder_high < head_high > right_shoulder_high
left_shoulder_high ≈ right_shoulder_high (within 5%)
neckline = line connecting troughs between shoulders
```

**Minimum bars**: 20 bars from left shoulder start to right shoulder end.

**Confirmation**:
```
close < neckline
volume_at_head < volume_at_left_shoulder (decreasing volume)
volume_at_breakout > avg_volume
```

**Target**:
```
target = neckline - (head_high - neckline)
```

---

### 3.2 Inverse Head and Shoulders (Bottom)

Mirror of H&S top. All rules reversed.

```
left_shoulder_low > head_low < right_shoulder_low
confirmation: close > neckline
target = neckline + (neckline - head_low)
```

---

### 3.3 Double Top

**Structure**:
```
peak1 ≈ peak2 (within 2%)
valley between peaks = support
minimum 10 bars between peaks
```

**Confirmation**: Close below valley support.
**Target**: Valley support - (peak - valley).

---

### 3.4 Double Bottom

Mirror of double top.

```
trough1 ≈ trough2 (within 2%)
confirmation: close > resistance between troughs
target = resistance + (resistance - trough)
```

---

### 3.5 Rounding Top / Bottom

**Structure**:
- Gradual curved price action (20+ bars)
- Volume typically mirrors price curve (U-shape for bottom)
- Slow transition, not sharp

**Detection**: Regression curve fitting or rolling momentum decline/increase.

---

## 4. BREAKOUT CONFIRMATION RULES

All patterns require breakout confirmation:

| Rule | Threshold |
|---|---|
| Price closes beyond pattern boundary | Required |
| Volume at breakout vs 20-day average | >= 1.3x |
| Close sustained beyond boundary | 2 consecutive closes preferred |
| No re-entry into pattern within 2 bars | Required (else false breakout) |

---

## 5. PATTERN FAILURE DETECTION

```
pattern_failure:
    breakout occurs
    BUT price re-enters pattern within 2-3 bars
    AND volume declines after breakout

failure_signal:
    reverse the pattern direction
    failed_bull_breakout → bearish signal
    failed_bear_breakdown → bullish signal
```

Pattern failures are often **stronger signals** than the original pattern.

---

## 6. SCORING RULES (-4 to +4)

### 6.1 Pattern Score (range -2 to +2)

| Pattern | Bullish Score | Bearish Score |
|---|---|---|
| H&S confirmed | — | -2 |
| Inverse H&S confirmed | +2 | — |
| Double top confirmed | — | -2 |
| Double bottom confirmed | +2 | — |
| Bull flag/pennant breakout | +1.5 | — |
| Bear flag/pennant breakdown | — | -1.5 |
| Ascending triangle breakout | +1.5 | — |
| Descending triangle breakdown | — | -1.5 |
| Symmetrical triangle breakout | +1 | -1 |
| Rounding bottom | +1 | — |
| Rounding top | — | -1 |
| No pattern detected | 0 | 0 |

### 6.2 Confirmation Score (range -1 to +1)

```
+1 : Price + volume breakout confirmed (2 closes)
 0 : Pattern detected but no breakout yet
-1 : Pattern failure detected (reverse signal)
```

### 6.3 Target Score (range -1 to +1)

```
+1 : Bullish target > 5% from breakout
-1 : Bearish target < -5% from breakout
 0 : Target < 5% or no target calculable
```

### 6.4 Total Score

```
score = pattern_score + confirmation_score + target_score
score = clamp(score, -4, +4)
```

---

## 7. SIGNAL CODES

| Code | Meaning |
|---|---|
| V4TP_BULL_FLAG | Bull flag breakout |
| V4TP_BEAR_FLAG | Bear flag breakdown |
| V4TP_BULL_PENNANT | Bull pennant breakout |
| V4TP_BEAR_PENNANT | Bear pennant breakdown |
| V4TP_BULL_TRI_ASC | Ascending triangle breakout |
| V4TP_BEAR_TRI_DESC | Descending triangle breakdown |
| V4TP_BULL_TRI_SYM | Symmetrical triangle bullish breakout |
| V4TP_BEAR_TRI_SYM | Symmetrical triangle bearish breakdown |
| V4TP_BEAR_HS | Head & Shoulders confirmed |
| V4TP_BULL_IHS | Inverse H&S confirmed |
| V4TP_BEAR_DOUBLE_TOP | Double top confirmed |
| V4TP_BULL_DOUBLE_BOT | Double bottom confirmed |
| V4TP_BULL_ROUND_BOT | Rounding bottom |
| V4TP_BEAR_ROUND_TOP | Rounding top |
| V4TP_BULL_FAILURE | Bear pattern failure (bullish) |
| V4TP_BEAR_FAILURE | Bull pattern failure (bearish) |
| V4TP_NEUT_NO_PATTERN | No pattern detected |
| V4TP_NEUT_FORMING | Pattern forming, no breakout yet |

---

## 8. SIGNAL QUALITY

| Quality | Condition |
|---|---|
| 4 | Major reversal (H&S, double) + volume confirmed + 2 closes |
| 3 | Continuation pattern + volume breakout |
| 2 | Pattern detected + single close breakout |
| 1 | Pattern forming, no breakout yet |
| 0 | No pattern |

---

## 9. EDGE CASES

- **Gap breakouts (VN market)**: Gap through pattern boundary = strong confirmation (treat as 2x volume)
- **Ceiling/floor constrained**: Ceiling hit prevents measuring true pattern boundary — reduce quality by 1
- **Low volume patterns**: If avg volume < 100k shares, pattern quality capped at 2
- **Overlapping patterns**: If multiple patterns detected, use the one with highest quality
- **Pattern duration**: Patterns lasting < 5 bars are noise, ignore. Patterns > 60 bars lose relevance
- **Pattern within pattern**: Larger timeframe pattern takes priority

---

## 10. MEASURING TECHNIQUE SUMMARY

| Pattern | Target Calculation |
|---|---|
| Flag/Pennant | Flagpole distance from breakout |
| Triangle | Base width from breakout |
| H&S | Head-to-neckline distance from neckline |
| Double Top/Bottom | Pattern height from breakout |
| Rectangle | Range height from breakout |

---

## 11. DATA LEAKAGE

- Pattern detection uses data up to T-1 only
- Breakout confirmation requires close at T-1 (not T)
- Target projection is forward-looking but NOT a feature — only used for target_score

---

*Patterns are structure. Breakouts are signals. Volume is confirmation.*
*Pattern + breakout + volume = actionable signal.*
