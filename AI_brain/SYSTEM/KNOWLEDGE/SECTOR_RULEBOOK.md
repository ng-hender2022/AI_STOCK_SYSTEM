# SECTOR_RULEBOOK --- AI_STOCK v2
Generated: 2026-03-15
Expert ID: V4S
Scale: -4 -> +4

---

## 1. INDICATORS / METRICS USED (with parameters)

### 1.1 Sector Classification

The 91-stock universe is grouped into sectors based on ICB (Industry Classification Benchmark) adapted for Vietnam market:

| Sector Code | Sector Name | Typical # Stocks | Key Representatives |
|-------------|-------------|-------------------|---------------------|
| BANK | Banking | 15-18 | VCB, BID, CTG, TCB, MBB, VPB, ACB, STB, HDB |
| REAL | Real Estate | 10-12 | VIC, VHM, NVL, KDH, DXG, NLG, PDR |
| STEEL | Steel / Materials | 5-7 | HPG, HSG, NKG, TLH |
| RETAIL | Retail / Consumer | 5-8 | MWG, FRT, PNJ, DGW |
| FOOD | Food & Beverage | 5-7 | VNM, MSN, SAB, KDC |
| TECH | Technology | 4-6 | FPT, CMG, ELC |
| ENERGY | Oil & Gas / Energy | 5-7 | GAS, PLX, PVD, PVS, BSR |
| UTIL | Utilities / Power | 5-7 | POW, GEG, REE, NT2, PC1 |
| SECUR | Securities / Brokerage | 5-7 | SSI, VCI, HCM, VND, SHS |
| INDUS | Industrials / Construction | 5-8 | CTD, VCG, HBC, FCN |
| OTHER | Other / Diversified | remainder | catch-all |

### 1.2 Sector Performance Metrics

| Metric | Formula | Params |
|--------|---------|--------|
| **Sector Return 5d** | equal-weighted average of 5-day returns of sector member stocks | lookback: 5 trading days |
| **Sector Return 20d** | equal-weighted average of 20-day returns | lookback: 20 trading days |
| **Sector Return 60d** | equal-weighted average of 60-day returns | lookback: 60 trading days |
| **Sector vs Market 5d** | sector_return_5d - VNINDEX_return_5d | excess return (short-term) |
| **Sector vs Market 20d** | sector_return_20d - VNINDEX_return_20d | excess return (medium-term) |
| **Sector Breadth** | % of stocks in sector where close > prev_close (today) | daily |
| **Sector Breadth SMA5** | 5-day average of daily sector breadth | smoothed |
| **Sector Rank 5d** | rank of sector by 5d return among all sectors | 1 = best, N = worst |
| **Sector Rank 20d** | rank of sector by 20d return | 1 = best |
| **Sector Rank Change** | sector_rank_20d(today) - sector_rank_20d(10 days ago) | positive = improving rank |
| **Sector Acceleration** | sector_return_5d - sector_return_20d (annualized) | positive = accelerating |

### 1.3 Sector Momentum & Rotation

| Metric | Formula | Params |
|--------|---------|--------|
| **Sector RS Ratio** | sector_return / market_return (over 20d) | ratio form |
| **Sector RS Momentum** | change in sector RS ratio over 10 days | rate of change |
| **Rotation Signal** | sector rank improved/deteriorated by >= 3 positions in 10 days | threshold: 3 rank change |
| **Sector Money Flow** | sum of (volume * price_change_sign) for sector members, normalized | proxy for sector fund flow |

---

## 2. SCORING RULES (detailed score mapping table)

### 2.1 Per-Stock Sector Score

The V4S score is assigned to EACH STOCK based on the strength of its sector.

#### Step 1: Sector Strength Score

| Condition | Sector Strength |
|-----------|-----------------|
| Sector rank 1st-2nd (among all sectors) by 20d return AND sector_vs_market_20d > +3% | +4 |
| Sector rank 1st-3rd AND sector_vs_market_20d > +1.5% | +3 |
| Sector rank top quartile AND sector_vs_market > 0% | +2 |
| Sector rank upper half AND sector breadth > 60% | +1 |
| Sector rank middle (neither top nor bottom third) | 0 |
| Sector rank lower half AND sector breadth < 40% | -1 |
| Sector rank bottom quartile AND sector_vs_market < 0% | -2 |
| Sector rank bottom 3rd AND sector_vs_market_20d < -1.5% | -3 |
| Sector rank last or 2nd-last AND sector_vs_market_20d < -3% | -4 |

#### Step 2: Sector Momentum Modifier (additive)

| Condition | Modifier |
|-----------|----------|
| Sector accelerating (5d return > 20d return, positive) AND rank improving | +1 |
| Sector acceleration neutral | 0 |
| Sector decelerating (5d return < 20d return, or negative while 20d positive) AND rank deteriorating | -1 |

#### Step 3: Rotation Signal Modifier

| Condition | Modifier |
|-----------|----------|
| Sector rank improved by >= 3 positions in 10 days (rotation INTO sector) | +1 |
| Sector rank dropped by >= 3 positions in 10 days (rotation OUT OF sector) | -1 |
| No significant rank change | 0 |

#### Step 4: Intra-Sector Relative Position

| Condition | Modifier |
|-----------|----------|
| Stock is in top 20% of its sector by 20d return | +0.5 (rounds up if needed) |
| Stock is in bottom 20% of its sector by 20d return | -0.5 |
| Stock is in middle 60% | 0 |

### 2.2 Final Score Computation

```
sector_strength = sector_strength_score  # from Step 1
momentum_mod = momentum_modifier          # from Step 2
rotation_mod = rotation_modifier          # from Step 3
intra_mod = intra_sector_modifier         # from Step 4

raw_score = sector_strength + momentum_mod + rotation_mod + intra_mod
final_score = clamp(round(raw_score), -4, +4)
```

### 2.3 Score Interpretation

| Score | Label | Meaning |
|-------|-------|---------|
| +4 | SECTOR_LEADER | Stock is in the strongest sector, sector accelerating, rotation inflow |
| +3 | SECTOR_STRONG | Stock in a top-performing sector with momentum |
| +2 | SECTOR_ABOVE_AVG | Stock in an above-average sector |
| +1 | SECTOR_MILD_BULL | Stock in a mildly outperforming sector |
| 0 | SECTOR_NEUTRAL | Sector performing in line with market |
| -1 | SECTOR_MILD_BEAR | Stock in a mildly underperforming sector |
| -2 | SECTOR_BELOW_AVG | Stock in a below-average sector |
| -3 | SECTOR_WEAK | Stock in a weak sector, losing momentum |
| -4 | SECTOR_LAGGARD | Stock in the weakest sector, sector decelerating, rotation outflow |

---

## 3. SIGNAL CODES (reference SIGNAL_CODEBOOK)

| Code | Description | Score Range |
|------|-------------|-------------|
| SEC_LEADER | Stock in top-ranked sector with acceleration | +3 to +4 |
| SEC_STRONG | Stock in strong sector | +2 |
| SEC_ABOVE_AVG | Mild sector tailwind | +1 |
| SEC_NEUTRAL | Sector in line with market | 0 |
| SEC_BELOW_AVG | Mild sector headwind | -1 |
| SEC_WEAK | Stock in underperforming sector | -2 |
| SEC_LAGGARD | Stock in bottom-ranked sector with deceleration | -3 to -4 |
| SEC_ROTATE_IN | Significant rotation into this sector (rank improved >= 3) | Positive modifier |
| SEC_ROTATE_OUT | Significant rotation out of this sector (rank dropped >= 3) | Negative modifier |
| SEC_DIVERGE_UP | Stock outperforming its own (weak) sector | Informational |
| SEC_DIVERGE_DOWN | Stock underperforming its own (strong) sector | Informational |
| SEC_BROAD_ADVANCE | Sector breadth > 80% (broad participation) | Bullish confirmation |
| SEC_NARROW | Sector breadth < 30% (narrow, fragile) | Bearish warning |
| SEC_ACCEL | Sector accelerating (5d >> 20d return) | Momentum signal |
| SEC_DECEL | Sector decelerating (5d << 20d return) | Momentum fading |

---

## 4. SIGNAL QUALITY RULES

### 4.1 Confidence Assignment
- **HIGH** (>= 0.75): Sector is clearly top/bottom ranked (rank 1-2 or last 2) AND sector breadth confirms AND momentum aligns AND rank stable for >= 5 days.
- **MEDIUM** (0.50 - 0.74): Sector clearly above/below average with at least one confirming factor (breadth or momentum).
- **LOW** (0.25 - 0.49): Sector mildly above/below average, mixed confirming factors.
- **SKIP** (< 0.25): Sector is mid-ranked with conflicting breadth and momentum. Emit SEC_NEUTRAL.

### 4.2 Minimum Sector Size
- A sector must have >= 3 stocks in the 91-stock universe to be scored separately.
- If a sector has < 3 stocks, merge it into OTHER and do not compute sector-specific signals.
- Sector statistics with only 3-4 stocks have inherently higher noise. Reduce confidence by one level for sectors with < 5 members.

### 4.3 Freshness
- Sector scores computed daily after market close.
- Sector rank changes (rotation signals) require a 10-day lookback; signals are valid for 5 trading days after detection.
- Sector acceleration signals are valid for 3 trading days.

---

## 5. EDGE CASES

### 5.1 Sector with All Stocks Suspended
- If all stocks in a sector are suspended (e.g., regulatory halt on an entire industry), do not compute sector score.
- Carry forward the previous sector score for up to 5 days, then decay to NEUTRAL.
- Flag: SECTOR_SUSPENDED.

### 5.2 Single Stock Dominating Sector Returns
- In sectors with few stocks, one large-cap stock can dominate the average.
- Check: if one stock's weight (by market cap) > 50% of sector total cap, use median return instead of mean for sector return.
- Flag: SECTOR_CONCENTRATED. Apply confidence reduction of one level.
- Affected sectors in Vietnam: FOOD (VNM dominant), ENERGY (GAS dominant), TECH (FPT dominant).

### 5.3 New Sector Formation
- If a significant number of stocks are reclassified into a new sector, the new sector has no historical sector rank data.
- Use 20d return for initial ranking, but flag as NEW_SECTOR and set confidence to LOW for the first 20 trading days.

### 5.4 All Sectors Moving Together
- In market-wide selloffs or rallies, sector dispersion collapses (all sectors move in the same direction).
- If the standard deviation of sector 5d returns < 1%, flag: LOW_DISPERSION. Sector scores become less informative.
- In low-dispersion environments, reduce all sector scores toward zero by 1 point.

### 5.5 Sector Rank Ties
- If two sectors have identical 20d returns, they share the same rank. Use 5d return as tiebreaker.
- If still tied, use sector breadth as secondary tiebreaker.

---

## 6. VIETNAM MARKET NOTES (specific adaptations for HOSE/HNX)

### 6.1 Sector Weights in VNINDEX
Approximate VNINDEX sector weights (as of 2025):
| Sector | Approx Weight |
|--------|---------------|
| Banking | 28-32% |
| Real Estate | 12-16% |
| Food & Beverage | 6-8% |
| Technology | 5-7% |
| Steel / Materials | 4-6% |
| Retail | 4-6% |
| Oil & Gas / Energy | 4-6% |
| Securities | 3-5% |
| Utilities | 3-5% |
| Other | 10-15% |

Banking dominance means VNINDEX can be "bullish" while most sectors are bearish if banks rally alone. This is why sector analysis is critical for Vietnam.

### 6.2 Vietnam Sector Rotation Cycle (typical)

| Market Phase | Leading Sectors | Lagging Sectors |
|--------------|-----------------|-----------------|
| Early Recovery | Securities, Banking | Real Estate, Materials |
| Bull Phase 1 | Banking, Real Estate | Utilities |
| Bull Phase 2 | Materials, Steel, Construction | Banking (slowing) |
| Late Bull | Small-cap speculative, Technology | All blue-chip sectors |
| Early Bear | Utilities, Consumer Staples | Securities, Real Estate |
| Bear Market | Cash (all sectors weak) | Most cyclicals |

This pattern is a guideline. Actual rotation depends on policy, global commodity prices, and credit cycles.

### 6.3 Policy-Sensitive Sectors
- **Banking**: Directly impacted by SBV monetary policy (interest rates, credit growth targets). SBV sets annual credit growth caps for each bank.
- **Real Estate**: Sensitive to credit policy, land law changes, and provincial government project approvals. The 2022-2023 corporate bond crisis heavily impacted this sector.
- **Securities**: Highly correlated with market volume and sentiment. Tends to lead market turns (both up and down).
- **Steel**: Sensitive to China steel prices and infrastructure spending. Government public investment programs boost this sector.
- **Energy**: GAS/PLX influenced by global oil prices. POW/utilities by electricity pricing policy (EVN contracts).

### 6.4 Foreign Investment by Sector
- Foreign investors heavily concentrated in Banking (VCB, ACB), Consumer (VNM), and Technology (FPT).
- Sectors with high foreign ownership are more sensitive to global risk sentiment and USD/VND movements.
- When foreign net selling is concentrated in one sector (> 200B VND/day from a single sector), that sector's score should be viewed with caution on the bullish side.

### 6.5 Sector Earnings Season Effects
- Vietnamese listed companies report quarterly earnings (Q1: Apr, Q2: Jul, Q3: Oct, Q4+Annual: Jan-Feb).
- During earnings season, sector returns can be heavily driven by a few early reporters.
- If < 50% of a sector's stocks have reported current quarter earnings, sector strength signals may be premature. Flag: EARNINGS_INCOMPLETE.

### 6.6 Sector ETF Proxies
- Vietnam currently has limited sector ETFs. The main ETFs track VNINDEX or VN30.
- Without sector ETFs, sector rotation is executed via individual stock trades, which means:
  - Sector moves are often less synchronized (stocks in the same sector may lag by days).
  - Use 5-day sector breadth (SMA5) rather than single-day breadth for more reliable readings.

### 6.7 Sector Correlation Matrix
- Vietnam sectors tend to have higher cross-correlations than mature markets (avg pairwise correlation ~0.5 vs ~0.3 in US).
- This means sector dispersion signals (low dispersion warning) trigger more frequently.
- Periods of high cross-sector correlation > 0.7 across all pairs indicate a macro-driven market where sector selection adds little value. Flag: MACRO_DRIVEN.

### 6.8 Sector and Regime Interaction
- In STRONG_BULL regime (V4REG = +4): all sectors tend to rise, sector selection is less critical. Focus on acceleration (which sectors are leading).
- In BEAR regime (V4REG <= -2): sector selection is critical for risk management. Being in the right (least-weak) sector can save significant drawdown.
- In NEUTRAL regime: sector rotation is the primary driver of alpha. V4S becomes one of the most important experts.
