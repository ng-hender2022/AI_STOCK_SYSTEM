# BOLLINGER BANDS RULEBOOK — AI_STOCK v2
Generated: 2026-03-15
Expert ID: V4BB
Scale: -4 → +4

---

## 1. INDICATORS USED (with parameters)

| Indicator | Parameter | Description |
|-----------|-----------|-------------|
| **BB_Mid** | SMA(Close, 20) | Middle Bollinger Band — 20-period simple moving average |
| **BB_Upper** | BB_Mid + 2 * StdDev(Close, 20) | Upper Bollinger Band — 2 standard deviations above |
| **BB_Lower** | BB_Mid - 2 * StdDev(Close, 20) | Lower Bollinger Band — 2 standard deviations below |
| **BB_Width** | (BB_Upper - BB_Lower) / BB_Mid * 100 | Bandwidth as percentage of middle band |
| **BB_Width_SMA20** | SMA(BB_Width, 20) | 20-day average of bandwidth — baseline |
| **BB_Width_Ratio** | BB_Width / BB_Width_SMA20 | Current bandwidth relative to average |
| **%B** | (Close - BB_Lower) / (BB_Upper - BB_Lower) | Price position within bands (0.0 = lower, 1.0 = upper) |
| **BB_Slope** | (BB_Mid[0] - BB_Mid[4]) / BB_Mid[4] * 100 | 5-day slope of middle band — trend direction |
| **BB_Width_Pctile** | Percentile rank of BB_Width in 252-day history | Long-term squeeze/expansion context |

### Standard Deviation Calculation

```
StdDev(Close, 20) = sqrt(sum((Close[i] - SMA(Close,20))^2 for i=0..19) / 20)
```

### Derived Metrics

- **Band_Position**: Where price is relative to bands: "ABOVE_UPPER" (%B > 1.0), "UPPER_ZONE" (0.8 < %B <= 1.0), "MIDDLE_ZONE" (0.2 <= %B <= 0.8), "LOWER_ZONE" (0.0 <= %B < 0.2), "BELOW_LOWER" (%B < 0.0)
- **Squeeze_State**: BB_Width_Pctile < 10th = "TIGHT_SQUEEZE", < 20th = "SQUEEZE", > 80th = "WIDE", > 90th = "VERY_WIDE"
- **BB_Trend**: sign(BB_Slope) — upward, downward, or flat middle band

---

## 2. SCORING RULES (detailed score mapping table)

### Primary Scoring Matrix

| Score | %B Range | BB_Width State | BB_Slope | Description |
|-------|----------|---------------|----------|-------------|
| **+4** | > 1.05 | Expanding (Ratio > 1.30) from squeeze | Up (> +0.3%) | Squeeze breakout upward — strong bullish momentum, band walk initiating |
| **+3** | 0.90 – 1.05 | Expanding (Ratio > 1.15) | Up (> +0.2%) | Price at/near upper band with expanding volatility — bullish continuation |
| **+2** | 0.75 – 0.90 | Any | Up (> +0.1%) | Price in upper zone, uptrend intact |
| **+1** | 0.55 – 0.75 | Any | Up (> 0%) | Price above middle band, mild bullish bias |
| **0** | 0.40 – 0.60 | Any (especially contracting) | Flat (-0.1% to +0.1%) | Price near middle band — neutral, no directional signal |
| **-1** | 0.25 – 0.45 | Any | Down (< 0%) | Price below middle band, mild bearish bias |
| **-2** | 0.10 – 0.25 | Any | Down (< -0.1%) | Price in lower zone, downtrend intact |
| **-3** | -0.05 – 0.10 | Expanding (Ratio > 1.15) | Down (< -0.2%) | Price at/near lower band with expanding volatility — bearish continuation |
| **-4** | < -0.05 | Expanding (Ratio > 1.30) from squeeze | Down (< -0.3%) | Squeeze breakout downward — strong bearish momentum, band walk initiating |

### Bollinger Squeeze Rules

The squeeze (low bandwidth) is one of the most important Bollinger signals — it precedes large moves.

| Squeeze Stage | BB_Width_Pctile | Duration | Handling |
|---------------|----------------|----------|----------|
| **Pre-Squeeze** | 20th – 10th | Early | Flag `SQUEEZE_FORMING`, score tends toward 0 |
| **Tight Squeeze** | < 10th | Persistent | Flag `SQUEEZE_TIGHT`, score = 0, mark as high-priority watchlist |
| **Squeeze Release Up** | Was < 10th, now %B > 0.85 AND BB_Width_Ratio > 1.20 | Breakout | Score = +4, flag `SQUEEZE_BREAK_UP` |
| **Squeeze Release Down** | Was < 10th, now %B < 0.15 AND BB_Width_Ratio > 1.20 | Breakout | Score = -4, flag `SQUEEZE_BREAK_DOWN` |
| **False Squeeze Break** | Squeeze release but reverses within 2 sessions | Failed | Revert score to 0, flag `SQUEEZE_FAKEOUT` |

### Bollinger Bounce Rules

| Pattern | Condition | Score |
|---------|-----------|-------|
| **Lower Band Bounce** | %B touches/goes below 0.0, then closes above 0.10 within 2 sessions | Score = max(score, +1), flag `BB_BOUNCE_LOWER` |
| **Upper Band Rejection** | %B touches/goes above 1.0, then closes below 0.90 within 2 sessions | Score = min(score, -1), flag `BB_BOUNCE_UPPER` |
| **Double Bottom at Lower Band** | %B < 0.05 twice within 10 sessions with higher %B low on second touch | Score = max(score, +2), flag `BB_DOUBLE_BOTTOM` |
| **Double Top at Upper Band** | %B > 0.95 twice within 10 sessions with lower %B high on second touch | Score = min(score, -2), flag `BB_DOUBLE_TOP` |

### Bollinger Band Walk Rules

| Pattern | Condition | Score |
|---------|-----------|-------|
| **Upper Band Walk** | %B > 0.80 for 5+ consecutive sessions AND BB_Width expanding | Score = +3 or +4, flag `BB_WALK_UPPER` |
| **Lower Band Walk** | %B < 0.20 for 5+ consecutive sessions AND BB_Width expanding | Score = -3 or -4, flag `BB_WALK_LOWER` |
| **Walk Exhaustion (Upper)** | Upper band walk for 8+ sessions AND BB_Width starts contracting | Reduce score by 1, flag `BB_WALK_EXHAUSTION` |
| **Walk Exhaustion (Lower)** | Lower band walk for 8+ sessions AND BB_Width starts contracting | Increase score by 1, flag `BB_WALK_EXHAUSTION` |

### W-Bottom and M-Top Patterns (Bollinger-specific)

| Pattern | Condition | Score |
|---------|-----------|-------|
| **W-Bottom** | First low at %B < 0.0, rally to %B > 0.50, second low at %B > 0.0 (higher %B than first) | Score = +3, flag `BB_W_BOTTOM` |
| **M-Top** | First high at %B > 1.0, decline to %B < 0.50, second high at %B < 1.0 (lower %B than first) | Score = -3, flag `BB_M_TOP` |

---

## 3. SIGNAL CODES (reference SIGNAL_CODEBOOK)

| Code | Name | Trigger |
|------|------|---------|
| `BB_SQUEEZE_BREAK_UP` | Squeeze Breakout Up | Score = +4, squeeze release upward |
| `BB_SQUEEZE_BREAK_DOWN` | Squeeze Breakout Down | Score = -4, squeeze release downward |
| `BB_SQUEEZE_TIGHT` | Tight Squeeze | BB_Width_Pctile < 10th |
| `BB_SQUEEZE_FORMING` | Squeeze Forming | BB_Width_Pctile 10th-20th |
| `BB_SQUEEZE_FAKEOUT` | Squeeze Fakeout | Squeeze release reverses within 2 sessions |
| `BB_WALK_UPPER` | Upper Band Walk | %B > 0.80 for 5+ days, expanding width |
| `BB_WALK_LOWER` | Lower Band Walk | %B < 0.20 for 5+ days, expanding width |
| `BB_WALK_EXHAUSTION` | Band Walk Exhaustion | Walk 8+ days, width contracting |
| `BB_BOUNCE_LOWER` | Lower Band Bounce | %B touches 0.0 then recovers |
| `BB_BOUNCE_UPPER` | Upper Band Rejection | %B touches 1.0 then retreats |
| `BB_W_BOTTOM` | W-Bottom Pattern | Classic Bollinger W-bottom |
| `BB_M_TOP` | M-Top Pattern | Classic Bollinger M-top |
| `BB_DOUBLE_BOTTOM` | Double Bottom at Band | Two touches of lower band |
| `BB_DOUBLE_TOP` | Double Top at Band | Two touches of upper band |
| `BB_ABOVE_UPPER` | Price Above Upper Band | %B > 1.0 |
| `BB_BELOW_LOWER` | Price Below Lower Band | %B < 0.0 |
| `BB_MIDDLE_CROSS_UP` | Middle Band Cross Up | %B crosses above 0.50 from below |
| `BB_MIDDLE_CROSS_DOWN` | Middle Band Cross Down | %B crosses below 0.50 from above |
| `BB_WIDTH_EXPAND` | Bandwidth Expanding | BB_Width_Ratio > 1.30 |
| `BB_WIDTH_CONTRACT` | Bandwidth Contracting | BB_Width_Ratio < 0.70 |

---

## 4. SIGNAL QUALITY RULES

### Quality Tiers

| Quality | Condition | Confidence |
|---------|-----------|------------|
| **A (High)** | Squeeze breakout (confirmed by volume V_Ratio > 1.5) OR W-Bottom/M-Top confirmed OR Band walk with expanding width | 80-95% |
| **B (Medium)** | Squeeze breakout (without volume confirmation) OR price at band extremes (%B < 0.05 or > 0.95) with expanding width | 55-79% |
| **C (Low)** | Price in middle zone (0.30 < %B < 0.70) OR bandwidth stable (0.85 < Ratio < 1.15) OR conflicting signals | 35-54% |
| **D (Noise)** | Squeeze fakeout detected OR %B oscillating rapidly (crosses 0.50 three or more times in 5 sessions) OR insufficient history | < 35% |

### Quality Modifiers

1. **Volume Confirmation Bonus**: If squeeze breakout occurs with V_Ratio > 2.0, upgrade quality by one tier.
2. **Multi-Band Confirmation**: If price breaks above/below BB AND also breaks a key support/resistance level, upgrade by one tier.
3. **Trend Alignment Bonus**: If BB_Slope direction matches the breakout direction, upgrade by one tier.
4. **Fakeout Penalty**: If the stock has produced 2+ squeeze fakeouts in the last 30 days, downgrade all squeeze signals by one tier.
5. **Bandwidth Persistence**: If squeeze (BB_Width_Pctile < 20th) has lasted 10+ sessions, the eventual breakout quality is upgraded by one tier (longer compression = stronger release).

### Minimum Quality for Action

- Squeeze breakout (Score +/-4): actionable at Quality B or better.
- Band walk (Score +/-3): actionable at Quality B or better.
- Score magnitude 2: requires Quality A.
- Score magnitude <= 1: informational only.

---

## 5. EDGE CASES

| Edge Case | Handling |
|-----------|----------|
| **First 20 sessions** | BB requires 20 periods for SMA and StdDev — output score = 0 with flag `INSUFFICIENT_BB_HISTORY` |
| **Zero standard deviation** | If StdDev = 0 (price unchanged for 20 sessions), BB_Upper = BB_Lower = BB_Mid — set score = 0, flag `BB_ZERO_STDDEV`, squeeze is at maximum |
| **Price gap through band** | If price gaps from inside bands to outside (open already beyond band), %B calculation is valid but the signal is gap-driven — flag `BB_GAP_BREAKOUT` |
| **Ceiling/Floor price lock** | Price band limits compress the standard deviation artificially. If stock hits ceiling/floor 3+ times in 20-day window, BB parameters are distorted — flag `BB_BAND_LIMITED`, reduce quality by one tier |
| **Stock split** | Price level changes — BB recalculates correctly with adjusted prices, but first 20 sessions post-split will mix adjusted and actual data. Use fully adjusted prices. Flag `SPLIT_ADJUSTED` |
| **Extreme %B values** | %B can theoretically be any value (negative or > 1.0). Values beyond [-0.5, 1.5] suggest extreme conditions or data issues — cap display at [-0.5, 1.5], flag `BB_EXTREME_PCT_B` |
| **Low-price stocks** | For stocks < 5,000 VND, tick size effects can make StdDev and band calculations noisy — flag `BB_LOW_PRICE_NOISE` |
| **Dividend ex-date** | Price drop on ex-date can push %B sharply lower — not a true sell signal. Flag `EX_DIVIDEND_BB` and ignore %B signal for 1 session |
| **Very high StdDev** | In crash scenarios, BB_Width can become extremely wide (> 3x average), making bounce signals unreliable — flag `BB_EXTREME_WIDTH` |

---

## 6. VIETNAM MARKET NOTES

### BB Parameters Optimized for Vietnam

Standard BB(20,2) works well for Vietnamese stocks, with these adaptations:

1. **Band Limit and StdDev Compression**: Vietnam's daily price limits (HOSE +/-7%) create a natural ceiling on standard deviation. The maximum possible StdDev for a 20-day period is constrained by these limits. This means:
   - BB_Width has a theoretical maximum that is lower than in unlimited markets.
   - Squeeze thresholds should be calibrated to Vietnamese BB_Width distributions, not global ones.
   - Recommended: Use Vietnam-specific BB_Width_Pctile (calculated from Vietnamese stock data), not global percentiles.

2. **Typical BB_Width Ranges for Vietnamese Stocks**:

| Category | Squeeze (< 20th pctile) | Normal | Wide (> 80th pctile) |
|----------|-------------------------|--------|----------------------|
| **VN30** | BB_Width < 4.0% | 4.0% – 8.0% | > 8.0% |
| **Mid Cap** | BB_Width < 5.0% | 5.0% – 12.0% | > 12.0% |
| **Small Cap** | BB_Width < 6.0% | 6.0% – 16.0% | > 16.0% |

3. **Ceiling/Floor and Bollinger Band Walk**:
   - When a stock walks the upper Bollinger Band AND hits ceiling price, this is an extremely strong bullish signal in Vietnam — it means demand exceeds supply at maximum allowed price.
   - Signal: `BB_WALK_UPPER` + `PRICE_LOCKED_CE` = upgrade to score +4, Quality A.
   - Conversely, lower band walk + floor price = score -4, Quality A.

4. **ATC Session and %B Jumps**: The ATC session (14:30-14:45 on HOSE) can cause sudden %B changes due to the closing price auction. If %B changes by more than 0.30 in the ATC session alone, flag `BB_ATC_DISTORTION`.

5. **Tet Holiday Impact**:
   - Pre-Tet: BB_Width typically contracts (low volume = low volatility = squeeze).
   - Post-Tet: BB_Width typically expands sharply as the market digests holiday news.
   - The pre-Tet squeeze often produces the strongest breakout signal of the year (up or down).
   - Flag `TET_SQUEEZE` when squeeze coincides with the pre-Tet window.

6. **Sector-Specific BB Behavior**:
   - **Banking stocks** (VCB, BID, CTG, TCB, MBB): Lower baseline BB_Width due to institutional ownership and slower price movement. Use tighter squeeze thresholds.
   - **Real estate stocks** (VHM, VIC, NVL): Higher baseline BB_Width due to policy sensitivity. Wider squeeze thresholds.
   - **Speculative/Penny stocks**: BB_Width can be misleadingly wide due to tick-size effects — use BB with caution.

7. **Foreign Investor Influence**: Foreign investors often trade based on BB signals on VN30 stocks. This creates a self-reinforcing pattern where:
   - BB squeeze breakouts on VN30 stocks tend to be more reliable (foreign buying amplifies the move).
   - BB bounces on VN30 stocks also tend to be more reliable (foreign mean-reversion strategies).

8. **KRX System and Order Types**: Post-KRX migration, new order types (stop orders, conditional orders) may change how prices interact with Bollinger Bands. Monitor for structural changes in BB signal reliability.

### Bollinger + Volume Cross-Reference

For highest-quality signals in the Vietnamese market, always cross-reference V4BB with V4V (Volume Expert):

| BB Signal | Volume Confirmation | Combined Quality |
|-----------|---------------------|------------------|
| Squeeze breakout + V_Ratio > 2.0 | Strong | Quality A |
| Squeeze breakout + V_Ratio 1.0–2.0 | Moderate | Quality B |
| Squeeze breakout + V_Ratio < 1.0 | Weak | Quality C (likely fakeout) |
| Band bounce + Volume dry-up | Confirms weak selling/buying | Quality B |
| Band walk + sustained high volume | Confirms trend strength | Quality A |
