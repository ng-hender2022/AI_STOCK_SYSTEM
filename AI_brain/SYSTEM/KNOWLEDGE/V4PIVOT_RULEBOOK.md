# V4PIVOT RULEBOOK — Pivot Point Expert

Expert ID: V4PIVOT
Scale: -4 to +4
Generated: 2026-03-16
Status: ACTIVE

Primary Sources:
- John L. Person — A Complete Guide to Technical Trading Tactics (2004)
- John L. Person — Mastering the Stock Market (2012)

---

## 1. CORE FORMULAS

### Standard Pivot Point

```
P  = (H + L + C) / 3

R1 = (2 * P) - L
R2 = P + (H - L)
R3 = H + 2 * (P - L)

S1 = (2 * P) - H
S2 = P - (H - L)
S3 = L - 2 * (H - P)
```

### Midpoint Levels

```
M_R1R2 = (R1 + R2) / 2
M_S1S2 = (S1 + S2) / 2
M_PR1  = (P + R1) / 2
M_PS1  = (P + S1) / 2
```

---

## 2. THREE TIMEFRAMES

| Timeframe | H, L, C source | Update frequency |
|---|---|---|
| Daily | Previous day's HLC | Every trading day |
| Weekly | Previous week's HLC | Every Monday |
| Monthly | Previous month's HLC | First day of month |

### Computation Rules

- **Daily pivot**: Use yesterday's H, L, C (T-1). Strictly no T data.
- **Weekly pivot**: Use last completed week's H, L, C. If mid-week, use prior week.
- **Monthly pivot**: Use last completed month's H, L, C.

---

## 3. MARKET CONDITION

```
BULLISH  : close > P  (price above pivot = buyers in control)
BEARISH  : close < P  (price below pivot = sellers in control)
NEUTRAL  : close ≈ P  (within 0.2% of pivot)
```

---

## 4. SCORING RULES (-4 to +4)

### 4.1 Position Score (range -2 to +2)

| Condition | Score |
|---|---|
| Close > R2 | +2 |
| Close between R1 and R2 | +1.5 |
| Close between P and R1 | +1 |
| Close at P (neutral zone) | 0 |
| Close between S1 and P | -1 |
| Close between S2 and S1 | -1.5 |
| Close < S2 | -2 |

### 4.2 Confluence Score (range -1 to +1)

Count how many timeframes agree on direction:

| Confluence | Score |
|---|---|
| Daily + Weekly + Monthly all bullish | +1 |
| 2 of 3 bullish | +0.5 |
| Mixed / no agreement | 0 |
| 2 of 3 bearish | -0.5 |
| Daily + Weekly + Monthly all bearish | -1 |

### 4.3 Timeframe Alignment Score (range -1 to +1)

```
+1 : Daily P rising AND Weekly P rising AND Monthly P rising
-1 : Daily P falling AND Weekly P falling AND Monthly P falling
 0 : Mixed
```

(P rising = today's P > yesterday's P)

### 4.4 Total Score

```
score = position_score + confluence_score + alignment_score
score = clamp(score, -4, +4)
```

---

## 5. SIGNAL QUALITY

| Quality | Condition |
|---|---|
| 4 (VERY_STRONG) | 3-timeframe confluence + close beyond R2/S2 |
| 3 (STRONG) | 2-timeframe confluence + close beyond R1/S1 |
| 2 (MODERATE) | Single timeframe signal + clear direction |
| 1 (WEAK) | Close near pivot, no confluence |
| 0 (NONE) | Insufficient data |

---

## 6. KEY RULES FROM PERSON

### First Test Rule

- **First test of S1 or R1 is the most reliable** — highest probability of reaction
- Subsequent tests weaken the level
- After 3+ tests, expect breakout

### Level Interaction

- Close above R1 → R1 becomes support
- Close below S1 → S1 becomes resistance
- Failed test (close returns) → reversal signal

### Volume at Pivot Levels

- High volume at pivot level = significant reaction
- Low volume at pivot level = likely to break through

---

## 7. SIGNAL CODES

| Code | Meaning |
|---|---|
| V4PIVOT_BULL_ABOVE_R1 | Close above R1, bullish |
| V4PIVOT_BULL_ABOVE_R2 | Close above R2, strong bullish |
| V4PIVOT_BEAR_BELOW_S1 | Close below S1, bearish |
| V4PIVOT_BEAR_BELOW_S2 | Close below S2, strong bearish |
| V4PIVOT_BULL_CONFLUENCE | Multi-timeframe bullish confluence |
| V4PIVOT_BEAR_CONFLUENCE | Multi-timeframe bearish confluence |
| V4PIVOT_NEUT_AT_PIVOT | Close near pivot |
| V4PIVOT_BULL_BOUNCE_S1 | Bounce from S1 (first test) |
| V4PIVOT_BEAR_REJECT_R1 | Rejection from R1 (first test) |

---

## 8. EDGE CASES

- **Holiday weeks**: Weekly pivot uses last full trading week
- **Short months**: Monthly pivot still uses actual HLC
- **IPO stocks**: Need minimum 1 month of data for monthly pivots
- **Vietnam ceiling/floor**: If close hits ceiling (C=H), pivot levels shift up next day
- **Low liquidity**: Pivot levels less reliable for thinly traded stocks (combine with V4LIQ)

---

## 9. DATA LEAKAGE

- Daily pivot: computed from T-1 HLC only
- Weekly pivot: computed from last completed week only
- Monthly pivot: computed from last completed month only
- NEVER use any data from current period

---

*Pivot analysis gives objective, mathematically derived support/resistance levels.*
*Multi-timeframe confluence is the strongest signal.*
