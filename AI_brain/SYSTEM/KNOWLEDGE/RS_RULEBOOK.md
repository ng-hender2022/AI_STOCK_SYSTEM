# RS_RULEBOOK — AI_STOCK v2
Generated: 2026-03-15
Expert ID: V4RS
Scale: -4 → +4

---

## 1. INDICATORS / METRICS USED (with parameters)

### 1.1 Relative Strength Ratio
| Metric | Definition | Params |
|--------|-----------|--------|
| **RS_5d** | Stock 5-day return / VNINDEX 5-day return | `period: 5` |
| **RS_20d** | Stock 20-day return / VNINDEX 20-day return | `period: 20` |
| **RS_60d** | Stock 60-day return / VNINDEX 60-day return | `period: 60` |
| **RS_Composite** | Weighted average: `0.25 * RS_5d + 0.35 * RS_20d + 0.40 * RS_60d` | Weights emphasize medium-term |
| **RS_Line** | Cumulative RS ratio over time (stock price / VNINDEX level), normalized to 100 at start | Continuous |

### 1.2 Relative Strength Trend
| Metric | Definition | Params |
|--------|-----------|--------|
| **RS_SMA10** | 10-day SMA of RS_Line | `sma_period: 10` |
| **RS_SMA30** | 30-day SMA of RS_Line | `sma_period: 30` |
| **RS_Trend** | Direction label: `RISING` if RS_SMA10 > RS_SMA30 and both slopes positive; `FALLING` if RS_SMA10 < RS_SMA30 and both slopes negative; `FLAT` otherwise | — |
| **RS_Slope** | Linear regression slope of RS_Line over 20 days, standardized | `slope_period: 20` |
| **RS_Acceleration** | Change in RS_Slope over 10 days (is RS strengthening or weakening?) | `accel_period: 10` |

### 1.3 Relative Strength Rank
| Metric | Definition | Params |
|--------|-----------|--------|
| **RS_Rank_20d** | Percentile rank of stock's 20-day RS among all 91 stocks (0-100) | — |
| **RS_Rank_60d** | Percentile rank of stock's 60-day RS among all 91 stocks (0-100) | — |
| **RS_Rank_Composite** | `0.4 * RS_Rank_20d + 0.6 * RS_Rank_60d` | — |
| **RS_Rank_Change** | Change in RS_Rank_Composite over 10 days | `change_period: 10` |
| **RS_Decile** | Which decile (1-10) the stock falls in based on RS_Rank_Composite. Decile 1 = top 10%. | — |

### 1.4 RS vs Sector
| Metric | Definition | Params |
|--------|-----------|--------|
| **RS_vs_Sector** | Stock return / Sector average return (same periods as RS ratio) | Same periods |
| **Sector_RS** | Sector average return / VNINDEX return | — |

---

## 2. SCORING RULES (detailed score mapping table)

### 2.1 Primary Score from RS_Decile + RS_Trend

| RS_Decile | RS_Trend = RISING | RS_Trend = FLAT | RS_Trend = FALLING |
|-----------|-------------------|-----------------|-------------------|
| 1 (top 10%) | **+4** | +3 | +2 |
| 2 (11-20%) | +3 | +2 | +1 |
| 3 (21-30%) | +2 | +2 | +1 |
| 4 (31-40%) | +2 | +1 | 0 |
| 5 (41-50%) | +1 | 0 | 0 |
| 6 (51-60%) | 0 | 0 | -1 |
| 7 (61-70%) | 0 | -1 | -2 |
| 8 (71-80%) | -1 | -2 | -2 |
| 9 (81-90%) | -2 | -2 | -3 |
| 10 (bottom 10%) | -2 | -3 | **-4** |

### 2.2 Score Modifiers

| Condition | Modifier | Notes |
|-----------|----------|-------|
| RS_Rank_Change > +20 (10-day improvement) | +1 | Rapidly improving relative strength |
| RS_Rank_Change < -20 (10-day deterioration) | -1 | Rapidly deteriorating relative strength |
| RS_Acceleration > 0 AND RS_Trend = RISING | +1 | Accelerating outperformance |
| RS_Acceleration < 0 AND RS_Trend = FALLING | -1 | Accelerating underperformance |
| All three RS periods (5d, 20d, 60d) agree in direction | +/-1 toward that direction | Full alignment across timeframes |
| RS_vs_Sector > 1.2 (outperforming own sector by 20%+) | +1 | Stock is sector leader |
| RS_vs_Sector < 0.8 (underperforming own sector by 20%+) | -1 | Stock is sector laggard |

### 2.3 Final Score
```
final_score = clamp(primary_score + sum(modifiers), -4, +4)
```

---

## 3. SIGNAL CODES (reference SIGNAL_CODEBOOK)

| Code | Meaning | Typical Score |
|------|---------|---------------|
| `RS_TOP_LEADER` | Top decile RS across all periods, trend rising | +4 |
| `RS_EMERGING_LEADER` | RS rank improving rapidly, entering top quartile | +3 |
| `RS_OUTPERFORMER` | Above-average RS, stable or improving | +2 |
| `RS_MILD_OUTPERFORM` | Slight outperformance, not yet decisive | +1 |
| `RS_NEUTRAL` | RS near market average, no edge | 0 |
| `RS_MILD_UNDERPERFORM` | Slight underperformance | -1 |
| `RS_UNDERPERFORMER` | Below-average RS, stable or declining | -2 |
| `RS_DETERIORATING` | RS rank declining rapidly, falling out of top half | -3 |
| `RS_BOTTOM_LAGGARD` | Bottom decile, trend falling — persistent weakness | -4 |
| `RS_TREND_REVERSAL_UP` | RS trend flipping from FALLING to RISING (SMA10 crosses above SMA30) | +1 to +2 |
| `RS_TREND_REVERSAL_DOWN` | RS trend flipping from RISING to FALLING (SMA10 crosses below SMA30) | -1 to -2 |
| `RS_NEW_HIGH` | RS_Line at new 60-day high — breakout in relative terms | +1 bonus |
| `RS_NEW_LOW` | RS_Line at new 60-day low — breakdown in relative terms | -1 penalty |
| `RS_SECTOR_LEADER` | Strongest stock within its sector by RS | Context flag |
| `RS_SECTOR_LAGGARD` | Weakest stock within its sector by RS | Context flag |

---

## 4. SIGNAL QUALITY RULES

### 4.1 Confidence Assessment
| Level | Criteria |
|-------|----------|
| **HIGH** | RS_Decile in top/bottom 2 deciles, RS_Trend confirms, all periods agree, rank stable for 10+ days |
| **MEDIUM** | RS_Decile in top/bottom 3 deciles, trend partially confirms, 2 of 3 periods agree |
| **LOW** | Middle deciles (4-7), mixed signals across periods |
| **TRANSITIONAL** | RS rank changing rapidly (>15 rank change in 10 days) — signal may not persist |

### 4.2 Lookback Requirements
- RS_5d: requires minimum 10 trading days of data
- RS_20d: requires minimum 30 trading days of data
- RS_60d: requires minimum 80 trading days of data
- RS_Rank: requires all 91 stocks to have valid data for the period. If fewer than 80 stocks have data, flag `RS_INCOMPLETE_UNIVERSE`

### 4.3 Recalculation Frequency
- RS ratios and ranks recalculated **daily at end of session**
- RS_Trend evaluated daily but only changes label when SMA crossover is confirmed for 2 consecutive days (avoids whipsaw)
- Score is valid for **1 trading day**

### 4.4 Signal Persistence
- RS signals tend to be persistent (momentum effect). A stock in decile 1 typically stays in top 3 deciles for 20-40 trading days.
- Treat rapid decile changes (>3 decile shift in 5 days) as anomalous — flag `RS_RAPID_SHIFT` and reduce confidence.

---

## 5. EDGE CASES

### 5.1 VNINDEX Flat Days
- If VNINDEX return is near zero (absolute return < 0.05%) for a period, RS ratio can produce extreme values.
- When VNINDEX period return is between -0.1% and +0.1%, use **absolute return rank** instead of RS ratio for that period. Flag `RS_INDEX_FLAT`.

### 5.2 Stock with Extreme Returns
- If stock return > +30% in 20 days (ceiling hits, special events), RS ratio will be extreme.
- Cap single-period RS contribution to the equivalent of decile 1/10 score. The overall score still maxes at +/-4 but don't let one extreme period dominate.
- If stock hits ceiling for 3+ consecutive days, flag `RS_CEILING_STREAK` — RS is mechanically inflated.

### 5.3 Newly Listed or Resumed Stocks
- Stocks with fewer than 60 trading days: compute RS only for available periods. Use RS_5d and RS_20d with higher weights.
- Stocks with fewer than 20 trading days: output score = 0, code `RS_NEUTRAL`, flag `RS_NEW_LISTING`.
- Stocks resuming after suspension: exclude first 5 trading days post-resumption from RS calculation. Flag `RS_POST_SUSPENSION`.

### 5.4 Corporate Actions
- Stock splits, bonus shares, rights issues: ensure price data is adjusted. If unadjusted data detected (daily return > +15% or < -15% without ceiling/floor), flag `RS_CORP_ACTION_SUSPECT`.
- Ex-dividend days: price drop is mechanical, not RS deterioration. If stock drops by approximately the dividend amount on ex-date, exclude that day from RS short-term (5d) calculation.

### 5.5 Sector Concentration in Deciles
- If top decile is dominated by one sector (>60% of top decile from same sector), flag `RS_SECTOR_CONCENTRATED`. This indicates sector rotation rather than stock-specific strength.
- Cross-reference with V4S (sector expert) to distinguish sector effect from stock-specific alpha.

---

## 6. VIETNAM MARKET NOTES (specific adaptations for HOSE/HNX)

### 6.1 Benchmark Selection
- Primary benchmark: **VNINDEX** (HOSE composite)
- For HNX-listed stocks in the universe, still use VNINDEX as benchmark (it is the market reference)
- Do NOT use VN30 as benchmark — it is too narrow and creates distortions for non-VN30 stocks

### 6.2 RS Behavior in Vietnam Market Regimes
| Regime | RS Characteristic |
|--------|-------------------|
| Strong Bull | RS dispersion is moderate. Most stocks rise. Top decile stocks tend to be momentum leaders. |
| Weak Bull | RS dispersion increases. Top decile stocks outperform significantly while bottom half lags. |
| Bear Market | RS becomes less predictive. Even top-RS stocks decline. Relative outperformance may mean "declining less." |
| Recovery | RS leaders from prior bull often lag in recovery. New leaders emerge. Watch for RS_TREND_REVERSAL_UP signals. |

### 6.3 Foreign Favorite Stocks
- Certain stocks (VNM, HPG, MSN, VHM, VIC, etc.) have high foreign ownership and their RS is influenced by global/EM fund flows
- When global EM outflows occur, these stocks' RS deteriorates mechanically regardless of fundamentals
- Flag stocks with foreign ownership > 30% as `RS_FOREIGN_SENSITIVE`

### 6.4 Price Limit Impact on RS
- 7% daily limit on HOSE means maximum daily outperformance vs VNINDEX is capped
- Consecutive ceiling-hit days create mechanically high RS — this is real outperformance but the magnitude is constrained
- When calculating 5d RS and stock hit ceiling 3+ of 5 days, note that actual buyer demand may exceed observed return. Flag `RS_CEILING_CONSTRAINED`.

### 6.5 Liquidity Filter
- RS signals on illiquid stocks are unreliable — a stock can be in the top decile purely due to one large buy order
- Cross-reference with V4LIQ: if V4LIQ score <= -2, reduce RS confidence by one level
- Minimum liquidity for reliable RS: average daily value > 2 billion VND over 20 days

### 6.6 Vietnamese Market Momentum Characteristics
- Momentum effect in Vietnam tends to be stronger in mid-cap stocks than large caps
- Mean reversion is faster for VN30 stocks (RS leadership typically lasts 15-25 days)
- Mid-cap RS leadership can persist 30-60 days
- RS rank reversal (decile 10 to decile 1) in under 20 days is common during sector rotation — treat with caution

### 6.7 Sector RS Cross-Reference
- Always emit `RS_SECTOR_LEADER` or `RS_SECTOR_LAGGARD` flags alongside the main RS score
- This helps V4S (sector expert) and the meta-aggregator distinguish between:
  - Strong stock in strong sector (double positive)
  - Strong stock in weak sector (stock-specific alpha — higher conviction)
  - Weak stock in strong sector (potential catch-up or fundamental problem)
  - Weak stock in weak sector (double negative — avoid)
