# BOLLINGER BANDS RULEBOOK — Bollinger Bands Expert

Expert ID: V4BB
Scale: -4 to +4
Generated: 2026-03-16
Status: ACTIVE

Primary Sources:
- John Bollinger — Bollinger on Bollinger Bands (2001)
- John J. Murphy — Technical Analysis of the Financial Markets (1999)

---

## 1. FORMULA

```
Middle Band = SMA(close, 20)
Upper Band  = Middle + 2 * StdDev(close, 20)
Lower Band  = Middle - 2 * StdDev(close, 20)

%B         = (Close - Lower) / (Upper - Lower)
Bandwidth  = (Upper - Lower) / Middle
```

Parameters: (20, 2) — Bollinger's standard.

---

## 2. SCORING RULES (-4 to +4)

### 2.1 Position Score (range -2 to +2)

| Condition | Score |
|---|---|
| Close > Upper Band (%B > 1.0) | +2 |
| Close between Middle and Upper (0.5 < %B <= 1.0) | +1 |
| Close near Middle (0.4 <= %B <= 0.6) | 0 |
| Close between Lower and Middle (0.0 <= %B < 0.5) | -1 |
| Close < Lower Band (%B < 0.0) | -2 |

### 2.2 Squeeze Score (range -1 to +1)

```
squeeze_percentile = percentile_rank(bandwidth, 120 days)

IF squeeze_percentile < 10:
    squeeze active, score based on breakout direction:
    +1 if breaks above upper, -1 if breaks below lower, 0 if no break yet
ELSE:
    score = 0
```

### 2.3 Band Walk Score (range -0.5 to +0.5)

```
+0.5 : Close near/above upper band for 3+ bars
-0.5 : Close near/below lower band for 3+ bars
 0   : No band walk
```

### 2.4 Reversal Score (range -0.5 to +0.5)

W-Bottom / M-Top (Bollinger):
```
W-Bottom: second low has higher %B than first → +0.5
M-Top: second high has lower %B than first → -0.5
```

### 2.5 Total Score

```
score = position_score + squeeze_score + band_walk_score + reversal_score
score = clamp(score, -4, +4)
```

---

## 3. KEY RULES FROM BOLLINGER

- **Squeeze**: Narrow bands = low volatility = coming breakout
- **Band Walk**: Strong trends ride upper/lower band — NOT overbought/oversold
- **%B**: Core numeric feature (0-1 range, can exceed)
- **W-Bottom / M-Top**: Bollinger's preferred reversal patterns

---

## 4. SIGNAL CODES

| Code | Meaning |
|---|---|
| V4BB_BULL_BREAK | Close above upper band |
| V4BB_BEAR_BREAK | Close below lower band |
| V4BB_BULL_SQUEEZE | Squeeze resolved upward |
| V4BB_BEAR_SQUEEZE | Squeeze resolved downward |
| V4BB_BULL_WALK | Walking upper band |
| V4BB_BEAR_WALK | Walking lower band |
| V4BB_BULL_REVERSAL | W-Bottom pattern |
| V4BB_BEAR_REVERSAL | M-Top pattern |
| V4BB_NEUT_SQUEEZE | Squeeze active, no direction |
| V4BB_NEUT_MID | Price near middle band |

---

## 5. SIGNAL QUALITY

| Quality | Condition |
|---|---|
| 4 | Squeeze breakout + band walk + volume |
| 3 | Squeeze breakout or W/M pattern |
| 2 | Clear position beyond bands |
| 1 | Near band but no pattern |
| 0 | Price near middle, no squeeze |

---

## 6. FEATURES FOR R LAYER

```
bb_pct_b, bb_bandwidth, bb_squeeze_active, bb_position,
bb_bandwidth_pctile, bb_band_walk
```

---

*Bollinger Bands measure volatility. Squeeze predicts breakout.*
*%B is the key numeric feature. Band walk shows trend strength.*
