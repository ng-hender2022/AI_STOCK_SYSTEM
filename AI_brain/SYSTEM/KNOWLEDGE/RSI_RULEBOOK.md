# RSI RULEBOOK — RSI Expert

Expert ID: V4RSI
Scale: 0 to 100 (raw RSI value as primary_score)
Generated: 2026-03-16
Status: ACTIVE

Primary Sources:
- J. Welles Wilder — New Concepts in Technical Trading Systems (1978)
- John J. Murphy — Technical Analysis of the Financial Markets (1999), Chapter 10

---

## 1. FORMULA

```
RS = avg_gain(14) / avg_loss(14)
RSI = 100 - (100 / (1 + RS))
```

Period: 14 (Wilder standard)

First calculation: simple average of gains/losses over 14 periods.
Subsequent: smoothed average = (prev_avg * 13 + current) / 14.

---

## 2. PRIMARY SCORE

```
primary_score = RSI value (0 to 100)
```

This preserves the full RSI information for R Layer to consume.

---

## 3. SIGNAL LOGIC

### 3.1 Overbought / Oversold

| Condition | Label |
|---|---|
| RSI > 70 | OVERBOUGHT |
| RSI > 80 | EXTREME_OVERBOUGHT |
| RSI < 30 | OVERSOLD |
| RSI < 20 | EXTREME_OVERSOLD |
| 30 <= RSI <= 70 | NEUTRAL |

### 3.2 Regime-Adjusted Levels (Murphy Ch.10)

| Market Regime | Overbought | Oversold |
|---|---|---|
| Bull market | 80 | 40 |
| Bear market | 60 | 20 |
| Neutral | 70 | 30 |

Regime from V4REG determines which levels to use.

### 3.3 Centerline Cross

```
RSI crossing above 50 → bullish momentum confirmation
RSI crossing below 50 → bearish momentum confirmation
```

### 3.4 Divergence

```
Bullish divergence: price makes lower low, RSI makes higher low
Bearish divergence: price makes higher high, RSI makes lower high
```
Lookback: 10-30 bars. Most reliable near OB/OS levels.

### 3.5 Failure Swing (Wilder)

```
Bullish failure swing:
    RSI falls below 30
    RSI bounces above X
    RSI pulls back but stays above 30
    RSI breaks above X
    → Buy signal

Bearish failure swing:
    RSI rises above 70
    RSI falls below Y
    RSI rallies but stays below 70
    RSI breaks below Y
    → Sell signal
```

Failure swings are **independent of price action** — pure RSI pattern.

---

## 4. SCORING FOR SIGNAL_QUALITY (0 to 4)

| Quality | Condition |
|---|---|
| 4 | Divergence + failure swing + extreme OB/OS |
| 3 | Divergence at OB/OS level |
| 2 | Extreme OB/OS (< 20 or > 80) |
| 1 | Regular OB/OS (< 30 or > 70) |
| 0 | RSI in neutral zone (30-70), no divergence |

---

## 5. SIGNAL CODES

| Code | Meaning |
|---|---|
| V4RSI_BULL_EXTREME_OS | RSI < 20, extreme oversold |
| V4RSI_BEAR_EXTREME_OB | RSI > 80, extreme overbought |
| V4RSI_BULL_REVERSAL | RSI bouncing from oversold zone |
| V4RSI_BEAR_REVERSAL | RSI dropping from overbought zone |
| V4RSI_BULL_DIV | Bullish divergence |
| V4RSI_BEAR_DIV | Bearish divergence |
| V4RSI_BULL_FAILURE_SWING | Bullish failure swing pattern |
| V4RSI_BEAR_FAILURE_SWING | Bearish failure swing pattern |
| V4RSI_BULL_CENTER_CROSS | RSI crossed above 50 |
| V4RSI_BEAR_CENTER_CROSS | RSI crossed below 50 |
| V4RSI_NEUT_NEUTRAL | RSI in neutral zone |

---

## 6. FEATURES FOR R LAYER

```
rsi_value           : RSI(14) raw value (0-100)
rsi_slope           : (RSI[t] - RSI[t-3]) / 100
rsi_ma              : SMA(RSI, 10)
rsi_above_50        : 1 / -1
rsi_zone            : -2(extreme OS) / -1(OS) / 0(neutral) / +1(OB) / +2(extreme OB)
rsi_divergence      : +1(bullish) / -1(bearish) / 0
rsi_failure_swing   : +1(bullish) / -1(bearish) / 0
```

---

## 7. EDGE CASES

- **Strong trends**: RSI can stay OB (>70) for weeks in strong bull — do NOT sell just because OB
- **Bear market**: RSI rarely exceeds 60 — adjust levels per regime
- **VN ceiling/floor**: Ceiling days push RSI toward extreme — less meaningful
- **Low volume**: RSI on low-volume stocks can be jumpy — combine with V4LIQ quality reduction

---

*RSI measures momentum speed and change.*
*Divergence and failure swings are the highest-quality RSI signals.*
