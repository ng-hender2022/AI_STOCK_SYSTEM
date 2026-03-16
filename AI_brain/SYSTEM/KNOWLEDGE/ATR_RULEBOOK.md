# ATR RULEBOOK — ATR Volatility Expert

Expert ID: V4ATR
Scale: 0 to 4 (volatility magnitude, direction-neutral)
Generated: 2026-03-16
Status: ACTIVE

Primary Sources:
- J. Welles Wilder — New Concepts in Technical Trading Systems (1978)
- John J. Murphy — Technical Analysis of the Financial Markets (1999), Chapter 15

---

## 1. FORMULA

### True Range
```
TR = max(H - L, |H - prevC|, |L - prevC|)
```

### ATR
```
ATR(14) = smoothed average of TR over 14 periods
First ATR = simple average of first 14 TRs
Subsequent: ATR = (prev_ATR * 13 + TR) / 14
```

### ATR Percent
```
ATR_pct = ATR / Close * 100
```

---

## 2. SCORING RULES (0 to 4)

Score based on ATR_pct percentile within 120-day lookback:

| Percentile | Score | Label |
|---|---|---|
| 0-20th | 0 | VERY_LOW_VOL |
| 20-40th | 1 | LOW_VOL |
| 40-65th | 2 | NORMAL_VOL |
| 65-85th | 3 | HIGH_VOL |
| 85-100th | 4 | EXTREME_VOL |

---

## 3. ADDITIONAL FEATURES

### ATR Expansion/Contraction
```
atr_change = (ATR[t] - ATR[t-5]) / ATR[t-5]
EXPANDING: > +0.10 | CONTRACTING: < -0.10 | STABLE: else
```

### Volatility Regime
```
SQUEEZE: percentile < 15 AND contracting
EXPANSION: percentile > 80 AND expanding
CLIMAX: percentile > 95
NORMAL: otherwise
```

### ATR Ratio
```
atr_ratio = ATR(14) / SMA(ATR(14), 50)
```

---

## 4. KEY RULES FROM WILDER & MURPHY

- Volatility is mean-reverting: extremes predict change
- ATR for stops: trailing stop = Close - 2 * ATR
- ATR expanding with direction = strong trend
- ATR at extreme high = possible exhaustion

---

## 5. SIGNAL CODES

| Code | Meaning |
|---|---|
| V4ATR_NEUT_SQUEEZE | Very low ATR, potential squeeze |
| V4ATR_BULL_EXPAND | ATR expanding + price up |
| V4ATR_BEAR_EXPAND | ATR expanding + price down |
| V4ATR_BEAR_EXTREME | ATR spike, panic |
| V4ATR_NEUT_CLIMAX | ATR extreme, exhaustion |
| V4ATR_NEUT_NORMAL | Normal volatility |

---

## 6. SIGNAL QUALITY

| Quality | Condition |
|---|---|
| 4 | Extreme ATR with clear setup |
| 3 | ATR at percentile extremes |
| 2 | Noticeable expansion/contraction |
| 1 | Slightly outside normal |
| 0 | Normal range |

---

## 7. FEATURES FOR R LAYER

```
atr_value, atr_pct, atr_percentile, atr_ratio,
atr_change_5d, atr_expanding, atr_contracting, vol_regime
```

---

*ATR measures market temperature. Extremes are the most informative.*
