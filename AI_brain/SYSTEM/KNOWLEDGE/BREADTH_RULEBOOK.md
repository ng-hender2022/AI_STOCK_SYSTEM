# BREADTH_RULEBOOK — AI_STOCK v2
Generated: 2026-03-15
Expert ID: V4BR
Scale: -4 → +4

---

## 1. INDICATORS / METRICS USED (with parameters)

### 1.1 Advance/Decline Metrics
| Metric | Definition | Params |
|--------|-----------|--------|
| **Advance/Decline Ratio (A/D)** | Count of advancing stocks / count of declining stocks across the 91-stock universe | Recalculated daily |
| **A/D Line** | Cumulative sum of (advances - declines) over time | Rolling, no reset |
| **A/D Line SMA** | 10-day and 20-day SMA of the A/D line for trend detection | `sma_short: 10`, `sma_long: 20` |
| **Net Advances** | advances - declines (absolute count) | — |
| **Unchanged Count** | Stocks with 0% change (within 0.1% tolerance) | `unchanged_tolerance: 0.001` |

### 1.2 Moving Average Breadth
| Metric | Definition | Params |
|--------|-----------|--------|
| **% Above SMA50** | Percentage of 91 stocks trading above their 50-day SMA | `sma_period: 50` |
| **% Above SMA200** | Percentage of 91 stocks trading above their 200-day SMA | `sma_period: 200` |
| **% Above SMA20** | Short-term breadth, percentage above 20-day SMA | `sma_period: 20` |
| **SMA50 Breadth Momentum** | 5-day change in % above SMA50 | `momentum_period: 5` |
| **SMA200 Breadth Momentum** | 10-day change in % above SMA200 | `momentum_period: 10` |

### 1.3 New Highs / New Lows
| Metric | Definition | Params |
|--------|-----------|--------|
| **New 52-week Highs** | Count of stocks making 52-week (250 trading day) highs | `lookback: 250` |
| **New 52-week Lows** | Count of stocks making 52-week (250 trading day) lows | `lookback: 250` |
| **New 20-day Highs** | Short-term momentum: count at 20-day highs | `lookback: 20` |
| **New 20-day Lows** | Short-term weakness: count at 20-day lows | `lookback: 20` |
| **High-Low Differential** | new_highs - new_lows | — |
| **High-Low Ratio** | new_highs / (new_highs + new_lows), avoids division by zero | — |

### 1.4 Breadth Thrust Indicators
| Metric | Definition | Params |
|--------|-----------|--------|
| **Breadth Thrust** | 10-day EMA of (advances / (advances + declines)). Thrust signal when rises from <0.40 to >0.615 within 10 days | `ema_period: 10`, `low_threshold: 0.40`, `high_threshold: 0.615` |
| **McClellan Oscillator (adapted)** | 19-day EMA of net advances minus 39-day EMA of net advances | `short_ema: 19`, `long_ema: 39` |
| **McClellan Summation Index** | Cumulative sum of McClellan Oscillator | Rolling |

---

## 2. SCORING RULES (detailed score mapping table)

### 2.1 Primary Score Matrix

| Score | % Above SMA50 | A/D Ratio | Net 52w Highs-Lows | Breadth Momentum (5d chg in %SMA50) |
|-------|---------------|-----------|---------------------|--------------------------------------|
| **+4** | > 80% | > 3.0 | > +15 | > +20pp |
| **+3** | 65% - 80% | 2.0 - 3.0 | +8 to +15 | +10pp to +20pp |
| **+2** | 55% - 65% | 1.5 - 2.0 | +3 to +8 | +5pp to +10pp |
| **+1** | 50% - 55% | 1.1 - 1.5 | +1 to +3 | +2pp to +5pp |
| **0** | 45% - 50% | 0.8 - 1.1 | -1 to +1 | -2pp to +2pp |
| **-1** | 40% - 45% | 0.67 - 0.8 | -3 to -1 | -5pp to -2pp |
| **-2** | 30% - 40% | 0.5 - 0.67 | -8 to -3 | -10pp to -5pp |
| **-3** | 20% - 30% | 0.33 - 0.5 | -15 to -8 | -20pp to -10pp |
| **-4** | < 20% | < 0.33 | < -15 | < -20pp |

### 2.2 Composite Score Calculation
```
raw_score = round(mean(score_sma50, score_ad_ratio, score_hilo, score_momentum))
```
- Each sub-score is independently computed from the table above
- Final score = `clamp(raw_score, -4, +4)`

### 2.3 Divergence Detection (Override Rules)

| Condition | Override |
|-----------|----------|
| VNINDEX at 20-day high BUT % above SMA50 declining for 5+ days | Cap breadth score at +1, emit `BR_NEG_DIVERGENCE` |
| VNINDEX at 20-day low BUT % above SMA50 rising for 5+ days | Floor breadth score at -1, emit `BR_POS_DIVERGENCE` |
| A/D line making new low while VNINDEX holds above prior low | Emit `BR_BULL_DIVERGENCE`, add +1 to score |
| A/D line making new high while VNINDEX fails to make new high | Emit `BR_BEAR_DIVERGENCE`, subtract 1 from score |

### 2.4 Breadth Thrust Override
- If breadth thrust signal fires (see 1.4), set score to **+4** regardless of other metrics. Emit `BR_THRUST`. This is a rare, high-conviction signal.
- Duration: thrust override active for 5 trading days after trigger.

---

## 3. SIGNAL CODES (reference SIGNAL_CODEBOOK)

| Code | Meaning | Typical Score |
|------|---------|---------------|
| `BR_BROAD_ADVANCE` | Strong broad advance, most stocks participating | +3 to +4 |
| `BR_BROAD_DECLINE` | Strong broad decline, selling is widespread | -3 to -4 |
| `BR_HEALTHY_BULL` | Majority above MA50, A/D positive, consistent breadth | +2 to +3 |
| `BR_HEALTHY_BEAR` | Majority below MA50, A/D negative | -2 to -3 |
| `BR_NARROW_ADVANCE` | Index up but breadth narrow (<50% participating) | 0 to +1 |
| `BR_NARROW_DECLINE` | Index down but decline not broad | 0 to -1 |
| `BR_NEG_DIVERGENCE` | Index rising, breadth falling — warning signal | Caps at +1 |
| `BR_POS_DIVERGENCE` | Index falling, breadth improving — bottoming signal | Floor at -1 |
| `BR_BULL_DIVERGENCE` | A/D line diverging bullishly from index | +1 modifier |
| `BR_BEAR_DIVERGENCE` | A/D line diverging bearishly from index | -1 modifier |
| `BR_THRUST` | Breadth thrust fired — rare strong bullish signal | +4 override |
| `BR_WASHOUT` | >85% stocks declining in single session — potential capitulation | Context-dependent |
| `BR_NEUTRAL` | No clear breadth signal | 0 |

---

## 4. SIGNAL QUALITY RULES

### 4.1 Confidence Assessment
| Level | Criteria |
|-------|----------|
| **HIGH** | All 4 sub-scores agree in direction (all positive or all negative), absolute composite >= 3 |
| **MEDIUM** | 3 of 4 sub-scores agree in direction, absolute composite >= 2 |
| **LOW** | Mixed sub-scores, absolute composite <= 1 |
| **DIVERGENCE** | Sub-scores conflict significantly (e.g., SMA50 bullish but momentum bearish) — flag for review |

### 4.2 Temporal Rules
- Breadth scores are computed **end of day** only (no intraday breadth)
- Score is valid for **1 trading day** — recomputed each session
- Breadth thrust signals persist for **5 trading days**
- Divergence signals persist until resolved (breadth confirms index direction)

### 4.3 Universe Integrity
- The 91-stock universe must have at least 85 stocks with valid data on any given day
- If fewer than 85 stocks have data (due to halts, missing data), flag `BR_INCOMPLETE_UNIVERSE` and reduce confidence by one level
- Newly listed stocks: exclude from breadth calculation for first 20 trading days

---

## 5. EDGE CASES

### 5.1 Extreme Readings
- If % above SMA50 > 90%: market is overbought per breadth. Score remains +4 but flag `BR_OVERBOUGHT`. This is NOT a sell signal — it indicates strength but warns of potential mean reversion.
- If % above SMA50 < 10%: market is oversold per breadth. Score remains -4 but flag `BR_OVERSOLD`. Historically, readings below 15% precede bounces within 5-10 days on HOSE.

### 5.2 Index Composition Changes
- When VN30 or VN100 rebalances (twice yearly, January and July), breadth metrics may shift mechanically. Flag `BR_REBALANCE_WINDOW` for 5 trading days after rebalancing.
- If a stock is added/removed from the 91-stock universe, recompute all historical breadth from scratch to maintain consistency.

### 5.3 All Stocks Ceiling/Floor
- Rare event: if >50 of 91 stocks hit ceiling price, A/D ratio is extreme but may not sustain. Flag `BR_MASS_CEILING`. Score = +4 but confidence = MEDIUM (artificial constraint).
- If >50 stocks hit floor price, flag `BR_MASS_FLOOR`. Score = -4 but may indicate capitulation.

### 5.4 Holiday-Adjacent Sessions
- First trading day after Tet/national holiday: breadth may be distorted by pent-up order flow. Flag `BR_POST_HOLIDAY`. Reduce confidence by one level.
- Last trading day before long holiday: typically low volume, breadth less meaningful. Flag `BR_PRE_HOLIDAY`.

### 5.5 Zero Decline Days
- If declines = 0, A/D ratio is undefined. Set A/D sub-score to +4 directly.
- If advances = 0, set A/D sub-score to -4 directly.

---

## 6. VIETNAM MARKET NOTES (specific adaptations for HOSE/HNX)

### 6.1 Universe Definition
- Primary universe: 91 stocks selected for analysis (presumably top liquidity on HOSE/HNX)
- Breadth computed on this fixed universe, not entire exchange
- HOSE has ~400 listed stocks; our 91-stock universe represents the investable core
- Universe should be reviewed quarterly and updated if major liquidity shifts occur

### 6.2 HOSE vs HNX Treatment
- If universe includes both HOSE and HNX stocks, compute separate breadth for each exchange as supplementary data
- HOSE breadth is the primary signal (dominant exchange by market cap and volume)
- HNX breadth may lead or lag HOSE — if HNX breadth deteriorates while HOSE holds, early warning

### 6.3 Foreign Flow and Breadth
- Large foreign net sell days (>500B VND net sell) often coincide with narrow declines concentrated in VN30. Breadth may look better than headline index suggests.
- Large foreign net buy days tend to be concentrated in specific sectors. Breadth may understate the bullish impact.
- Cross-reference with foreign flow data when breadth diverges from index.

### 6.4 Derivatives Market Influence
- VN30 futures expiry (3rd Thursday monthly) can create artificial breadth readings in VN30 components
- On expiry days, compute breadth excluding VN30 stocks as a supplementary check
- If VN30 breadth diverges sharply from non-VN30 breadth on expiry, flag `BR_DERIV_DISTORTION`

### 6.5 Typical Breadth Ranges for HOSE
Based on historical observations:
- Normal bull market: % above SMA50 oscillates between 50-75%
- Strong bull: % above SMA50 sustains above 70%
- Correction: % above SMA50 drops to 30-45%
- Bear market: % above SMA50 sustains below 35%
- Capitulation trough: % above SMA50 drops below 15% (rare, ~2-3x per decade)

### 6.6 Sector Breadth Cross-Reference
- Overall breadth score should be compared with V4S (sector) expert
- If breadth is strong (+3/+4) but driven by only 1-2 sectors, the rally is fragile
- Healthy advances show broad sector participation (at least 5 of 8 major sectors advancing)

### 6.7 Margin Lending Context
- Vietnam market breadth can collapse rapidly when margin calls cascade
- If breadth drops from >60% to <30% within 5 sessions, flag `BR_MARGIN_CASCADE` — this indicates forced selling and potential overshoot
- Post-margin-cascade, breadth typically recovers within 5-10 sessions as forced selling exhausts
