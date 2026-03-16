# STOCHASTIC RULEBOOK — Stochastic Expert

Expert ID: V4STO
Scale: 0 to 100 (raw %K value as primary_score)
Generated: 2026-03-16
Status: ACTIVE

Primary Sources:
- George C. Lane — Stochastic Oscillator (1950s)
- John J. Murphy — Technical Analysis of the Financial Markets (1999), Chapter 10

---

## 1. FORMULA

### Fast Stochastic
```
%K(14) = 100 * (Close - Lowest_Low_14) / (Highest_High_14 - Lowest_Low_14)
%D(3)  = SMA(%K, 3)
```

### Slow Stochastic (preferred for daily)
```
Slow %K = Fast %D = SMA(Fast %K, 3)
Slow %D = SMA(Slow %K, 3)
```

Parameters: (14, 3, 3) — standard settings.

---

## 2. PRIMARY SCORE

```
primary_score = Slow %K value (0 to 100)
```

---

## 3. SIGNAL LOGIC

### 3.1 Overbought / Oversold

| Condition | Label |
|---|---|
| %K > 80 | OVERBOUGHT |
| %K < 20 | OVERSOLD |
| 20 <= %K <= 80 | NEUTRAL |

### 3.2 %K/%D Crossover (Murphy/Lane)

```
Bullish cross: %K crosses above %D (best when both below 20)
Bearish cross: %K crosses below %D (best when both above 80)
```

**Key rule from Lane**: Crosses are ONLY significant in OB/OS zones.
Crosses in the middle zone (30-70) are unreliable — ignore them.

### 3.3 Divergence

```
Bullish divergence: price lower low, %K higher low (in OS zone)
Bearish divergence: price higher high, %K lower high (in OB zone)
```

### 3.4 Hinge Pattern (Lane)

When %D slows its rate of change (curve flattens) before %K cross:
```
%D slope approaching zero while %K still moving → early reversal signal
```

### 3.5 Setup/Failure (Lane Advanced)

```
Bearish setup: first OB reading → potential weakness
Bearish failure: second OB reading lower than first → confirmed sell
```

---

## 4. SCORING FOR SIGNAL_QUALITY (0 to 4)

| Quality | Condition |
|---|---|
| 4 | Divergence + %K/%D cross in OB/OS zone |
| 3 | %K/%D cross in OB/OS zone (< 20 or > 80) |
| 2 | %K/%D cross near OB/OS (20-30 or 70-80) |
| 1 | OB/OS zone reached but no cross |
| 0 | %K in neutral zone, no cross |

---

## 5. SIGNAL CODES

| Code | Meaning |
|---|---|
| V4STO_BULL_CROSS | %K crossed above %D in oversold zone |
| V4STO_BEAR_CROSS | %K crossed below %D in overbought zone |
| V4STO_BULL_EXTREME_OS | %K < 20, oversold |
| V4STO_BEAR_EXTREME_OB | %K > 80, overbought |
| V4STO_BULL_DIV | Bullish divergence |
| V4STO_BEAR_DIV | Bearish divergence |
| V4STO_NEUT_MID | %K in neutral zone |

---

## 6. FEATURES FOR R LAYER

```
stoch_k            : Slow %K (0-100)
stoch_d            : Slow %D (0-100)
stoch_k_slope      : (%K[t] - %K[t-3]) / 100
k_above_d          : 1 / -1
stoch_zone         : -1(OS) / 0(neutral) / +1(OB)
stoch_divergence   : +1(bullish) / -1(bearish) / 0
stoch_cross_in_zone: 1 if cross occurred in OB/OS zone
```

---

## 7. EDGE CASES

- **Strong trends**: Stochastic stays OB/OS for extended periods — do NOT counter-trend trade
- **Low range days**: If Highest High = Lowest Low (no range), %K undefined → output quality 0
- **VN ceiling/floor**: Artificial extremes — reduce quality by 1
- **Combine with ADX**: If ADX > 30 (strong trend), stochastic OB/OS less reliable for reversal

---

*Stochastic excels at identifying turns in trading ranges.*
*In strong trends, use for timing entries, not counter-trend trades.*
