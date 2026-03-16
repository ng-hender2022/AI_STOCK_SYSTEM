# V4SR RULEBOOK — Support/Resistance Expert

Expert ID: V4SR
Scale: -4 to +4
Generated: 2026-03-16
Status: ACTIVE

Primary Sources:
- Edwards & Magee — Technical Analysis of Stock Trends (9th Edition)
- Adam Grimes — The Art and Science of Technical Analysis (2012)

---

## 1. CORE PRINCIPLE

Support and resistance are **zones**, not exact prices (Grimes).
Levels gain strength through repeated tests and lose strength over time.
Old support becomes new resistance after breakout, and vice versa (Edwards & Magee).

---

## 2. SWING HIGH/LOW DETECTION

### Definition

```
Swing High: bar[i].high > bar[i-N..i-1].high AND bar[i].high > bar[i+1..i+N].high
Swing Low:  bar[i].low  < bar[i-N..i-1].low  AND bar[i].low  < bar[i+1..i+N].low
```

### Parameters

| Parameter | Value | Note |
|---|---|---|
| N (minimum bars each side) | 3 | Confirmed swing requires 3 bars on each side |
| N_strong | 5 | Strong swing requires 5 bars each side |
| Lookback window | 120 days | Scan back 120 trading days for levels |

---

## 3. SR ZONE CONSTRUCTION

### Zone Width

```
zone_width = ATR(14) * zone_multiplier
zone_multiplier = 0.5  (default)

zone_upper = swing_price + zone_width / 2
zone_lower = swing_price - zone_width / 2
```

ATR-based width adapts to volatility of each stock.

### Zone Merging

If two swing points are within 1 ATR of each other, merge into single zone:
```
merged_price = weighted_average(prices, weights=touch_counts)
merged_width = max(zone1_upper, zone2_upper) - min(zone1_lower, zone2_lower)
```

---

## 4. ZONE STRENGTH

### Touch Count

```
strength_touches = number of times price entered zone and reversed
```

Each touch adds +1 to strength. Maximum meaningful strength = 5.

### Age Decay

Older levels lose relevance:

```
age_factor = max(0.3, 1.0 - (days_since_formation / decay_period))
decay_period = 120 days
```

### Volume Confirmation

```
volume_factor = avg_volume_at_touches / avg_volume_overall
```

If volume_factor > 1.5 → zone is institution-recognized.

### Combined Strength

```
zone_strength = strength_touches * age_factor * min(2.0, volume_factor)
```

Range: 0 to ~10 (capped practical range)

---

## 5. ROLE REVERSAL (Polarity)

From Edwards & Magee:

```
IF support_zone is broken (close < zone_lower for 2+ days):
    support_zone → becomes resistance_zone

IF resistance_zone is broken (close > zone_upper for 2+ days):
    resistance_zone → becomes support_zone
```

Role-reversed zones retain 70% of their original strength.

---

## 6. DISTANCE SCORING

```
dist_to_nearest_support = (close - nearest_support_price) / close
dist_to_nearest_resistance = (nearest_resistance_price - close) / close
```

### Position Score

| Condition | Score |
|---|---|
| At strong support (within zone, strength >= 3) | +2 |
| Near support (within 1 ATR, strength >= 2) | +1 |
| At strong resistance (within zone, strength >= 3) | -2 |
| Near resistance (within 1 ATR, strength >= 2) | -1 |
| Between levels, no proximity | 0 |
| Breakout above resistance confirmed | +2 |
| Breakdown below support confirmed | -2 |

---

## 7. SCORING RULES (-4 to +4)

### 7.1 Position Score (range -2 to +2)

Based on distance scoring table above.

### 7.2 Strength Score (range -1 to +1)

```
IF near support:
    strength_score = +min(1.0, zone_strength / 5)
IF near resistance:
    strength_score = -min(1.0, zone_strength / 5)
IF between levels:
    strength_score = 0
```

### 7.3 Context Score (range -1 to +1)

```
+1 : Price bouncing from support + rising volume
-1 : Price rejected from resistance + rising volume
 0 : No clear reaction
```

### 7.4 Total Score

```
score = position_score + strength_score + context_score
score = clamp(score, -4, +4)
```

---

## 8. SIGNAL CODES

| Code | Meaning |
|---|---|
| V4SR_BULL_AT_SUPPORT | Price at support zone |
| V4SR_BEAR_AT_RESISTANCE | Price at resistance zone |
| V4SR_BULL_BREAK_RESISTANCE | Breakout above resistance |
| V4SR_BEAR_BREAK_SUPPORT | Breakdown below support |
| V4SR_BULL_POLARITY_SUPPORT | Role-reversed resistance now acting as support |
| V4SR_BEAR_POLARITY_RESISTANCE | Role-reversed support now acting as resistance |
| V4SR_NEUT_BETWEEN_LEVELS | Price between S/R levels |
| V4SR_BULL_BOUNCE | Bounce from support with volume |
| V4SR_BEAR_REJECT | Rejection from resistance with volume |

---

## 9. SIGNAL QUALITY

| Quality | Condition |
|---|---|
| 4 | Strong zone (3+ touches) + volume confirmation + breakout/bounce |
| 3 | Strong zone + clear reaction |
| 2 | Moderate zone (2 touches) or near level |
| 1 | Weak zone (1 touch) or far from levels |
| 0 | No identifiable S/R nearby |

---

## 10. EDGE CASES

- **Gap through level**: Level is invalidated, not tested
- **Ceiling/floor price (VN)**: Artificially constrained — treat ceiling days as potential resistance break attempts
- **Low volume stocks**: Fewer touches needed to validate (2 instead of 3)
- **IPO stocks**: Not enough history — reduce lookback to available data, quality capped at 2
- **Breakout failure**: If price returns within zone in 2 days → false breakout → reverse signal

---

## 11. DATA LEAKAGE

- All swing detection uses data up to T-1 only
- N bars on right side of swing = uses T-1, T-2, T-3 (past data)
- NEVER use T data for zone construction or scoring

---

*Support/Resistance zones are the battlefield of supply and demand.*
*Zone strength + volume + polarity = the complete SR picture.*
