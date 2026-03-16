# VOLUME RULEBOOK — Volume Behavior Expert

Expert ID: V4V
Scale: -4 to +4
Generated: 2026-03-16
Status: ACTIVE

Primary Sources:
- John J. Murphy — Technical Analysis of the Financial Markets (1999), Chapter 7
- Edwards & Magee — Technical Analysis of Stock Trends (9th Edition)

---

## 1. CORE PRINCIPLE (Murphy Ch.7)

"Volume should expand in the direction of the existing price trend."

```
Healthy uptrend   : rising price + rising volume
Healthy downtrend : falling price + rising volume
Warning sign      : rising price + declining volume
```

---

## 2. INDICATORS

```
vol_ratio    = volume[t] / SMA(volume, 20)
vol_trend_5  = SMA(volume, 5) / SMA(volume, 20)
climax       = volume[t] > 3 * SMA(volume, 20)
```

---

## 3. SCORING RULES (-4 to +4)

### 3.1 Volume-Price Confirmation (range -2 to +2)

| Condition | Score |
|---|---|
| Price up + vol surge (>2x) | +2 |
| Price up + above avg (>1.2x) | +1 |
| Price up + below avg (<0.8x) | -0.5 |
| Price down + vol surge (>2x) | -2 |
| Price down + above avg | -1 |
| Price down + below avg | +0.5 |

### 3.2 Volume Trend (range -1 to +1)

```
+1 : vol_trend_5 > 1.3
 0 : 0.7 to 1.3
-1 : vol_trend_5 < 0.7
```

### 3.3 Divergence (range -1 to +1)

```
+1 : Price falling + volume declining (exhausted selling)
-1 : Price rising + volume declining (weak rally)
 0 : No divergence
```

### Total
```
score = confirmation + trend + divergence, clamp -4..+4
```

---

## 4. KEY RULES FROM MURPHY

- Volume precedes price — expansion before breakout
- Climax volume marks reversals (top or bottom)
- Volume should increase on rallies, decrease on pullbacks in uptrend
- Breakout without volume = suspect

---

## 5. SIGNAL CODES

| Code | Meaning |
|---|---|
| V4V_BULL_EXPAND | Volume surge + price up |
| V4V_BEAR_EXPAND | Volume surge + price down |
| V4V_BULL_CONFIRM | Rising vol + uptrend |
| V4V_BEAR_CONFIRM | Rising vol + downtrend |
| V4V_BEAR_DIV | Price up, volume declining |
| V4V_BULL_DIV | Price down, volume declining |
| V4V_NEUT_DRY | Volume drying up |
| V4V_BULL_CLIMAX_BOT | Climax at bottom |
| V4V_BEAR_CLIMAX_TOP | Climax at top |

---

## 6. SIGNAL QUALITY

| Quality | Condition |
|---|---|
| 4 | Climax + reversal pattern |
| 3 | Surge (>2x) + clear direction |
| 2 | Above-avg + direction match |
| 1 | Mild change or divergence |
| 0 | Normal volume |

---

## 7. FEATURES FOR R LAYER

```
vol_ratio, vol_trend_5, vol_trend_10, vol_price_confirm,
vol_climax, vol_drying, vol_expansion
```

---

*Volume is the force behind price. Divergence is the most reliable warning.*
