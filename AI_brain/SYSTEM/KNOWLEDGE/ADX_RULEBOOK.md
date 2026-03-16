# ADX RULEBOOK — Trend Strength Expert

Expert ID: V4ADX
Scale: 0 to 4 (strength only, direction-neutral)
Generated: 2026-03-16
Status: ACTIVE

Primary Sources:
- J. Welles Wilder — New Concepts in Technical Trading Systems (1978)
- John J. Murphy — Technical Analysis of the Financial Markets (1999), Chapter 15

---

## 1. INDICATORS

### ADX (Average Directional Index)
```
+DM = H[t] - H[t-1]  (if positive and > -DM, else 0)
-DM = L[t-1] - L[t]   (if positive and > +DM, else 0)
TR  = max(H-L, |H-prevC|, |L-prevC|)

+DI(14) = 100 * smoothed(+DM, 14) / smoothed(TR, 14)
-DI(14) = 100 * smoothed(-DM, 14) / smoothed(TR, 14)

DX  = 100 * |+DI - -DI| / (+DI + -DI)
ADX = smoothed(DX, 14)
```

Period: 14 (Wilder standard)

### ADXR (ADX Rating)
```
ADXR = (ADX[today] + ADX[14 bars ago]) / 2
```
Smoother version of ADX, slower to react.

---

## 2. SCORING RULES (0 to 4)

ADX measures **trend strength only** — direction is captured in signal_code, not in the score.

| ADX Value | Score | Label | Meaning |
|---|---|---|---|
| ADX < 15 | 0 | NO_TREND | No meaningful trend, choppy market |
| 15 <= ADX < 20 | 1 | WEAK | Emerging trend or fading trend |
| 20 <= ADX < 25 | 2 | MODERATE | Trend developing |
| 25 <= ADX < 40 | 3 | STRONG | Established trend |
| ADX >= 40 | 4 | VERY_STRONG | Extreme trend (watch for exhaustion) |

### Direction (in signal_code and metadata, not in score)
```
BULLISH  : +DI > -DI
BEARISH  : -DI > +DI
NEUTRAL  : |+DI - -DI| < 3
```

### ADX Slope Modifier
```
adx_rising  : ADX[t] > ADX[t-3]  → trend strengthening
adx_falling : ADX[t] < ADX[t-3]  → trend weakening
```

### DI Crossover (event signal)
```
bullish_di_cross : +DI crosses above -DI
bearish_di_cross : -DI crosses above +DI
```

---

## 3. KEY RULES FROM WILDER & MURPHY

### Trend Strength Interpretation (Murphy Ch.15)
- ADX rising = trend strengthening regardless of direction
- ADX falling = trend weakening, entering range
- ADX < 20 for extended period → expect breakout eventually
- ADX peaking above 40-45 → trend may be exhausting (watch for reversal)

### DI Cross Rules (Wilder)
- +DI crossing above -DI = bullish signal
- -DI crossing above +DI = bearish signal
- Most reliable when ADX > 20 at time of cross
- DI cross with ADX < 15 = unreliable (choppy market)

### Extreme Point Rule (Wilder)
- On day of DI cross, note extreme point (high for bull cross, low for bear cross)
- If price violates extreme point in days after cross → confirms signal
- If price does NOT violate → signal may fail

---

## 4. SIGNAL CODES

| Code | Meaning |
|---|---|
| V4ADX_BULL_TREND_STRONG | ADX > 25, +DI > -DI, trend strong |
| V4ADX_BEAR_TREND_STRONG | ADX > 25, -DI > +DI, trend strong |
| V4ADX_BULL_TREND_START | ADX rising from < 20, +DI > -DI |
| V4ADX_BEAR_TREND_START | ADX rising from < 20, -DI > +DI |
| V4ADX_NEUT_TREND_WEAK | ADX < 20, no clear trend |
| V4ADX_BULL_DI_CROSS | +DI just crossed above -DI |
| V4ADX_BEAR_DI_CROSS | -DI just crossed above +DI |
| V4ADX_NEUT_EXHAUSTION | ADX > 40 and falling (trend exhausting) |

---

## 5. SIGNAL QUALITY

| Quality | Condition |
|---|---|
| 4 | ADX > 30 + DI cross confirmed + ADX rising |
| 3 | ADX > 25 + clear DI separation |
| 2 | ADX 20-25 or DI cross with moderate ADX |
| 1 | ADX 15-20, weak signal |
| 0 | ADX < 15, no trend |

---

## 6. SECONDARY SCORE

```
secondary_score = +DI - -DI  (raw directional difference)
```
Range: roughly -50 to +50. Provides direction + magnitude for R Layer.

---

## 7. EDGE CASES

- **ADX > 50**: Very rare, usually in panic/crash — score stays 4 but signal exhaustion
- **+DI = -DI**: No trend direction, score = ADX-based but signal = NEUTRAL
- **Whipsaw filter**: Ignore DI crosses if ADX < 15 (Murphy recommendation)
- **Vietnam market**: During ceiling/floor days, ADX may spike artificially — note in metadata

---

*ADX tells you IF there is a trend. DI tells you the direction.*
*Strong ADX + clear DI = high confidence trend signal.*
