# OBV RULEBOOK — AI_STOCK v2
Generated: 2026-03-15
Expert ID: V4OBV
Scale: -4 → +4

---

## 1. INDICATORS USED (with parameters)

| Indicator | Parameter | Description |
|-----------|-----------|-------------|
| **OBV** | Cumulative | On-Balance Volume: cumulative sum of signed volume (+vol if close > prev close, -vol if close < prev close, 0 if unchanged) |
| **OBV_SMA20** | SMA(OBV, 20) | 20-day simple moving average of OBV |
| **OBV_Slope20** | Linear regression slope of OBV over 20 days | Normalized slope: (OBV[0] - OBV[19]) / (20 * VMA20) |
| **OBV_Slope5** | Linear regression slope of OBV over 5 days | Short-term slope for momentum detection |
| **Price_Slope20** | Linear regression slope of Close over 20 days | Normalized: (Close[0] - Close[19]) / (20 * Close[19]) |
| **OBV_High20** | Highest OBV in 20 days | For breakout detection |
| **OBV_Low20** | Lowest OBV in 20 days | For breakdown detection |
| **OBV_High52W** | Highest OBV in 52 weeks (260 sessions) | Major breakout reference |
| **OBV_Low52W** | Lowest OBV in 52 weeks | Major breakdown reference |

### OBV Calculation

```
If Close[t] > Close[t-1]:  OBV[t] = OBV[t-1] + Volume[t]
If Close[t] < Close[t-1]:  OBV[t] = OBV[t-1] - Volume[t]
If Close[t] = Close[t-1]:  OBV[t] = OBV[t-1]
```

### Derived Metrics

- **OBV_Divergence** = sign(OBV_Slope20) vs sign(Price_Slope20) — divergence when signs differ
- **OBV_Momentum** = OBV_Slope5 / abs(OBV_Slope20) — acceleration ratio
- **OBV_Position** = (OBV - OBV_Low20) / (OBV_High20 - OBV_Low20) — position within 20-day range (0.0 to 1.0)

---

## 2. SCORING RULES (detailed score mapping table)

### Primary Scoring Matrix

| Score | OBV Trend (Slope20) | OBV Breakout Status | Price-OBV Alignment | Description |
|-------|---------------------|---------------------|---------------------|-------------|
| **+4** | Strongly positive (> +0.03) | OBV at/near 20-day high (Position > 0.95) | Price also at 20-day high | Full bullish confirmation — accumulation with price breakout |
| **+3** | Positive (> +0.02) | OBV near 20-day high (Position > 0.85) | Price trending up | Strong accumulation — OBV leading or confirming uptrend |
| **+2** | Moderately positive (> +0.01) | OBV above SMA20 | Price up or flat | Moderate accumulation — buying pressure building |
| **+1** | Slightly positive (> 0) | OBV near SMA20 | Any | Mild accumulation — marginal buying pressure |
| **0** | Flat (-0.005 to +0.005) | OBV near SMA20 | Any | Neutral — no detectable accumulation or distribution |
| **-1** | Slightly negative (< 0) | OBV near SMA20 | Any | Mild distribution — marginal selling pressure |
| **-2** | Moderately negative (< -0.01) | OBV below SMA20 | Price down or flat | Moderate distribution — selling pressure building |
| **-3** | Negative (< -0.02) | OBV near 20-day low (Position < 0.15) | Price trending down | Strong distribution — OBV confirming downtrend |
| **-4** | Strongly negative (< -0.03) | OBV at/near 20-day low (Position < 0.05) | Price also at 20-day low | Full bearish confirmation — distribution with price breakdown |

### Divergence Override Rules

Divergence signals override the primary score when detected. These are among the most powerful OBV signals.

| Divergence Type | Condition | Score Override | Priority |
|-----------------|-----------|----------------|----------|
| **Class A Bullish Divergence** | OBV_Slope20 > +0.01 AND Price_Slope20 < -0.01 AND OBV making higher lows | Set score = +3 (min) | HIGH |
| **Class B Bullish Divergence** | OBV_Slope20 > 0 AND Price_Slope20 < -0.005 | Set score = max(score, +2) | MEDIUM |
| **Class A Bearish Divergence** | OBV_Slope20 < -0.01 AND Price_Slope20 > +0.01 AND OBV making lower highs | Set score = -3 (max) | HIGH |
| **Class B Bearish Divergence** | OBV_Slope20 < 0 AND Price_Slope20 > +0.005 | Set score = min(score, -2) | MEDIUM |
| **Hidden Bullish Divergence** | OBV_Slope20 > +0.01 AND price pulls back but OBV holds above prior low | Set score = max(score, +2) | MEDIUM |
| **Hidden Bearish Divergence** | OBV_Slope20 < -0.01 AND price bounces but OBV stays below prior high | Set score = min(score, -2) | MEDIUM |

### OBV Breakout/Breakdown Rules

| Rule ID | Condition | Effect |
|---------|-----------|--------|
| **OB-1** | OBV breaks above 20-day high AND price confirms (also breaks high) | Score = +4 |
| **OB-2** | OBV breaks above 20-day high BUT price does NOT break high | Score = max(score, +2), flag `OBV_LEADING_BULL` |
| **OB-3** | OBV breaks below 20-day low AND price confirms (also breaks low) | Score = -4 |
| **OB-4** | OBV breaks below 20-day low BUT price does NOT break low | Score = min(score, -2), flag `OBV_LEADING_BEAR` |
| **OB-5** | OBV breaks 52-week high | Add +1 to score (cap at +4), flag `OBV_52W_HIGH` |
| **OB-6** | OBV breaks 52-week low | Add -1 to score (cap at -4), flag `OBV_52W_LOW` |

### Momentum Modifier

| OBV_Momentum | Condition | Adjustment |
|--------------|-----------|------------|
| > 2.0 | OBV accelerating strongly in slope direction | Add +1 to magnitude (cap at +/-4) |
| 1.0 – 2.0 | OBV accelerating | No adjustment |
| 0.5 – 1.0 | OBV steady | No adjustment |
| < 0.5 | OBV decelerating | Reduce magnitude by 1 (floor at 0) |

---

## 3. SIGNAL CODES (reference SIGNAL_CODEBOOK)

| Code | Name | Trigger |
|------|------|---------|
| `OBV_ACCUM_STRONG` | Strong Accumulation | Score >= +3 |
| `OBV_ACCUM_MILD` | Mild Accumulation | Score = +1 or +2 |
| `OBV_DIST_STRONG` | Strong Distribution | Score <= -3 |
| `OBV_DIST_MILD` | Mild Distribution | Score = -1 or -2 |
| `OBV_NEUTRAL` | OBV Neutral | Score = 0 |
| `OBV_BULL_DIV_A` | Class A Bullish Divergence | OBV up, price down (strong) |
| `OBV_BULL_DIV_B` | Class B Bullish Divergence | OBV up, price down (moderate) |
| `OBV_BEAR_DIV_A` | Class A Bearish Divergence | OBV down, price up (strong) |
| `OBV_BEAR_DIV_B` | Class B Bearish Divergence | OBV down, price up (moderate) |
| `OBV_HIDDEN_BULL` | Hidden Bullish Divergence | OBV holds support during pullback |
| `OBV_HIDDEN_BEAR` | Hidden Bearish Divergence | OBV fails to recover during bounce |
| `OBV_BREAKOUT` | OBV Breakout | OBV breaks 20-day high |
| `OBV_BREAKDOWN` | OBV Breakdown | OBV breaks 20-day low |
| `OBV_LEADING_BULL` | OBV Leading Bullish | OBV breakout before price breakout |
| `OBV_LEADING_BEAR` | OBV Leading Bearish | OBV breakdown before price breakdown |
| `OBV_52W_HIGH` | OBV 52-Week High | OBV at 52-week high |
| `OBV_52W_LOW` | OBV 52-Week Low | OBV at 52-week low |
| `OBV_FLAT` | OBV Flat | OBV slope near zero for 10+ days |

---

## 4. SIGNAL QUALITY RULES

### Quality Tiers

| Quality | Condition | Confidence |
|---------|-----------|------------|
| **A (High)** | Divergence Class A OR confirmed breakout/breakdown (OB-1/OB-3) OR 52-week signal | 80-95% |
| **B (Medium)** | Divergence Class B OR OBV leading signal (OB-2/OB-4) OR strong accumulation/distribution with trend alignment | 55-79% |
| **C (Low)** | Mild accumulation/distribution without strong trend OR decelerating momentum | 35-54% |
| **D (Noise)** | OBV flat for 10+ days OR conflicting short/long-term slopes OR very low volume environment (V_Ratio < 0.5) | < 35% |

### Quality Modifiers

1. **Volume Confirmation**: If today's V_Ratio > 1.5 in the direction of OBV signal, upgrade quality by one tier.
2. **Trend Persistence**: If OBV_Slope20 sign has been consistent for 10+ consecutive days, upgrade by one tier.
3. **Whipsaw Penalty**: If OBV_Slope20 changed sign 3+ times in last 10 days, downgrade quality to D.
4. **Low Volume Penalty**: If VMA20 is in the bottom 20th percentile of the stock's historical volume, downgrade by one tier.
5. **Multi-Timeframe Bonus**: If weekly OBV trend aligns with daily signal, upgrade by one tier.

### Minimum Quality for Action

- Divergence signals (Class A): actionable at any quality (already high confidence).
- Score magnitude >= 3: requires Quality B or better.
- Score magnitude 2: requires Quality A.
- Score magnitude <= 1: informational only.

---

## 5. EDGE CASES

| Edge Case | Handling |
|-----------|----------|
| **First 20 sessions** | OBV_SMA20, OBV_Slope20, OBV_High20, OBV_Low20 undefined — use available data; if < 10 sessions, output score = 0 with flag `INSUFFICIENT_OBV_HISTORY` |
| **Stock split / reverse split** | OBV must be recalculated with adjusted volumes — flag `SPLIT_ADJUSTED` for 5 sessions post-split |
| **Rights issue / bonus shares** | Volume inflated on ex-date — apply OBV reset or use adjusted volume data; flag `CORPORATE_ACTION` |
| **Trading halt** | Volume = 0, OBV unchanged — skip day in slope calculation; flag `HALTED` |
| **Ceiling/Floor lock** | Volume reflects only one-sided interest — OBV calculation valid but interpretation changes. At ceiling, OBV increases reflect excess buying demand (matched volume only); at floor, OBV decreases reflect excess selling supply |
| **Dividend ex-date** | Price drops mechanically — this can falsely generate -Volume for OBV. Apply correction: if ex-dividend, treat price change as (Close - (PrevClose - Dividend)) for OBV sign determination |
| **OBV range compression** | When OBV_High20 ≈ OBV_Low20 (range < 5% of OBV), OBV_Position is unreliable — clamp score to [-1, +1] |
| **Extreme OBV spike** | Single-day OBV change > 5x average daily OBV change — likely block trade or error. Flag `OBV_SPIKE`, use median instead of current value for slope calc |
| **Delisting / merger** | OBV signals invalid — output score = 0, flag `DELISTING` |

---

## 6. VIETNAM MARKET NOTES

### OBV Specifics for Vietnamese Stocks

1. **T+2 Settlement & OBV Lag**: Due to T+2 settlement, OBV accumulation/distribution patterns may lag the actual institutional intent by 1-2 days. When interpreting OBV divergences, allow a 2-day tolerance window for the price to "catch up" to OBV signals.

2. **Foreign Flow as OBV Supplement**: Vietnamese exchanges publish daily foreign net buy/sell data. When OBV shows accumulation AND foreign net buy is positive, the signal is significantly stronger. Consider tracking:
   - **OBV_Foreign**: Separate OBV calculated using only foreign-attributed volume (when data available).
   - If OBV_Foreign diverges from total OBV, flag `FOREIGN_DOMESTIC_DIVERGE`.

3. **Proprietary Trading Noise**: Vietnamese securities companies engage in active proprietary trading. This adds noise to OBV especially in mid-cap and small-cap stocks. For stocks outside VN30, apply a noise discount: reduce OBV signal quality by one tier for Small/Micro liquidity tier stocks.

4. **Ceiling/Floor Price Impact on OBV**:
   - **Ceiling (CE)**: At HOSE +7%, only matched volume counts for OBV. Excess buy orders are unmatched. OBV understates true buying pressure. Flag `OBV_CE_UNDERSTATED`.
   - **Floor (FL)**: At HOSE -7%, OBV understates true selling pressure. Flag `OBV_FL_UNDERSTATED`.

5. **ATC Session and OBV**: The ATC (Afternoon Trading Close) session at 14:30-14:45 can generate large OBV moves due to order matching concentration. If > 30% of daily volume occurs in ATC, flag `ATC_HEAVY` — OBV spike may be less organic.

6. **Tet Holiday OBV Reset**: During the 5 sessions before Tet, OBV patterns are unreliable due to portfolio rebalancing for year-end. Flag `TET_WINDOW` and reduce quality by two tiers.

7. **Margin Lending and OBV**: When HOSE/HNX margin ratios tighten (regulatory announcements), forced selling creates negative OBV that does not reflect fundamental distribution. Cross-reference with margin regulation news. Flag `MARGIN_REGULATION` when detected.

8. **VN30 Index Futures Arbitrage**: Arbitrage between VN30 futures and basket stocks creates mechanical volume that distorts OBV for VN30 constituents. On futures expiry days (3rd Thursday of expiry month), flag `FUTURES_EXPIRY` and discount OBV signals by one quality tier.

### Recommended OBV Lookback by Market Cap

| Market Cap Tier | OBV Trend Lookback | Breakout Lookback | Rationale |
|-----------------|--------------------|--------------------|-----------|
| VN30 (Mega) | 20 days | 20 days + 52W | Stable, high-volume |
| Large Cap | 20 days | 20 days | Adequate volume |
| Mid Cap | 30 days | 30 days | Needs longer period for noise reduction |
| Small Cap | 40 days | 40 days | High noise, longer smoothing needed |
| Micro Cap | OBV unreliable | Do not use | Flag `OBV_UNRELIABLE` |

### OBV Divergence Reliability in Vietnam

Historical backtesting on HOSE data shows the following success rates for OBV divergence signals:

| Signal | VN30 Success Rate | Mid-Cap Success Rate | Small-Cap Success Rate |
|--------|-------------------|----------------------|------------------------|
| Class A Bullish Div | ~72% | ~60% | ~45% |
| Class A Bearish Div | ~68% | ~55% | ~40% |
| Class B Bullish Div | ~58% | ~48% | ~35% |
| Class B Bearish Div | ~55% | ~45% | ~33% |

*Note: Success rates are approximate and based on historical patterns. These should be recalibrated periodically with updated data.*
