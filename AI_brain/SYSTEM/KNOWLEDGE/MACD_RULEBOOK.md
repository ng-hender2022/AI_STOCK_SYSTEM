# MACD RULEBOOK — MACD Expert

Expert ID: V4MACD
Scale: -4 to +4
Generated: 2026-03-16
Status: ACTIVE

Primary Sources:
- Gerald Appel — The Moving Average Convergence-Divergence Trading Method (1979)
- John J. Murphy — Technical Analysis of the Financial Markets (1999), Chapter 10

---

## 1. INDICATORS

### MACD Line
```
MACD = EMA(close, 12) - EMA(close, 26)
```

### Signal Line
```
Signal = EMA(MACD, 9)
```

### Histogram
```
Histogram = MACD - Signal
```

Parameters: (12, 26, 9) — standard Appel settings.

---

## 2. SCORING RULES (-4 to +4)

### 2.1 Signal Line Cross Score (range -2 to +2)

| Condition | Score |
|---|---|
| MACD crosses above Signal AND both above zero | +2 |
| MACD crosses above Signal (below zero) | +1 |
| MACD above Signal (no fresh cross) | +0.5 |
| MACD = Signal (neutral) | 0 |
| MACD below Signal (no fresh cross) | -0.5 |
| MACD crosses below Signal (above zero) | -1 |
| MACD crosses below Signal AND both below zero | -2 |

Cross detection: MACD[t] > Signal[t] AND MACD[t-1] <= Signal[t-1] (or reverse).

### 2.2 Zero Line Score (range -1 to +1)

| Condition | Score |
|---|---|
| MACD > 0 AND rising | +1 |
| MACD > 0 AND falling | +0.5 |
| MACD near zero (|MACD| < threshold) | 0 |
| MACD < 0 AND rising | -0.5 |
| MACD < 0 AND falling | -1 |

Threshold = 0.5% of close price.

### 2.3 Histogram Momentum Score (range -0.5 to +0.5)

```
+0.5 : Histogram positive AND expanding (hist[t] > hist[t-1] > 0)
-0.5 : Histogram negative AND expanding (hist[t] < hist[t-1] < 0)
 0   : Histogram contracting or near zero
```

### 2.4 Divergence Score (range -1 to +1)

```
+1 : Bullish divergence (price lower low, MACD higher low)
-1 : Bearish divergence (price higher high, MACD lower high)
 0 : No divergence
```

Divergence lookback: 10-30 bars. Require at least 5 bars between MACD pivots.

### 2.5 Total Score

```
score = cross_score + zero_line_score + histogram_score + divergence_score
score = clamp(score, -4, +4)
```

---

## 3. KEY RULES FROM MURPHY

### Signal Line Crossovers (Ch.10)
- Most common MACD signal
- Buy: MACD crosses above signal line
- Sell: MACD crosses below signal line
- More significant when occurring far from zero line

### Zero Line Crossovers
- MACD crossing above zero = medium-term bullish confirmation
- MACD crossing below zero = medium-term bearish confirmation
- Stronger than signal line cross alone

### Divergence (Murphy emphasis)
- Bearish divergence: price makes new high but MACD does not → weakening momentum
- Bullish divergence: price makes new low but MACD does not → selling pressure diminishing
- Divergence is the **most important** MACD signal per Murphy

### Histogram (Appel)
- Histogram measures distance between MACD and Signal
- Histogram shrinking = momentum decelerating (early warning)
- Histogram reversing direction = earliest signal of change

---

## 4. SIGNAL CODES

| Code | Meaning |
|---|---|
| V4MACD_BULL_CROSS | MACD crossed above signal line |
| V4MACD_BEAR_CROSS | MACD crossed below signal line |
| V4MACD_BULL_CROSS_ZERO | MACD crossed above zero line |
| V4MACD_BEAR_CROSS_ZERO | MACD crossed below zero line |
| V4MACD_BULL_DIV | Bullish divergence detected |
| V4MACD_BEAR_DIV | Bearish divergence detected |
| V4MACD_BULL_HIST_EXPAND | Histogram positive and expanding |
| V4MACD_BEAR_HIST_EXPAND | Histogram negative and expanding |
| V4MACD_NEUT_FLAT | MACD near zero, no signal |

---

## 5. SIGNAL QUALITY

| Quality | Condition |
|---|---|
| 4 | Signal cross + zero line confirm + divergence |
| 3 | Signal cross + zero line confirm OR divergence alone |
| 2 | Signal cross only, clear direction |
| 1 | MACD trending but no cross |
| 0 | MACD flat near zero |

---

## 6. FEATURES FOR R LAYER

```
macd_value          : MACD line value (normalized by close)
signal_value        : Signal line value
histogram_value     : Histogram value
macd_slope          : (MACD[t] - MACD[t-3]) / close
histogram_slope     : (hist[t] - hist[t-3]) / close
macd_above_signal   : 1 / -1
macd_above_zero     : 1 / -1
divergence_flag     : +1 (bullish) / -1 (bearish) / 0
```

---

## 7. EDGE CASES

- **Whipsaw in sideways market**: MACD crosses frequently when ADX < 20 — reduce quality
- **Fast-moving VN stocks**: MACD may lag significantly — histogram is better early warning
- **Gap opens**: Gap through signal line = count as cross, but quality reduced by 1
- **Ceiling/floor**: Constrained prices compress MACD — note in metadata

---

*MACD combines trend-following and momentum in one indicator.*
*Divergence is the most powerful signal. Cross is the most common.*
