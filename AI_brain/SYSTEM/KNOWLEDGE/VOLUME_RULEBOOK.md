# VOLUME RULEBOOK — AI_STOCK v2
Generated: 2026-03-15
Expert ID: V4V
Scale: -4 → +4

---

## 1. INDICATORS USED (with parameters)

| Indicator | Parameter | Description |
|-----------|-----------|-------------|
| **Volume** | Current session | Raw volume of the current trading session |
| **VMA20** | SMA(Volume, 20) | 20-day simple moving average of volume |
| **VMA5** | SMA(Volume, 5) | 5-day simple moving average of volume (short-term trend) |
| **V_Ratio** | Volume / VMA20 | Volume relative to 20-day average |
| **V_Trend** | VMA5 / VMA20 | 5-day volume trend relative to 20-day baseline |
| **Price_Change** | (Close - PrevClose) / PrevClose | Session price change percentage |
| **V_Streak** | Consecutive days V > VMA20 or V < VMA20 | Volume persistence counter |

### Derived Metrics

- **V_Ratio** = Current Volume / VMA20
- **V_Trend** = VMA5 / VMA20 (>1.0 = rising volume environment, <1.0 = declining)
- **V_Acceleration** = Today's V_Ratio - Yesterday's V_Ratio (rate of change in volume intensity)

---

## 2. SCORING RULES (detailed score mapping table)

### Primary Scoring Matrix

| Score | V_Ratio Range | Price Direction | V_Trend | Description |
|-------|---------------|-----------------|---------|-------------|
| **+4** | > 3.00 | Up >= +1.5% | > 1.30 | Volume surge with strong price advance — climactic buying |
| **+3** | 2.00 – 3.00 | Up >= +1.0% | > 1.15 | High volume breakout with confirmed price gain |
| **+2** | 1.50 – 2.00 | Up >= +0.5% | > 1.00 | Above-average volume supporting upward price move |
| **+1** | 1.10 – 1.50 | Up > 0% | >= 0.90 | Mildly elevated volume on price advance |
| **0** | 0.70 – 1.10 | Any | 0.80 – 1.20 | Normal/average volume — no signal |
| **-1** | 1.10 – 1.50 | Down < 0% | >= 0.90 | Mildly elevated volume on price decline |
| **-2** | 1.50 – 2.00 | Down <= -0.5% | > 1.00 | Above-average volume supporting downward price move |
| **-3** | 2.00 – 3.00 | Down <= -1.0% | > 1.15 | High volume breakdown with confirmed price drop |
| **-4** | > 3.00 | Down <= -1.5% | > 1.30 | Volume surge with strong price decline — climactic selling |

### Volume Dry-Up Rules

| Condition | Score Modifier | Logic |
|-----------|---------------|-------|
| V_Ratio < 0.40 | Force score to 0 | Volume too thin — no reliable signal |
| V_Ratio 0.40 – 0.60 | Clamp score to [-1, +1] | Low volume — weak conviction |
| V_Ratio 0.60 – 0.70 | Clamp score to [-2, +2] | Below-average volume — moderate conviction |

### Volume-Price Confirmation & Divergence

| Pattern | Condition | Score Adjustment |
|---------|-----------|-----------------|
| **Bullish Confirmation** | V_Ratio > 1.5 AND Price_Change > +1% | Score stays positive (no change) |
| **Bearish Confirmation** | V_Ratio > 1.5 AND Price_Change < -1% | Score stays negative (no change) |
| **Bullish Divergence** | V_Ratio < 0.7 AND Price_Change < -1% | Score += +1 (selling on low volume = weak selling) |
| **Bearish Divergence** | V_Ratio < 0.7 AND Price_Change > +1% | Score -= 1 (buying on low volume = weak buying) |
| **Volume Fakeout** | V_Ratio > 2.0 AND abs(Price_Change) < 0.3% | Clamp score to [-1, +1] — volume without price movement is suspect |

### Breakout Confirmation Rules

| Rule ID | Condition | Effect |
|---------|-----------|--------|
| **BK-1** | Price breaks 20-day high AND V_Ratio >= 2.0 | Confirm breakout: score = max(score, +3) |
| **BK-2** | Price breaks 20-day high AND V_Ratio < 1.3 | Suspect breakout: clamp score to max +1 |
| **BK-3** | Price breaks 20-day low AND V_Ratio >= 2.0 | Confirm breakdown: score = min(score, -3) |
| **BK-4** | Price breaks 20-day low AND V_Ratio < 1.3 | Suspect breakdown: clamp score to min -1 |
| **BK-5** | V_Ratio >= 2.5 sustained for 3+ days | Trend acceleration — boost magnitude by +1 (cap at +/-4) |

---

## 3. SIGNAL CODES (reference SIGNAL_CODEBOOK)

| Code | Name | Trigger |
|------|------|---------|
| `VOL_SURGE_BUY` | Volume Surge Buy | Score = +4 |
| `VOL_SURGE_SELL` | Volume Surge Sell | Score = -4 |
| `VOL_BREAKOUT_CONF` | Volume Breakout Confirmed | BK-1 triggered |
| `VOL_BREAKDOWN_CONF` | Volume Breakdown Confirmed | BK-3 triggered |
| `VOL_BREAKOUT_FAIL` | Volume Breakout Failed | BK-2 triggered |
| `VOL_BREAKDOWN_FAIL` | Volume Breakdown Failed | BK-4 triggered |
| `VOL_BULL_DIV` | Volume Bullish Divergence | Price down, volume drying up |
| `VOL_BEAR_DIV` | Volume Bearish Divergence | Price up, volume drying up |
| `VOL_CLIMAX_TOP` | Volume Climax Top | V_Ratio > 3.0, price up after sustained uptrend (5+ days) |
| `VOL_CLIMAX_BOT` | Volume Climax Bottom | V_Ratio > 3.0, price down after sustained downtrend (5+ days) |
| `VOL_DRY` | Volume Dry-Up | V_Ratio < 0.40 |
| `VOL_FAKEOUT` | Volume Fakeout | V_Ratio > 2.0 but price flat |
| `VOL_TREND_RISE` | Volume Trend Rising | V_Trend crosses above 1.20 from below |
| `VOL_TREND_FALL` | Volume Trend Falling | V_Trend crosses below 0.80 from above |

---

## 4. SIGNAL QUALITY RULES

### Quality Tiers

| Quality | Condition | Confidence |
|---------|-----------|------------|
| **A (High)** | V_Ratio > 2.0 AND V_Trend confirms direction AND price change > 1% | 80-95% |
| **B (Medium)** | V_Ratio 1.3–2.0 AND partial confirmation | 55-79% |
| **C (Low)** | V_Ratio 1.0–1.3 OR conflicting V_Trend | 35-54% |
| **D (Noise)** | V_Ratio < 0.7 OR V_Fakeout pattern | < 35% |

### Quality Modifiers

1. **Trend Alignment Bonus**: If V_Trend direction matches score direction, quality upgrades by one tier.
2. **Streak Bonus**: If V_Streak >= 3 days in same direction, quality upgrades by one tier.
3. **Divergence Penalty**: If volume direction opposes price direction, quality downgrades by one tier.
4. **Time-of-Day Filter** (for intraday): Volume in first 15 min and last 15 min of HOSE/HNX session is inflated — apply 0.7x weight to V_Ratio calculations during those windows.

### Minimum Quality for Action

- Score magnitude >= 3 requires Quality A or B to be actionable.
- Score magnitude 2 requires Quality A to be actionable.
- Score magnitude <= 1 is informational only.

---

## 5. EDGE CASES

| Edge Case | Handling |
|-----------|----------|
| **IPO / First 20 days** | VMA20 undefined — use available days as average; if < 5 days, output score = 0 with flag `INSUFFICIENT_HISTORY` |
| **Trading halt / suspension** | Volume = 0 — output score = 0 with flag `HALTED` |
| **Ex-dividend date** | Volume often spikes artificially — apply 0.7x discount to V_Ratio on ex-date and T+1 |
| **Index rebalancing day** | Quarterly FTSE/VN30 rebalancing causes non-organic volume — flag `REBAL_DAY`, reduce quality by one tier |
| **Ceiling / Floor price hit** | If price locked at ceiling (CE) or floor (FL), volume reflects unmatched demand/supply — flag `PRICE_LOCKED_CE` or `PRICE_LOCKED_FL`, score +4 or -4 respectively regardless of V_Ratio |
| **Lot size change** | HOSE 100-share lot — when lot size changes, VMA20 needs recalibration period of 20 sessions |
| **Pre-holiday thin volume** | Sessions before Tet or major holidays typically have low volume — flag `PRE_HOLIDAY`, clamp score to [-1, +1] |
| **ATC/ATO session volume** | ATC (14:30-14:45) and ATO (09:00-09:15) volumes should be tracked separately for more accurate intraday analysis |
| **Foreign block trades** | Large foreign transactions on upstairs market may not reflect in exchange volume — flag `BLOCK_TRADE_DAY` if detected |

---

## 6. VIETNAM MARKET NOTES

### Exchange-Specific Rules

| Exchange | Session Times | Matching Method | Volume Notes |
|----------|--------------|-----------------|--------------|
| **HOSE** | 09:00–11:30, 13:00–14:30, ATC 14:30–14:45 | Continuous + periodic | Highest liquidity; VN30 stocks dominate ~60% volume |
| **HNX** | 09:00–11:30, 13:00–14:30, ATC 14:30–14:45 | Continuous | Lower liquidity; wider spreads affect volume interpretation |
| **UPCOM** | 09:00–11:30, 13:00–15:00 | Negotiation-heavy | Very low liquidity — require V_Ratio > 3.0 for any signal above +/-1 |

### Vietnam-Specific Volume Patterns

1. **Tet Effect**: Volume drops 40-60% in the 5 sessions before Tet and 2-3 sessions after. Normalize V_Ratio by using a seasonal adjustment factor of 1.5x during this window.

2. **T+2.5 Settlement Cycle**: Vietnam uses T+2 settlement for stocks (T+1 for bonds). Volume clustering occurs around settlement dates — be aware of forced selling volume near T+2 of large previous-session trades.

3. **Foreign Ownership Limit (FOL)**: When a stock nears its FOL cap, foreign buying volume dries up. If FOL > 49% (or sector-specific cap), flag `FOL_NEAR_LIMIT` and discount buy-side volume signals by 0.5x.

4. **Margin Call Cascades**: Vietnam market margin ratios are regulated. During sharp drops (VN-Index down > 3%), volume surges may be margin-call driven rather than organic. Flag `MARGIN_CALL_RISK` when market drops > 2% intraday and individual stock V_Ratio > 3.0.

5. **VN30 vs Mid/Small Cap**: VN30 stocks have 5-10x the average daily volume of mid-cap stocks. Always use stock-specific VMA20, never cross-compare raw volumes between tiers.

6. **Band Limits**: HOSE +/-7%, HNX +/-10%, UPCOM +/-15%. When price hits band limit, volume signal interpretation changes fundamentally — see Edge Cases above for `PRICE_LOCKED_CE` / `PRICE_LOCKED_FL`.

7. **Lunch Break Gap**: Volume often surges at 13:00 (session open after lunch). The first 5 minutes of the afternoon session may have inflated volume — apply 0.8x weight if analyzing intraday.

8. **KRX System Migration**: Post-KRX system, order types and matching have changed. Historical volume comparisons pre/post migration require normalization. Flag `PRE_KRX` for data before migration date.

### Liquidity Tiers for Vietnam Stocks

| Tier | Avg Daily Volume (VND) | V_Ratio Threshold for Signal | Notes |
|------|------------------------|------------------------------|-------|
| **Mega** | > 100B VND/day | Standard (as above) | VN30 blue chips |
| **Large** | 20B – 100B VND/day | V_Ratio thresholds +0.2 | Mid-cap leaders |
| **Medium** | 5B – 20B VND/day | V_Ratio thresholds +0.5 | Require stricter confirmation |
| **Small** | 1B – 5B VND/day | V_Ratio thresholds +1.0 | High noise, frequent fakeouts |
| **Micro** | < 1B VND/day | Score capped at +/-2 | Unreliable volume signals |
