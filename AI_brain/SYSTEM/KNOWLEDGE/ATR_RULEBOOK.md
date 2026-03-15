# ATR RULEBOOK — AI_STOCK v2
Generated: 2026-03-15
Expert ID: V4ATR
Scale: 0 → 4

---

## 1. INDICATORS USED (with parameters)

| Indicator | Parameter | Description |
|-----------|-----------|-------------|
| **ATR** | ATR(14) | Average True Range over 14 periods — measures average volatility |
| **ATR_Pct** | ATR / Close * 100 | ATR as percentage of current price — normalized volatility |
| **ATR_SMA20** | SMA(ATR, 20) | 20-day simple moving average of ATR — baseline volatility |
| **ATR_Ratio** | ATR / ATR_SMA20 | Current ATR relative to its 20-day average |
| **ATR_Slope5** | (ATR[0] - ATR[4]) / ATR[4] | 5-day rate of change in ATR — expansion/contraction speed |
| **ATR_High20** | Highest ATR in 20 days | Upper bound of recent volatility range |
| **ATR_Low20** | Lowest ATR in 20 days | Lower bound of recent volatility range |
| **ATR_Percentile** | ATR's percentile rank within 252-day (1-year) history | Long-term volatility context |

### True Range Calculation

```
TR = max(
    High - Low,
    abs(High - PrevClose),
    abs(Low - PrevClose)
)
ATR(14) = Wilder's smoothing: ATR_prev * 13/14 + TR / 14
```

### Derived Metrics

- **ATR_Ratio** = ATR / ATR_SMA20 (>1.0 = above-average volatility, <1.0 = below-average)
- **ATR_Band_Width** = (ATR_High20 - ATR_Low20) / ATR_SMA20 (how much ATR itself varies)
- **ATR_Regime** = Classification based on ATR_Percentile (see scoring rules)

---

## 2. SCORING RULES (detailed score mapping table)

### Primary Scoring Matrix

**IMPORTANT: V4ATR is direction-neutral. It measures ONLY the magnitude of volatility, not whether the market is going up or down. Score range is 0 to 4 (no negative values).**

| Score | ATR_Ratio Range | ATR_Pct Range (typical) | ATR_Percentile | Description |
|-------|-----------------|-------------------------|----------------|-------------|
| **0** | < 0.50 | < 0.8% | < 10th | Extremely low volatility — market dormant, no movement |
| **1** | 0.50 – 0.80 | 0.8% – 1.5% | 10th – 30th | Low volatility — quiet market, tight ranges |
| **2** | 0.80 – 1.20 | 1.5% – 2.5% | 30th – 70th | Normal volatility — typical trading conditions |
| **3** | 1.20 – 2.00 | 2.5% – 4.0% | 70th – 90th | High volatility — expanded ranges, active market |
| **4** | > 2.00 | > 4.0% | > 90th | Extreme volatility — crisis-level or breakout-level movement |

### ATR Expansion/Contraction Rules

| Pattern | Condition | Score Modifier | Signal |
|---------|-----------|----------------|--------|
| **Rapid Expansion** | ATR_Slope5 > +30% | Score += 1 (cap at 4) | `ATR_EXPANDING_FAST` |
| **Steady Expansion** | ATR_Slope5 +10% to +30% | No modifier | `ATR_EXPANDING` |
| **Stable** | ATR_Slope5 -10% to +10% | No modifier | `ATR_STABLE` |
| **Steady Contraction** | ATR_Slope5 -30% to -10% | No modifier | `ATR_CONTRACTING` |
| **Rapid Contraction** | ATR_Slope5 < -30% | Score -= 1 (floor at 0) | `ATR_CONTRACTING_FAST` |

### Volatility Regime Classification

| Regime | ATR_Percentile | Typical Duration | Trading Implication |
|--------|---------------|------------------|---------------------|
| **Compressed** | < 15th | Can persist for weeks | Breakout imminent — prepare for directional move |
| **Low** | 15th – 35th | Days to weeks | Trend development phase — low-risk entries |
| **Normal** | 35th – 65th | Most of the time | Standard conditions — follow primary strategy |
| **Elevated** | 65th – 85th | Days to weeks | Active trend in progress — wider stops needed |
| **Extreme** | > 85th | Rarely > 5 days | Crisis or climactic move — caution, mean-reversion likely |

### Contextual Score Adjustments

| Context | Condition | Adjustment |
|---------|-----------|------------|
| **Compression Warning** | ATR_Ratio < 0.50 for 5+ consecutive days | Flag `SQUEEZE_BUILDING`, keep score at 0 but mark high-priority watchlist |
| **Explosion from Compression** | ATR_Ratio jumps from < 0.50 to > 1.50 in 3 days | Score = 4, flag `VOLATILITY_EXPLOSION` |
| **Mean Reversion Warning** | ATR_Ratio > 2.50 for 3+ days | Flag `ATR_MEAN_REVERSION_DUE` — extreme volatility tends to contract |
| **New Volatility Regime** | ATR_Percentile crosses above 90th from below 70th within 5 days | Flag `NEW_HIGH_VOL_REGIME` |

---

## 3. SIGNAL CODES (reference SIGNAL_CODEBOOK)

| Code | Name | Trigger |
|------|------|---------|
| `ATR_EXTREME` | Extreme Volatility | Score = 4 |
| `ATR_HIGH` | High Volatility | Score = 3 |
| `ATR_NORMAL` | Normal Volatility | Score = 2 |
| `ATR_LOW` | Low Volatility | Score = 1 |
| `ATR_DORMANT` | Dormant / No Volatility | Score = 0 |
| `ATR_EXPANDING` | ATR Expanding | ATR_Slope5 > +10% |
| `ATR_EXPANDING_FAST` | ATR Expanding Rapidly | ATR_Slope5 > +30% |
| `ATR_CONTRACTING` | ATR Contracting | ATR_Slope5 < -10% |
| `ATR_CONTRACTING_FAST` | ATR Contracting Rapidly | ATR_Slope5 < -30% |
| `ATR_STABLE` | ATR Stable | ATR_Slope5 between -10% and +10% |
| `SQUEEZE_BUILDING` | Volatility Squeeze Building | ATR_Ratio < 0.50 for 5+ days |
| `VOLATILITY_EXPLOSION` | Volatility Explosion | ATR_Ratio jumps from < 0.50 to > 1.50 in 3 days |
| `ATR_MEAN_REVERSION_DUE` | Mean Reversion Due | ATR_Ratio > 2.50 for 3+ days |
| `NEW_HIGH_VOL_REGIME` | New High Volatility Regime | ATR_Percentile crosses 90th from below 70th |
| `ATR_BREAKOUT_ZONE` | Breakout Volatility Zone | Score jumps from 0 or 1 to 3 or 4 in one session |

---

## 4. SIGNAL QUALITY RULES

### Quality Tiers

| Quality | Condition | Confidence |
|---------|-----------|------------|
| **A (High)** | ATR_Percentile extreme (< 5th or > 95th) OR Volatility Explosion pattern OR score change >= 2 in one session | 80-95% |
| **B (Medium)** | ATR_Ratio clearly above or below average (< 0.60 or > 1.60) AND consistent for 3+ days | 55-79% |
| **C (Low)** | ATR_Ratio between 0.70 and 1.40 — normal range, little informational value | 35-54% |
| **D (Noise)** | ATR fluctuating without clear trend (ATR_Band_Width > 0.5 with no direction) OR insufficient history | < 35% |

### Quality Modifiers

1. **Persistence Bonus**: If ATR_Ratio has been consistently above 1.5 or below 0.6 for 5+ days, upgrade by one tier.
2. **Regime Change Bonus**: If ATR regime changes (e.g., Compressed to Elevated), upgrade by one tier — regime changes are highly informational.
3. **Low Volume Penalty**: If today's volume < 50% of VMA20, ATR may reflect wide bid-ask spreads rather than true volatility — downgrade by one tier.
4. **Gap Penalty**: If TR is dominated by gap (abs(High - PrevClose) or abs(Low - PrevClose) > 80% of TR), ATR reflects gap risk, not intraday volatility — flag `GAP_DOMINATED_TR`.

### How Other Experts Should Use V4ATR

- **Position Sizing**: ATR directly feeds position size calculations. Higher ATR = smaller position.
- **Stop Loss**: Stops should be set as multiples of ATR (typically 1.5x - 3.0x ATR from entry).
- **Profit Targets**: Targets at 2x - 4x ATR from entry.
- **V4ATR = 0 or 1**: Potential squeeze — prepare for breakout, use tight entries.
- **V4ATR = 3 or 4**: Wide stops required — reduce position size accordingly.

---

## 5. EDGE CASES

| Edge Case | Handling |
|-----------|----------|
| **First 14 sessions** | ATR(14) requires 14 periods — use available TR values with simple average until 14 periods available; flag `ATR_WARMUP` |
| **First 20 sessions for ATR_SMA20** | ATR_SMA20 undefined — use available ATR values; if < 14, use raw TR; flag `INSUFFICIENT_ATR_HISTORY` |
| **Trading halt** | No High/Low/Close — skip day in ATR calculation; flag `HALTED` |
| **Ceiling/Floor price lock** | True Range is artificially compressed (price cannot move beyond band). ATR understates actual volatility demand. Flag `ATR_BAND_LIMITED` |
| **Limit-up / Limit-down for multiple consecutive sessions** | ATR extremely compressed due to band limits — does NOT reflect true volatility. Score = 0, flag `ATR_BAND_LOCKED_MULTI` |
| **Ex-dividend / Ex-rights** | Price gap due to corporate action — TR on ex-date is inflated. Correct: use adjusted prices for TR calculation. Flag `CORPORATE_ACTION_ATR` |
| **Stock split** | Price level changes dramatically — ATR_Pct remains valid but raw ATR needs recalculation with adjusted prices. Flag `SPLIT_ADJUSTED` |
| **Penny stock (price < 1,000 VND)** | ATR_Pct can be extremely high due to minimum tick size (10 VND = 1% for a 1,000 VND stock). Apply minimum tick normalization. Flag `PENNY_STOCK_ATR` |
| **New listing / IPO** | First 5 sessions often have extreme volatility — ATR is valid but not indicative of future regime. Flag `IPO_VOLATILITY` for first 20 sessions |
| **Circuit breaker / Market-wide halt** | If exchange triggers circuit breaker, ATR for that session is not meaningful. Flag `CIRCUIT_BREAKER` |

---

## 6. VIETNAM MARKET NOTES

### Band Limit Impact on ATR

Vietnam's price band limits directly constrain True Range:

| Exchange | Daily Price Limit | Max Possible TR (% of price) | ATR Implication |
|----------|-------------------|-------------------------------|-----------------|
| **HOSE** | +/- 7% | ~14% (gap from floor to ceiling) | ATR_Pct capped at ~14% theoretical max |
| **HNX** | +/- 10% | ~20% | Higher theoretical ATR cap |
| **UPCOM** | +/- 15% | ~30% | Highest theoretical ATR cap |

**Key Rule**: When a stock hits ceiling or floor for 2+ consecutive days, ATR is artificially suppressed. The "true" volatility is higher than ATR indicates. Flag `ATR_SUPPRESSED_BY_BAND` and note that:
- Score should be manually set to 3 or 4 depending on context.
- The volatility will "explode" when the band lock releases.

### Typical ATR Ranges for Vietnamese Stocks

| Category | Normal ATR_Pct | Low ATR_Pct | High ATR_Pct | Notes |
|----------|---------------|-------------|--------------|-------|
| **VN30 Blue Chips** | 1.5% – 2.5% | < 1.0% | > 3.5% | Most liquid, lowest relative volatility |
| **Mid Cap** | 2.0% – 3.5% | < 1.5% | > 5.0% | Moderate volatility |
| **Small Cap** | 2.5% – 4.5% | < 2.0% | > 6.0% | Higher base volatility |
| **Penny / Speculative** | 3.0% – 7.0% | < 2.5% | > 7.0% (band limit) | Frequently hits limits |

### Vietnam-Specific Volatility Patterns

1. **Tet Volatility Cycle**:
   - Pre-Tet (5-10 sessions before): ATR typically contracts as volume drops — Score tends toward 0-1.
   - Post-Tet (first 3-5 sessions): ATR typically expands sharply due to gap and accumulated news — Score often jumps to 3-4.
   - Flag `TET_WINDOW` during this period.

2. **Derivatives Expiry**: VN30 futures expire on the 3rd Thursday of each month. ATR for VN30 component stocks tends to expand on expiry day and the session before. Flag `FUTURES_EXPIRY` on these dates.

3. **Regulatory Announcements**: SSC (State Securities Commission) announcements on margin rules, foreign ownership, or trading rules can cause sudden ATR spikes. These are non-organic and may not persist. Flag `REGULATORY_EVENT` when detected.

4. **Lunch Break Gaps**: The 1.5-hour lunch break (11:30-13:00) can cause intraday gaps. For intraday ATR calculations, treat the lunch break as a potential gap source. Daily ATR naturally captures this.

5. **VN-Index Correlation**: During market-wide selloffs (VN-Index down > 3%), individual stock ATR readings are less stock-specific and more macro-driven. Flag `MARKET_WIDE_STRESS` when VN-Index ATR_Ratio > 2.0.

6. **Sector Rotation Days**: When sector-specific news hits (e.g., banking regulations, real estate policy), stocks in the affected sector may have synchronized ATR expansion while the broader market stays calm. Note the sector context in signal metadata.

### ATR-Based Position Sizing for Vietnam

Recommended risk formulas adapted for Vietnam:

```
Position_Size = (Account_Risk_Per_Trade * Account_Value) / (ATR * Stop_Multiple)

Recommended Stop Multiples by V4ATR Score:
  Score 0-1: Stop = 1.5 * ATR (tight stop, low vol)
  Score 2:   Stop = 2.0 * ATR (normal stop)
  Score 3:   Stop = 2.5 * ATR (wide stop, high vol)
  Score 4:   Stop = 3.0 * ATR (very wide stop, extreme vol)

Account_Risk_Per_Trade: Typically 1-2% for Vietnamese retail investors
```

### ATR and the Minimum Tick Size

Vietnamese stocks have different tick sizes based on price level (HOSE):

| Price Range | Tick Size | Min ATR_Pct Impact |
|-------------|-----------|---------------------|
| >= 50,000 VND | 100 VND | Negligible |
| 10,000 – 49,950 VND | 50 VND | Minor |
| < 10,000 VND | 10 VND | Can inflate ATR_Pct significantly |

For stocks below 10,000 VND, the minimum tick size (10 VND) can represent 0.1% or more of price, creating a floor for ATR_Pct. Adjust ATR_Pct thresholds upward for these stocks.
