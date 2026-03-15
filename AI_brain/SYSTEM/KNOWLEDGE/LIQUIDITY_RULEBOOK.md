# LIQUIDITY_RULEBOOK — AI_STOCK v2
Generated: 2026-03-15
Expert ID: V4LIQ
Scale: -4 → +4

---

## 1. INDICATORS / METRICS USED (with parameters)

### 1.1 Average Daily Trading Value
| Metric | Definition | Params |
|--------|-----------|--------|
| **ADTV_20d** | Average daily traded value over 20 trading days (billion VND) | `period: 20` |
| **ADTV_60d** | Average daily traded value over 60 trading days (billion VND) | `period: 60` |
| **ADTV_Ratio** | ADTV_20d / ADTV_60d — ratio > 1 means liquidity improving, < 1 means declining | — |
| **Today_Value** | Today's total traded value (billion VND) | — |
| **Today_vs_Avg** | Today_Value / ADTV_20d — identifies abnormal volume days | — |

### 1.2 Volume Consistency
| Metric | Definition | Params |
|--------|-----------|--------|
| **Volume_CV** | Coefficient of variation (std / mean) of daily volume over 20 days | `period: 20` |
| **Zero_Volume_Days** | Count of days with zero or near-zero volume (<100 shares) in last 20 days | `period: 20`, `threshold: 100` |
| **Min_Daily_Volume_20d** | Minimum daily volume in last 20 days | `period: 20` |
| **Pct_Days_Above_1B** | Percentage of last 20 days where traded value > 1 billion VND | `period: 20`, `value_threshold: 1.0` |

### 1.3 Bid-Ask Spread Proxy
| Metric | Definition | Params |
|--------|-----------|--------|
| **HL_Spread** | (High - Low) / Close — proxy for intraday spread/volatility | Daily |
| **HL_Spread_20d_Avg** | 20-day average of HL_Spread | `period: 20` |
| **HL_Spread_Percentile** | Where current HL_Spread sits vs 60-day history (0-100) | `lookback: 60` |
| **Close_vs_VWAP_Proxy** | abs(Close - (High+Low+Close)/3) / Close — measures how far close deviates from typical price | — |

**Note**: Vietnam exchanges do not publish official bid-ask spread data intraday for historical analysis. We use High-Low range as a proxy. Higher HL_Spread = wider effective spread = worse liquidity.

### 1.4 Liquidity Trend
| Metric | Definition | Params |
|--------|-----------|--------|
| **Liquidity_Trend** | Label: `IMPROVING` if ADTV_Ratio > 1.15; `DECLINING` if ADTV_Ratio < 0.85; `STABLE` otherwise | — |
| **Volume_SMA5** | 5-day SMA of daily traded value — short-term volume trend | `period: 5` |
| **Volume_SMA20** | 20-day SMA of daily traded value | `period: 20` |
| **Volume_Breakout** | Today_vs_Avg > 3.0 — exceptional volume day | `threshold: 3.0` |
| **Volume_Drought** | Today_vs_Avg < 0.3 — extremely low volume day | `threshold: 0.3` |

### 1.5 Institutional Capacity
| Metric | Definition | Params |
|--------|-----------|--------|
| **Capacity_Score** | ADTV_20d / threshold tiers — can institutional investors trade this stock? | See thresholds below |
| **Days_to_Build_Position** | Estimated days to accumulate 1% of free float at 10% of ADTV | `participation_rate: 0.10` |
| **Days_to_Exit_Position** | Same calculation for selling | `participation_rate: 0.10` |

---

## 2. SCORING RULES (detailed score mapping table)

### 2.1 ADTV Tier Sub-Score (primary, weight 40%)

| ADTV_20d (Billion VND/day) | Tier Label | Sub-Score |
|---------------------------|------------|-----------|
| > 50 | `MEGA_LIQUID` | +4 |
| 20 - 50 | `HIGH_LIQUID` | +3 |
| 10 - 20 | `GOOD_LIQUID` | +2 |
| 5 - 10 | `MODERATE_LIQUID` | +1 |
| 2 - 5 | `LOW_LIQUID` | 0 |
| 1 - 2 | `VERY_LOW_LIQUID` | -1 |
| 0.5 - 1 | `ILLIQUID` | -2 |
| 0.1 - 0.5 | `VERY_ILLIQUID` | -3 |
| < 0.1 | `UNTRADEABLE` | -4 |

**Note**: These thresholds are calibrated for the Vietnamese market. 10B VND/day (~$400K USD) is considered the minimum for comfortable institutional trading.

### 2.2 Volume Consistency Sub-Score (weight 20%)

| Condition | Sub-Score |
|-----------|-----------|
| Volume_CV < 0.5 AND Zero_Volume_Days = 0 AND Pct_Days_Above_1B = 100% | +4 |
| Volume_CV < 0.7 AND Zero_Volume_Days = 0 | +2 |
| Volume_CV < 1.0 AND Zero_Volume_Days <= 1 | +1 |
| Volume_CV < 1.0 AND Zero_Volume_Days <= 3 | 0 |
| Volume_CV 1.0 - 1.5 OR Zero_Volume_Days 3-5 | -1 |
| Volume_CV 1.5 - 2.0 OR Zero_Volume_Days 5-10 | -2 |
| Volume_CV > 2.0 OR Zero_Volume_Days > 10 | -4 |

### 2.3 Spread Proxy Sub-Score (weight 20%)

| HL_Spread_20d_Avg | Sub-Score |
|-------------------|-----------|
| < 1.0% | +4 (very tight, blue-chip level) |
| 1.0% - 1.5% | +2 |
| 1.5% - 2.5% | +1 |
| 2.5% - 3.5% | 0 |
| 3.5% - 5.0% | -1 |
| 5.0% - 7.0% | -2 |
| 7.0% - 10.0% | -3 |
| > 10.0% | -4 (extremely wide, likely illiquid or volatile) |

### 2.4 Liquidity Trend Sub-Score (weight 20%)

| Condition | Sub-Score |
|-----------|-----------|
| ADTV_Ratio > 1.5 AND Volume_Breakout in last 5 days | +4 (surge) |
| ADTV_Ratio > 1.3 | +3 |
| ADTV_Ratio > 1.15 | +2 |
| ADTV_Ratio 1.05 - 1.15 | +1 |
| ADTV_Ratio 0.90 - 1.05 | 0 (stable) |
| ADTV_Ratio 0.75 - 0.90 | -1 |
| ADTV_Ratio 0.60 - 0.75 | -2 |
| ADTV_Ratio < 0.60 | -3 (liquidity drying up) |
| ADTV_Ratio < 0.40 AND Volume_Drought in last 3 days | -4 (severe) |

### 2.5 Composite Score Calculation
```
raw_score = 0.40 * adtv_sub + 0.20 * consistency_sub + 0.20 * spread_sub + 0.20 * trend_sub
final_score = round(clamp(raw_score, -4, +4))
```

### 2.6 Override Rules

| Condition | Override |
|-----------|----------|
| ADTV_20d < 0.1B VND (untradeable) | Force score = -4 regardless of other metrics |
| Zero_Volume_Days >= 15 out of 20 | Force score = -4 |
| Volume_Breakout (>3x avg) on a single day but ADTV_20d < 1B | Do NOT upgrade score — one-day spike does not fix structural illiquidity |

---

## 3. SIGNAL CODES (reference SIGNAL_CODEBOOK)

| Code | Meaning | Typical Score |
|------|---------|---------------|
| `LIQ_MEGA` | Mega-liquid, institutional-grade, no execution concern | +4 |
| `LIQ_HIGH` | High liquidity, comfortable for most strategies | +3 |
| `LIQ_GOOD` | Good liquidity, adequate for moderate position sizes | +2 |
| `LIQ_MODERATE` | Moderate liquidity, need to manage position sizing | +1 |
| `LIQ_LOW` | Low liquidity, execution risk is real | 0 |
| `LIQ_VERY_LOW` | Very low liquidity, limit orders only | -1 |
| `LIQ_ILLIQUID` | Illiquid, difficult to trade, slippage expected | -2 |
| `LIQ_VERY_ILLIQUID` | Very illiquid, only small positions feasible | -3 |
| `LIQ_UNTRADEABLE` | Essentially untradeable, no meaningful daily volume | -4 |
| `LIQ_IMPROVING` | Liquidity trend improving (ADTV_Ratio > 1.15) | Positive modifier |
| `LIQ_DECLINING` | Liquidity trend declining (ADTV_Ratio < 0.85) | Negative modifier |
| `LIQ_SURGE` | Volume spike >3x average — potential catalyst event | Flag |
| `LIQ_DROUGHT` | Volume <30% of average — no interest | Flag |
| `LIQ_INCONSISTENT` | High volume CV — unreliable liquidity | Warning |
| `LIQ_WIDE_SPREAD` | HL_Spread proxy > 5% — high transaction cost | Warning |
| `LIQ_INSTITUTIONAL` | ADTV > 10B VND, suitable for institutional flow | Quality flag |

---

## 4. SIGNAL QUALITY RULES

### 4.1 Confidence Assessment
| Level | Criteria |
|-------|----------|
| **HIGH** | ADTV_20d > 10B VND, Volume_CV < 0.7, no zero-volume days, consistent across 20d and 60d | Score is reliable |
| **MEDIUM** | ADTV_20d 2-10B VND, Volume_CV < 1.0, fewer than 3 zero-volume days | Score is reasonable but execution matters |
| **LOW** | ADTV_20d < 2B VND or Volume_CV > 1.0 or > 3 zero-volume days | Score reflects poor liquidity accurately but all other expert signals for this stock should be discounted |
| **REJECT** | ADTV_20d < 0.1B VND | Stock should be excluded from active analysis |

### 4.2 Cross-Expert Impact
The liquidity score directly impacts other experts' confidence:

| V4LIQ Score | Impact on Other Experts |
|-------------|------------------------|
| +3 to +4 | No adjustment. Full confidence in other signals. |
| +1 to +2 | Other experts operate normally. |
| 0 | Other experts' scores capped at +/-3. |
| -1 to -2 | Other experts' scores capped at +/-2. Candle patterns unreliable. |
| -3 to -4 | Other experts' scores capped at +/-1. Consider excluding stock from active signals. |

### 4.3 Recalculation
- Liquidity scores recalculated **daily at end of session**
- ADTV is inherently smoothed (20-day average), so daily changes are incremental
- Score is valid for **1 trading day** but typically stable (changes slowly unless there is a volume event)

### 4.4 Minimum Data
- Requires minimum 20 trading days of volume data
- If fewer than 20 days available (new listing), use available data and flag `LIQ_SHORT_HISTORY`
- If fewer than 5 days, output score = 0, code `LIQ_MODERATE`, flag `LIQ_INSUFFICIENT_DATA`

---

## 5. EDGE CASES

### 5.1 Volume Spikes from Corporate Events
- Rights issue ex-dates: volume may spike as rights are traded. This is not organic liquidity improvement.
- If volume > 5x average AND there is a known corporate event, flag `LIQ_CORP_EVENT_VOLUME`. Do not update ADTV trend from this day.
- Block trade (thoa thuan) volume: some exchanges report block trades separately. If block trade volume > 50% of day's total, flag `LIQ_BLOCK_TRADE`. Block trades do not improve retail execution quality.

### 5.2 ATC/ATO Volume Concentration
- If >60% of a stock's daily volume occurs in ATC (closing auction) or ATO (opening auction), the continuous session liquidity is poor.
- Flag `LIQ_AUCTION_CONCENTRATED` — effective liquidity during trading hours is worse than ADTV suggests.
- Adjust effective ADTV downward by multiplying by the continuous-session volume percentage.

### 5.3 Free Float Issues
- Some Vietnamese stocks have very low free float (controlling shareholder holds 70%+). Even with decent ADTV, liquidity can evaporate during stress.
- If known free float < 30%, flag `LIQ_LOW_FREE_FLOAT`.
- If ADTV > 5B VND but free float < 20%, reduce ADTV tier sub-score by 1 (liquidity is fragile).

### 5.4 Stock Suspension and Resumption
- If stock was suspended, ADTV_20d will naturally decline (zero-volume days included).
- After resumption, exclude the suspension period from ADTV calculation for 10 trading days. Use post-resumption data only.
- First 3 days after resumption: volume is often abnormally high (pent-up demand). Flag `LIQ_POST_SUSPENSION_SURGE`.

### 5.5 Market-Wide Low Volume Days
- Before Tet, before long holidays: entire market volume drops 30-50%.
- If market total value < 50% of its 20-day average, flag `LIQ_MARKET_THIN_DAY`.
- On these days, do NOT penalize individual stocks for low volume. Adjust by normalizing to market volume (stock_volume_ratio = stock_value / market_value).

### 5.6 Penny Stock Liquidity Trap
- Stocks priced < 5,000 VND can show misleadingly high share volume but low value.
- Always use **value** (VND) not share count for liquidity assessment.
- Penny stocks with ADTV_value < 0.5B VND: force score <= -2 regardless of share volume.

---

## 6. VIETNAM MARKET NOTES (specific adaptations for HOSE/HNX)

### 6.1 Liquidity Tiers for Vietnamese Market

| Tier | ADTV (B VND) | Approx USD | Example Stocks | Institutional Suitability |
|------|-------------|------------|----------------|--------------------------|
| Mega | > 50 | > $2M | HPG, VCB, TCB, VHM, MBB | Full institutional access |
| High | 20-50 | $0.8-2M | FPT, VNM, ACB, SSI, MWG | Large funds can trade |
| Good | 10-20 | $400K-800K | DPM, REE, PNJ, GMD | Mid-size funds OK |
| Moderate | 5-10 | $200-400K | Various mid-caps | Small funds, careful sizing |
| Low | 2-5 | $80-200K | Smaller mid-caps | Retail-oriented |
| Very Low | 1-2 | $40-80K | Small caps | Retail only, patient entry |
| Illiquid | < 1 | < $40K | Micro-caps, some HNX | Avoid for systematic trading |

### 6.2 HOSE vs HNX Liquidity
- HOSE stocks generally have higher liquidity than HNX equivalents
- HNX stocks in the 91-universe should be evaluated against the same thresholds but flagged as `LIQ_HNX` for awareness
- HNX trading mechanism differences (order matching) may result in slightly different volume patterns

### 6.3 Foreign Room and Liquidity
- Stocks approaching foreign ownership limit (FOL) may have reduced effective liquidity for foreign buyers
- When foreign room < 5% of outstanding shares, flag `LIQ_FOL_CONSTRAINED`
- This does not affect domestic liquidity, but impacts the stock's attractiveness to foreign funds
- Stocks with full foreign ownership (100% FOL reached): foreign buyers can only buy from foreign sellers. Flag `LIQ_FOL_FULL`.

### 6.4 T+2 Settlement Impact
- Vietnam operates T+2.5 (or T+2 depending on broker) settlement cycle
- Intraday buying power may differ from settled cash — this affects some traders' ability to provide liquidity
- On ex-dividend dates, T+2 settlement means the stock needs to be owned 2 business days before record date — can create volume spikes before ex-date

### 6.5 Market Microstructure Notes
- HOSE uses continuous order matching (9:15-14:30) + periodic auction (ATO, ATC)
- Order types: LO (limit order), ATO, ATC, MP (market price — converted to best available)
- No dedicated market makers for most stocks — liquidity is purely order-driven
- Price steps affect effective spread:
  - < 10,000 VND: step = 10 VND → effective minimum spread = 0.1-1.0%
  - 10,000-49,990 VND: step = 50 VND → effective minimum spread = 0.1-0.5%
  - >= 50,000 VND: step = 100 VND → effective minimum spread = 0.1-0.2%
- These price steps create a structural floor on the bid-ask spread

### 6.6 Seasonal Liquidity Patterns
| Period | Typical Liquidity Impact |
|--------|------------------------|
| Pre-Tet (2-3 weeks before) | Drops 30-50%. Flag `LIQ_PRE_TET`. |
| Post-Tet (first week) | Surges 20-50% as traders return. Flag `LIQ_POST_TET`. |
| Summer (Jun-Jul) | Slightly below average. |
| Q4 (Oct-Dec) | Often elevated due to fund rebalancing, tax planning. |
| Derivatives expiry weeks | VN30 stocks may see elevated volume. |

### 6.7 Liquidity Score as Gate for Other Experts
V4LIQ serves as a **gatekeeper** for the entire expert system:
- A stock with V4LIQ = -4 should generate minimal signals from other experts
- The meta-aggregator should weight all other expert scores by a liquidity factor:
  ```
  liquidity_weight = max(0.1, (V4LIQ_score + 4) / 8)
  ```
  This maps: -4 → 0.0 (but floored at 0.1), 0 → 0.5, +4 → 1.0
- This prevents the system from generating strong BUY/SELL signals on stocks that cannot be practically traded

### 6.8 Monitoring Alerts
Generate alerts (separate from scoring) when:
- A previously liquid stock (ADTV > 10B) drops below 5B for 5+ days → `ALERT_LIQ_DEGRADATION`
- A previously illiquid stock suddenly shows 3 consecutive days of ADTV > 10B → `ALERT_LIQ_EMERGENCE`
- Market-wide ADTV drops below 10,000B VND (HOSE total) → `ALERT_MARKET_LIQ_CRISIS`
- These alerts are logged to market.db for review, not included in the -4/+4 scoring
