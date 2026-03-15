# REGIME_RULEBOOK — AI_STOCK v2
Generated: 2026-03-15
Expert ID: V4REG
Scale: -4 → +4

---

## 1. INDICATORS / METRICS USED (with parameters)

### 1.1 VNINDEX Trend (Moving Average Alignment)
| Metric | Definition | Params |
|--------|-----------|--------|
| **VNINDEX_SMA20** | 20-day simple moving average of VNINDEX close | `period: 20` |
| **VNINDEX_SMA50** | 50-day simple moving average of VNINDEX close | `period: 50` |
| **VNINDEX_SMA200** | 200-day simple moving average of VNINDEX close | `period: 200` |
| **MA_Alignment** | Classification based on price vs MAs and MA ordering | See scoring rules |
| **MA_Slope_20** | Slope direction of SMA20 (degrees, positive = up) | `slope_period: 5` |
| **MA_Slope_50** | Slope direction of SMA50 | `slope_period: 10` |
| **Price_vs_MA200** | Percentage distance of VNINDEX from SMA200 | `= (close - sma200) / sma200 * 100` |

### 1.2 Market Breadth (from V4BR)
| Metric | Definition | Params |
|--------|-----------|--------|
| **Pct_Above_SMA50** | Percentage of 91 stocks above their 50-day SMA | From V4BR |
| **Pct_Above_SMA200** | Percentage of 91 stocks above their 200-day SMA | From V4BR |
| **AD_Ratio_5d** | 5-day average A/D ratio | `avg_period: 5` |
| **Breadth_Score** | V4BR composite score (-4 to +4) | From V4BR |

### 1.3 Volatility Metrics
| Metric | Definition | Params |
|--------|-----------|--------|
| **VNINDEX_Volatility_20d** | 20-day annualized historical volatility of VNINDEX daily returns | `period: 20`, `annualize: 252` |
| **VNINDEX_Volatility_60d** | 60-day annualized historical volatility | `period: 60` |
| **Vol_Ratio** | 20d vol / 60d vol — ratio > 1.5 indicates volatility expansion | — |
| **ATR_Percentile** | 14-day ATR of VNINDEX as percentile of its 252-day range | `atr_period: 14`, `pctile_lookback: 252` |
| **Max_Drawdown_20d** | Maximum peak-to-trough decline in last 20 trading days | `period: 20` |

### 1.4 Volume Trend
| Metric | Definition | Params |
|--------|-----------|--------|
| **Market_Volume_SMA20** | 20-day SMA of total HOSE trading value (billion VND) | `period: 20` |
| **Market_Volume_SMA50** | 50-day SMA of total HOSE trading value | `period: 50` |
| **Volume_Trend** | `EXPANDING` if SMA20 > SMA50 * 1.1; `CONTRACTING` if SMA20 < SMA50 * 0.9; `STABLE` otherwise | — |
| **Volume_vs_Avg** | Today's value / SMA20 — identifies abnormal volume days | — |
| **Foreign_Net_Flow_20d** | Cumulative foreign net buy/sell over 20 days (billion VND) | `period: 20` |

### 1.5 Derived Regime Indicators
| Metric | Definition | Params |
|--------|-----------|--------|
| **Trend_Score** | Composite from MA alignment + slopes (-4 to +4 sub-score) | See 2.1 |
| **Breadth_Component** | Normalized breadth score for regime (-4 to +4 sub-score) | See 2.2 |
| **Volatility_Component** | Volatility assessment (-2 to +2 modifier) | See 2.3 |
| **Volume_Component** | Volume trend assessment (-1 to +1 modifier) | See 2.4 |

---

## 2. SCORING RULES (detailed score mapping table)

### 2.1 Trend Sub-Score (weight: 40%)

| Condition | Sub-Score |
|-----------|-----------|
| Close > SMA20 > SMA50 > SMA200, all slopes positive | +4 |
| Close > SMA20 > SMA50, close > SMA200, SMA200 slope flat/positive | +3 |
| Close > SMA50, close > SMA200, SMA20 slope positive | +2 |
| Close > SMA200, close near SMA50 (within 2%) | +1 |
| Close near SMA200 (within 3%), no clear direction | 0 |
| Close < SMA200, close near SMA50 (within 2%) | -1 |
| Close < SMA50, close < SMA200, SMA20 slope negative | -2 |
| Close < SMA20 < SMA50, close < SMA200, SMA200 slope flat/negative | -3 |
| Close < SMA20 < SMA50 < SMA200, all slopes negative | -4 |

### 2.2 Breadth Sub-Score (weight: 30%)

| Condition | Sub-Score |
|-----------|-----------|
| Pct_Above_SMA50 > 80% AND Pct_Above_SMA200 > 70% | +4 |
| Pct_Above_SMA50 > 65% AND Pct_Above_SMA200 > 55% | +3 |
| Pct_Above_SMA50 > 55% AND Pct_Above_SMA200 > 45% | +2 |
| Pct_Above_SMA50 > 50% | +1 |
| Pct_Above_SMA50 between 40-50% | 0 |
| Pct_Above_SMA50 < 40% | -1 |
| Pct_Above_SMA50 < 30% AND Pct_Above_SMA200 < 45% | -2 |
| Pct_Above_SMA50 < 20% AND Pct_Above_SMA200 < 35% | -3 |
| Pct_Above_SMA50 < 15% AND Pct_Above_SMA200 < 25% | -4 |

### 2.3 Volatility Modifier (weight: 15%)

| Condition | Modifier |
|-----------|----------|
| Vol_Ratio < 0.7 AND ATR_Percentile < 20 (very low vol, calm market) | +1 |
| Vol_Ratio between 0.7-1.3 (normal) | 0 |
| Vol_Ratio > 1.5 AND market trending up (vol expansion in uptrend) | +1 |
| Vol_Ratio > 1.5 AND market trending down (vol expansion in downtrend) | -1 |
| Vol_Ratio > 2.0 (extreme volatility spike) | -2 |
| Max_Drawdown_20d > 10% | -1 additional |

### 2.4 Volume Modifier (weight: 15%)

| Condition | Modifier |
|-----------|----------|
| Volume_Trend = EXPANDING AND trend positive | +1 |
| Volume_Trend = STABLE | 0 |
| Volume_Trend = CONTRACTING AND trend positive | -1 (bearish divergence) |
| Volume_Trend = EXPANDING AND trend negative | 0 (could be capitulation) |
| Volume_Trend = CONTRACTING AND trend negative | 0 |
| Foreign_Net_Flow_20d > +2000B VND | +1 |
| Foreign_Net_Flow_20d < -2000B VND | -1 |

### 2.5 Composite Regime Score Calculation
```
raw_score = 0.40 * trend_sub + 0.30 * breadth_sub + 0.15 * vol_modifier_scaled + 0.15 * vol_trend_scaled
regime_score = round(clamp(raw_score, -4, +4))
```

Note: vol_modifier and vol_trend are scaled to -4/+4 range before weighting.

### 2.6 Regime Label Mapping

| Score | Label | Description |
|-------|-------|-------------|
| **+4** | `STRONG_BULL` | All systems go — strong uptrend, broad participation, healthy volume, low volatility |
| **+3** | `BULL` | Clear uptrend with good breadth, minor concerns possible |
| **+2** | `BULL` | Uptrend intact but some metrics weakening |
| **+1** | `WEAK_BULL` | Barely bullish, mixed signals, proceed with caution |
| **0** | `NEUTRAL` | No directional bias, range-bound or transitional |
| **-1** | `WEAK_BEAR` | Slight bearish tilt, early warning signs |
| **-2** | `BEAR` | Downtrend developing, breadth deteriorating |
| **-3** | `BEAR` | Clear downtrend with weak breadth |
| **-4** | `STRONG_BEAR` | Full bear mode — downtrend, breadth collapse, volatility elevated |

---

## 3. SIGNAL CODES (reference SIGNAL_CODEBOOK)

| Code | Meaning | Trigger |
|------|---------|---------|
| `REG_STRONG_BULL` | Market in strong bull regime | Score = +4 |
| `REG_BULL` | Market in bull regime | Score = +2 or +3 |
| `REG_WEAK_BULL` | Market in weak bull / early bull | Score = +1 |
| `REG_NEUTRAL` | No clear regime | Score = 0 |
| `REG_WEAK_BEAR` | Market in weak bear / early bear | Score = -1 |
| `REG_BEAR` | Market in bear regime | Score = -2 or -3 |
| `REG_STRONG_BEAR` | Market in strong bear regime | Score = -4 |
| `REG_TRANSITION_UP` | Regime score increased by 2+ in 5 days | Regime improving |
| `REG_TRANSITION_DOWN` | Regime score decreased by 2+ in 5 days | Regime deteriorating |
| `REG_GOLDEN_CROSS` | SMA50 crosses above SMA200 | Major bull signal |
| `REG_DEATH_CROSS` | SMA50 crosses below SMA200 | Major bear signal |
| `REG_VOLATILITY_SPIKE` | Vol_Ratio > 2.0 | Risk warning |
| `REG_CAPITULATION` | Score = -4 AND Vol_Ratio > 1.5 AND Volume_Trend = EXPANDING | Potential bottom |
| `REG_EUPHORIA` | Score = +4 AND Vol_Ratio > 1.5 AND Volume_Trend = EXPANDING | Potential top |

---

## 4. SIGNAL QUALITY RULES

### 4.1 Regime Stability
| Level | Criteria |
|-------|----------|
| **STABLE** | Same regime label for 10+ trading days | Confidence in regime is HIGH |
| **TRANSITIONING** | Regime label changed within last 10 days | Confidence MEDIUM, signals may whipsaw |
| **VOLATILE** | Regime label changed 3+ times in last 20 days | Confidence LOW, market is choppy |

### 4.2 Output Destinations
- **signals.db**: Write regime_score for each symbol (all 91 stocks receive the same regime score since this is a market-level expert)
- **market.db.market_regime**: Write regime_score, regime_label, all component sub-scores, and timestamp
- Both destinations updated simultaneously at end of each trading day

### 4.3 Regime Score Smoothing
- To prevent whipsaw, apply a **1-day confirmation rule**: regime label only changes if the new score persists for 2 consecutive days
- Exception: transitions to `STRONG_BEAR` (-4) or signals tagged `REG_CAPITULATION` take effect immediately (risk management priority)
- Smoothed score stored separately from raw score. Both are logged.

### 4.4 Minimum Data Requirements
- SMA200 requires 200 trading days of VNINDEX data
- If VNINDEX history < 200 days: use SMA100 as substitute, flag `REG_SHORT_HISTORY`
- Volatility metrics require minimum 60 trading days
- Breadth requires all component data from V4BR

---

## 5. EDGE CASES

### 5.1 Regime Transitions
- **Bull to Bear Transition**: Typically passes through WEAK_BULL and NEUTRAL. If score drops from +3 to -2 in under 5 days, flag `REG_RAPID_BEAR_ONSET` — this usually indicates an external shock.
- **Bear to Bull Transition**: Often slower. A move from -3 to +1 in under 10 days usually indicates a relief rally, not regime change. Flag `REG_BEAR_RALLY` and maintain BEAR label until +1 persists for 10+ days.

### 5.2 V-shaped Recoveries
- If score goes from -4 to -1 within 5 days: flag `REG_V_RECOVERY_ATTEMPT`
- Do NOT immediately switch to bullish regime. Require breadth confirmation (Pct_Above_SMA50 must cross above 40%)
- Historical: V-shaped recoveries in Vietnam are common after panic sell-offs but often retest lows

### 5.3 Index at All-Time High
- When VNINDEX is within 2% of all-time high: regime score naturally high
- Add flag `REG_ATH_PROXIMITY` — this is informational, not a modifier
- At ATH, watch for volatility expansion as a potential regime change signal

### 5.4 Extended Range-Bound Market
- If VNINDEX trades within a 5% range for 30+ days: regime often oscillates between -1 and +1
- Flag `REG_RANGE_BOUND` and set regime label to `NEUTRAL` regardless of small score fluctuations
- Exit range-bound: requires close outside the 30-day range with volume > 1.3x average

### 5.5 Gap-Driven Regime Changes
- If VNINDEX gaps down > 3% in a single session (rare on HOSE due to limits): immediately evaluate regime
- Override 2-day confirmation rule if gap-down moves score to -3 or -4
- Flag `REG_GAP_SHOCK`

### 5.6 End-of-Year / Tet Effects
- Last 2 weeks of December and first week of January: institutional portfolio rebalancing can distort trends
- Flag `REG_YEAR_END_DISTORTION`
- Tet holiday (variable dates): 1-2 weeks before Tet typically sees reduced volume and trend compression

---

## 6. VIETNAM MARKET NOTES (specific adaptations for HOSE/HNX)

### 6.1 VNINDEX as Regime Proxy
- VNINDEX is the primary index for regime classification (HOSE composite, cap-weighted)
- VN30 may lead or lag VNINDEX during regime transitions:
  - VN30 leading down while VNINDEX holds = large-cap led decline (often foreign-driven)
  - Small-cap leading down while VN30 holds = retail-driven decline
- Log both VNINDEX and VN30 regime metrics, but official regime uses VNINDEX

### 6.2 Volatility Norms for Vietnam
| Market State | Annualized Vol (20d) | Interpretation |
|-------------|---------------------|----------------|
| Low volatility | < 12% | Unusual calm, often precedes move |
| Normal | 12% - 22% | Standard trading conditions |
| Elevated | 22% - 35% | Increased uncertainty, regime may be shifting |
| Crisis | > 35% | Extreme stress, typically STRONG_BEAR |

### 6.3 Volume Norms for HOSE
| Volume Level | Daily Value (Billion VND) | Interpretation |
|-------------|--------------------------|----------------|
| Very Low | < 8,000 | Holiday/pre-holiday, no conviction |
| Low | 8,000 - 12,000 | Below average, indecisive |
| Normal | 12,000 - 20,000 | Average conditions |
| High | 20,000 - 30,000 | Above average, conviction |
| Very High | > 30,000 | Exceptional, often at turning points |

### 6.4 Foreign Flow Regime Impact
- Sustained foreign selling > 500B VND/day for 10+ days often coincides with BEAR regime
- Foreign reversal from selling to buying can precede regime improvement by 5-10 days (leading indicator)
- Track cumulative foreign flow: if 20-day net sell > 5,000B VND, flag `REG_FOREIGN_EXODUS`

### 6.5 Margin Debt and Regime
- Vietnam margin lending data published weekly/monthly by SSC/exchanges
- High margin-to-market-cap ratio (>3%) combined with BEAR regime = high crash risk
- Margin cascade (forced selling) can accelerate regime deterioration from -2 to -4 in 2-3 days
- Flag `REG_MARGIN_RISK_HIGH` when margin levels are elevated and regime is weakening

### 6.6 Regulatory / Policy Events
- SBV interest rate changes can shift regime rapidly
- Government bond yield curve changes (especially 10Y yield) affect equity regime
- Major policy announcements (new listing rules, tax changes, market opening to foreigners) can create regime discontinuities
- These events cannot be automatically detected — manual flag `REG_POLICY_EVENT` when applicable

### 6.7 Global Correlation
- VNINDEX correlation with S&P500 varies by regime:
  - Bull regime: correlation ~0.3-0.4 (moderate)
  - Bear regime: correlation increases to 0.5-0.7 (contagion)
  - Crisis: correlation can spike to 0.8+
- Monitor overnight S&P500 / Asian futures as early warning for regime stress
- Flag `REG_GLOBAL_STRESS` if S&P500 drops >3% in a session (Vietnam will likely be affected next day)

### 6.8 Dual Database Write
This expert is unique in writing to **two databases**:
1. `signals.db` — regime_score is written per symbol (all 91 stocks get the same market regime score)
2. `market.db.market_regime` — full regime record with:
   - `regime_score` (int, -4 to +4)
   - `regime_label` (string, e.g., "STRONG_BULL")
   - `trend_sub_score` (float)
   - `breadth_sub_score` (float)
   - `volatility_modifier` (float)
   - `volume_modifier` (float)
   - `regime_stable_days` (int, how many days current label has persisted)
   - `timestamp` (datetime)
   - `signal_codes` (list of active signal codes)
