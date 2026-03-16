# OBV RULEBOOK — On Balance Volume Expert

Expert ID: V4OBV
Scale: -4 to +4
Generated: 2026-03-16
Status: ACTIVE

Primary Sources:
- Joseph Granville — New Key to Stock Market Profits (1963)
- John J. Murphy — Technical Analysis of the Financial Markets (1999), Chapter 7

---

## 1. FORMULA

```
If close[t] > close[t-1]:  OBV[t] = OBV[t-1] + volume[t]
If close[t] < close[t-1]:  OBV[t] = OBV[t-1] - volume[t]
If close[t] = close[t-1]:  OBV[t] = OBV[t-1]
```

OBV is a **cumulative** indicator. Absolute value is meaningless — only direction/trend matters.

---

## 2. SCORING RULES (-4 to +4)

### 2.1 OBV Trend Score (range -2 to +2)

Based on OBV slope over 20 days:

```
obv_slope = linear_regression_slope(OBV, 20 days)
obv_slope_normalized = obv_slope / avg_daily_volume
```

| Condition | Score |
|---|---|
| OBV slope strongly positive (> 0.5 std) | +2 |
| OBV slope mildly positive | +1 |
| OBV flat (slope near zero) | 0 |
| OBV slope mildly negative | -1 |
| OBV slope strongly negative (< -0.5 std) | -2 |

### 2.2 OBV vs Price Divergence Score (range -1 to +1)

```
+1 : Bullish divergence — price lower low, OBV higher low (accumulation)
-1 : Bearish divergence — price higher high, OBV lower high (distribution)
 0 : No divergence (OBV confirms price)
```

Lookback: 10-30 bars for divergence detection.

### 2.3 OBV Breakout Score (range -1 to +1)

```
+1 : OBV breaks to new 52-day high (before price does)
-1 : OBV breaks to new 52-day low (before price does)
 0 : No OBV breakout
```

OBV breakout preceding price breakout = **leading signal** (Granville's key insight).

### 2.4 Total Score

```
score = trend_score + divergence_score + breakout_score
score = clamp(score, -4, +4)
```

---

## 3. KEY RULES FROM GRANVILLE & MURPHY

### OBV Confirms Price (Murphy Ch.7)
- Price rising + OBV rising = healthy uptrend (confirmed)
- Price falling + OBV falling = healthy downtrend (confirmed)
- Confirmation = confidence in current trend

### OBV Divergence (Granville's Discovery)
- Price rising + OBV falling = **distribution** → smart money selling → bearish warning
- Price falling + OBV rising = **accumulation** → smart money buying → bullish warning
- This is the most powerful OBV signal

### OBV Leading Price (Granville)
- OBV breaking to new highs before price → price will follow up
- OBV breaking to new lows before price → price will follow down
- "OBV leads, price follows"

---

## 4. SIGNAL CODES

| Code | Meaning |
|---|---|
| V4OBV_BULL_TREND | OBV trending up, confirms uptrend |
| V4OBV_BEAR_TREND | OBV trending down, confirms downtrend |
| V4OBV_BULL_DIV | Bullish divergence (accumulation) |
| V4OBV_BEAR_DIV | Bearish divergence (distribution) |
| V4OBV_BULL_BREAK | OBV new high (leading signal) |
| V4OBV_BEAR_BREAK | OBV new low (leading signal) |
| V4OBV_NEUT_FLAT | OBV flat, no signal |

---

## 5. SIGNAL QUALITY

| Quality | Condition |
|---|---|
| 4 | Divergence + OBV breakout (leading + diverging) |
| 3 | Divergence alone or OBV breakout alone |
| 2 | Clear OBV trend confirming price |
| 1 | Weak OBV trend |
| 0 | OBV flat or insufficient data |

---

## 6. FEATURES FOR R LAYER

```
obv_slope_norm      : normalized OBV 20-day slope
obv_divergence      : +1(bullish) / -1(bearish) / 0
obv_new_high        : 1/0
obv_new_low         : 1/0
obv_confirms_price  : 1(confirms) / -1(diverges) / 0
```

---

## 7. EDGE CASES

- **Gap days**: Gap up on high volume creates large OBV jump — may not mean sustained buying
- **Low liquidity**: OBV unreliable for stocks with sporadic volume (< 100k shares/day)
- **VN ATC session**: Large volume at close is normal VN market structure

---

*OBV reveals the flow of volume — the force behind price movement.*
*Divergence between OBV and price is the most actionable signal.*
