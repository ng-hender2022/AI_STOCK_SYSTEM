# PRICE ACTION RULEBOOK — AI_STOCK v2
Generated: 2026-03-15
Expert ID: V4P
Scale: -4 → +4

---

## 1. INDICATORS USED (with parameters)

| Indicator | Parameter | Description |
|-----------|-----------|-------------|
| **Close** | Current | Current session closing price |
| **High** | Current | Session high |
| **Low** | Current | Session low |
| **High20** | Highest High in 20 sessions | 20-day resistance reference |
| **Low20** | Lowest Low in 20 sessions | 20-day support reference |
| **High52W** | Highest High in 260 sessions | 52-week resistance reference |
| **Low52W** | Lowest Low in 260 sessions | 52-week support reference |
| **Swing_Highs** | Local maxima (high > high of 2 bars before and after) | Swing high detection over 5-bar window |
| **Swing_Lows** | Local minima (low < low of 2 bars before and after) | Swing low detection over 5-bar window |
| **HH_HL_Count** | Count of consecutive higher highs/higher lows in swing points | Uptrend strength measurement |
| **LH_LL_Count** | Count of consecutive lower highs/lower lows in swing points | Downtrend strength measurement |
| **Price_SMA20** | SMA(Close, 20) | 20-day moving average — dynamic support/resistance and trend filter |
| **Price_Slope20** | (Close - Close[19]) / Close[19] * 100 | 20-day price rate of change (%) |

### Derived Metrics

- **Trend_Structure**: Classification based on swing point sequence:
  - `UPTREND`: Last 2+ swing highs are HH AND last 2+ swing lows are HL
  - `DOWNTREND`: Last 2+ swing highs are LH AND last 2+ swing lows are LL
  - `CONSOLIDATION`: Mixed swing pattern (HH with LL, or LH with HL)
  - `TRANSITION_UP`: First HH after downtrend (LH/LL sequence broken)
  - `TRANSITION_DOWN`: First LH after uptrend (HH/HL sequence broken)

- **Distance_to_Resistance** = (High20 - Close) / Close * 100 — how far price is from 20-day resistance
- **Distance_to_Support** = (Close - Low20) / Close * 100 — how far price is from 20-day support
- **Range_Position** = (Close - Low20) / (High20 - Low20) — price position within 20-day range (0.0 to 1.0)
- **Breakout_Strength** = (Close - High20[yesterday]) / High20[yesterday] * 100 — magnitude of breakout above resistance
- **Breakdown_Strength** = (Low20[yesterday] - Close) / Low20[yesterday] * 100 — magnitude of breakdown below support

---

## 2. SCORING RULES (detailed score mapping table)

### Primary Scoring Matrix

| Score | Trend_Structure | Range_Position | Breakout/Breakdown Status | Description |
|-------|----------------|----------------|---------------------------|-------------|
| **+4** | UPTREND (HH_HL >= 3) | > 0.95 | Close > High20 by >= 1.0% | Strong uptrend with confirmed breakout of 20-day resistance |
| **+3** | UPTREND (HH_HL >= 2) | > 0.85 | Close near/at High20 | Established uptrend, price testing or at resistance |
| **+2** | UPTREND (HH_HL >= 1) or TRANSITION_UP | > 0.65 | No breakout | Developing uptrend, price in upper zone |
| **+1** | Any (with bullish lean) | 0.50 – 0.65 | No breakout | Price above midpoint, mild bullish bias |
| **0** | CONSOLIDATION | 0.35 – 0.65 | No breakout/breakdown | Ranging market, no directional bias |
| **-1** | Any (with bearish lean) | 0.35 – 0.50 | No breakdown | Price below midpoint, mild bearish bias |
| **-2** | DOWNTREND (LH_LL >= 1) or TRANSITION_DOWN | < 0.35 | No breakdown | Developing downtrend, price in lower zone |
| **-3** | DOWNTREND (LH_LL >= 2) | < 0.15 | Close near/at Low20 | Established downtrend, price testing or at support |
| **-4** | DOWNTREND (LH_LL >= 3) | < 0.05 | Close < Low20 by >= 1.0% | Strong downtrend with confirmed breakdown of 20-day support |

### Support/Resistance Rules (20-day lookback)

| Rule ID | Pattern | Condition | Score Effect |
|---------|---------|-----------|--------------|
| **SR-1** | **Resistance Breakout** | Close > High20 AND Close > PrevHigh20 by >= 0.5% | Score = max(score, +3); if clean break by >= 1.5%, score = +4 |
| **SR-2** | **Support Breakdown** | Close < Low20 AND Close < PrevLow20 by >= 0.5% | Score = min(score, -3); if clean break by >= 1.5%, score = -4 |
| **SR-3** | **Resistance Rejection** | High touches/exceeds High20 but Close < High20 by >= 0.5% | Score = min(score, 0), flag `RESISTANCE_REJECTION` |
| **SR-4** | **Support Bounce** | Low touches/undercuts Low20 but Close > Low20 by >= 0.5% | Score = max(score, 0), flag `SUPPORT_BOUNCE` |
| **SR-5** | **Resistance Turned Support** | Previous High20 broken upward, price pulls back to it and holds | Score = max(score, +2), flag `RES_TO_SUPPORT` |
| **SR-6** | **Support Turned Resistance** | Previous Low20 broken downward, price rallies to it and rejected | Score = min(score, -2), flag `SUP_TO_RESISTANCE` |
| **SR-7** | **52-Week Breakout** | Close > High52W | Score = +4, flag `52W_BREAKOUT` |
| **SR-8** | **52-Week Breakdown** | Close < Low52W | Score = -4, flag `52W_BREAKDOWN` |

### Trend Transition Rules

| Transition | Condition | Score | Signal |
|------------|-----------|-------|--------|
| **Downtrend to Uptrend** | First HH after 2+ LH sequence AND first HL after 2+ LL sequence | +2 | `TREND_REVERSAL_UP` |
| **Uptrend to Downtrend** | First LH after 2+ HH sequence AND first LL after 2+ HL sequence | -2 | `TREND_REVERSAL_DOWN` |
| **Trend Acceleration (Up)** | HH_HL count increases from 2 to 3+ AND slope steepening | Add +1 (cap at +4) | `TREND_ACCEL_UP` |
| **Trend Acceleration (Down)** | LH_LL count increases from 2 to 3+ AND slope steepening | Add -1 (cap at -4) | `TREND_ACCEL_DOWN` |
| **Trend Deceleration (Up)** | Uptrend but latest HH is only marginally higher (< 0.5%) | Reduce score by 1 | `TREND_DECEL_UP` |
| **Trend Deceleration (Down)** | Downtrend but latest LL is only marginally lower (< 0.5%) | Increase score by 1 | `TREND_DECEL_DOWN` |

### Breakout Confirmation Rules

| Rule ID | Condition | Confirmed? | Score |
|---------|-----------|------------|-------|
| **BK-P1** | Close > High20 AND volume V_Ratio > 1.5 AND next session close >= breakout close | YES — confirmed breakout | +4 |
| **BK-P2** | Close > High20 AND volume V_Ratio > 1.5 BUT next session closes back below High20 | NO — failed breakout | Revert to 0, flag `BREAKOUT_FAILED` |
| **BK-P3** | Close > High20 AND volume V_Ratio < 1.0 | SUSPECT — low conviction | Score capped at +2, flag `BREAKOUT_LOW_VOLUME` |
| **BK-P4** | Close < Low20 AND volume V_Ratio > 1.5 AND next session close <= breakdown close | YES — confirmed breakdown | -4 |
| **BK-P5** | Close < Low20 AND volume V_Ratio > 1.5 BUT next session closes back above Low20 | NO — failed breakdown | Revert to 0, flag `BREAKDOWN_FAILED` |
| **BK-P6** | Close < Low20 AND volume V_Ratio < 1.0 | SUSPECT — low conviction | Score capped at -2, flag `BREAKDOWN_LOW_VOLUME` |

### Price vs SMA20 Rules

| Condition | Score Modifier |
|-----------|---------------|
| Close > SMA20 AND SMA20 slope positive | Bullish confirmation — no modifier (already captured in trend structure) |
| Close < SMA20 AND SMA20 slope negative | Bearish confirmation — no modifier |
| Close crosses above SMA20 (from below) | Score += +1 (cap at +4), flag `SMA20_CROSS_UP` |
| Close crosses below SMA20 (from above) | Score -= 1 (cap at -4), flag `SMA20_CROSS_DOWN` |
| Close whipsaws around SMA20 (3+ crosses in 10 days) | Score clamped to [-1, +1], flag `SMA20_WHIPSAW` |

---

## 3. SIGNAL CODES (reference SIGNAL_CODEBOOK)

| Code | Name | Trigger |
|------|------|---------|
| `PA_STRONG_UPTREND` | Strong Uptrend | Score = +4 |
| `PA_UPTREND` | Uptrend | Score = +2 or +3 |
| `PA_MILD_BULL` | Mild Bullish | Score = +1 |
| `PA_NEUTRAL` | Neutral / Consolidation | Score = 0 |
| `PA_MILD_BEAR` | Mild Bearish | Score = -1 |
| `PA_DOWNTREND` | Downtrend | Score = -2 or -3 |
| `PA_STRONG_DOWNTREND` | Strong Downtrend | Score = -4 |
| `PA_BREAKOUT` | Resistance Breakout | Close > High20 (confirmed) |
| `PA_BREAKDOWN` | Support Breakdown | Close < Low20 (confirmed) |
| `PA_BREAKOUT_FAILED` | Failed Breakout | Breakout reversed within 2 sessions |
| `PA_BREAKDOWN_FAILED` | Failed Breakdown | Breakdown reversed within 2 sessions |
| `PA_BREAKOUT_LOW_VOL` | Low-Volume Breakout | Breakout with V_Ratio < 1.0 |
| `PA_BREAKDOWN_LOW_VOL` | Low-Volume Breakdown | Breakdown with V_Ratio < 1.0 |
| `PA_RESISTANCE_REJECT` | Resistance Rejection | Price rejected at High20 |
| `PA_SUPPORT_BOUNCE` | Support Bounce | Price bounced at Low20 |
| `PA_RES_TO_SUPPORT` | Resistance Turned Support | Previous resistance now acts as support |
| `PA_SUP_TO_RESISTANCE` | Support Turned Resistance | Previous support now acts as resistance |
| `PA_52W_BREAKOUT` | 52-Week Breakout | Close > 52-week high |
| `PA_52W_BREAKDOWN` | 52-Week Breakdown | Close < 52-week low |
| `PA_TREND_REVERSAL_UP` | Trend Reversal Up | Downtrend structure broken, uptrend beginning |
| `PA_TREND_REVERSAL_DOWN` | Trend Reversal Down | Uptrend structure broken, downtrend beginning |
| `PA_TREND_ACCEL_UP` | Trend Acceleration Up | Uptrend steepening |
| `PA_TREND_ACCEL_DOWN` | Trend Acceleration Down | Downtrend steepening |
| `PA_TREND_DECEL_UP` | Trend Deceleration Up | Uptrend losing momentum |
| `PA_TREND_DECEL_DOWN` | Trend Deceleration Down | Downtrend losing momentum |
| `PA_SMA20_CROSS_UP` | SMA20 Cross Up | Price crosses above SMA20 |
| `PA_SMA20_CROSS_DOWN` | SMA20 Cross Down | Price crosses below SMA20 |
| `PA_SMA20_WHIPSAW` | SMA20 Whipsaw | Multiple SMA20 crosses in short period |
| `PA_INSIDE_BAR` | Inside Bar | Today's range within yesterday's range |
| `PA_OUTSIDE_BAR` | Outside Bar | Today's range engulfs yesterday's range |

---

## 4. SIGNAL QUALITY RULES

### Quality Tiers

| Quality | Condition | Confidence |
|---------|-----------|------------|
| **A (High)** | 52-week breakout/breakdown OR trend with 3+ HH/HL or LH/LL AND confirmed breakout with volume OR trend reversal confirmed by multiple sessions | 80-95% |
| **B (Medium)** | Established trend (2+ swing confirmations) OR confirmed S/R breakout with moderate volume OR resistance-turned-support / support-turned-resistance confirmed | 55-79% |
| **C (Low)** | Early trend (1 swing confirmation) OR price near but not breaking S/R OR SMA20 cross without trend structure | 35-54% |
| **D (Noise)** | Consolidation with no clear structure OR SMA20 whipsaw OR failed breakout/breakdown OR insufficient swing points | < 35% |

### Quality Modifiers

1. **Volume Confirmation Bonus**: If breakout/breakdown occurs with V_Ratio > 2.0, upgrade quality by one tier.
2. **Multi-Timeframe Alignment**: If weekly price action trend matches daily signal, upgrade by one tier.
3. **Swing Point Clarity**: If swing highs/lows are clearly defined (> 1% difference between swing point and surrounding bars), upgrade by one tier.
4. **Failed Signal Penalty**: If the stock has produced 2+ failed breakouts or breakdowns in the last 20 sessions, downgrade all breakout/breakdown signals by one tier.
5. **Consolidation Duration Bonus**: If consolidation (score = 0) has persisted for 15+ sessions, the eventual breakout/breakdown quality is upgraded by one tier.
6. **Gap Penalty**: If breakout/breakdown occurs via gap (open already beyond S/R), the gap may fill — downgrade by one tier unless gap is > 3%.

### Minimum Quality for Action

- 52-week breakout/breakdown: actionable at any quality.
- Score magnitude >= 3: requires Quality B or better.
- Score magnitude 2: requires Quality A.
- Score magnitude <= 1: informational only.

---

## 5. EDGE CASES

| Edge Case | Handling |
|-----------|----------|
| **First 20 sessions** | High20 / Low20 / SMA20 use available data; swing points may be insufficient. If < 10 sessions, score = 0, flag `INSUFFICIENT_PA_HISTORY` |
| **Trading halt** | Skip halted days — do not count as sessions for swing point detection or S/R calculation. Flag `HALTED` |
| **Ceiling price lock (CE)** | Price at ceiling is NOT a natural resistance rejection — it is excess demand. Do not generate `RESISTANCE_REJECTION` signal. If at ceiling and High20, flag `CE_AT_RESISTANCE` — interpret as bullish (demand exceeds supply at high). Score = max(score, +3) |
| **Floor price lock (FL)** | Price at floor is NOT a natural support bounce — it is excess supply. Do not generate `SUPPORT_BOUNCE` signal. If at floor and Low20, flag `FL_AT_SUPPORT` — interpret as bearish. Score = min(score, -3) |
| **Stock split / Reverse split** | Use adjusted prices for all calculations. First 5 sessions post-split may have abnormal swing patterns — flag `SPLIT_ADJUSTED` |
| **Ex-dividend gap** | Price drops mechanically on ex-date. Do NOT count as breakdown or new LL. Adjust High20/Low20 by dividend amount on ex-date. Flag `EX_DIVIDEND_PA` |
| **Rights issue** | Similar to dividend — adjust reference prices. Flag `CORPORATE_ACTION` |
| **Thin trading (< 5 matched trades)** | Price action is noise — score = 0, flag `THIN_TRADING` |
| **Unchanged close for 5+ sessions** | No price action — score = 0, flag `PRICE_FROZEN` (common in illiquid UPCOM stocks) |
| **Gap-up or gap-down open** | If gap > 3% of previous close, flag `GAP_UP` or `GAP_DOWN`. Gaps may act as future S/R levels — add gap level to S/R tracking |
| **Inside bar** | Today's entire range is within yesterday's range — flag `INSIDE_BAR`, score unchanged but marks potential compression before move |
| **Outside bar / Engulfing** | Today's range fully engulfs yesterday's range — flag `OUTSIDE_BAR`, may signal reversal. If bullish engulfing (close near high after downtrend), score += +1. If bearish engulfing (close near low after uptrend), score -= 1 |

---

## 6. VIETNAM MARKET NOTES

### Price Action Specifics for Vietnamese Market

1. **Daily Price Limits and Trend Structure**:
   - HOSE +/-7%, HNX +/-10%, UPCOM +/-15%.
   - When a stock trends strongly, it can hit the ceiling/floor for multiple consecutive sessions. This creates artificially "flat" price bars that are NOT consolidation — they are constrained trends.
   - **Ceiling Lock Trend**: 3+ consecutive CE days = very strong uptrend. Score = +4 regardless of swing structure. Flag `CE_STREAK`.
   - **Floor Lock Trend**: 3+ consecutive FL days = very strong downtrend. Score = -4 regardless of swing structure. Flag `FL_STREAK`.
   - During ceiling/floor locks, traditional HH/HL or LH/LL analysis is unreliable because the price is capped.

2. **T+2 Settlement and Price Behavior**:
   - Stocks bought on day T can only be sold on T+2 (after matching). This creates a natural 2-day holding period that affects short-term price patterns.
   - Expect more 2-3 day momentum patterns (short-term traders who bought on dips sell T+2 into strength).
   - Pullbacks after breakouts often occur on T+2 or T+3 — do not immediately call `BREAKOUT_FAILED` until T+3 confirms.

3. **Session Structure and Key Price Levels**:
   - **ATO (09:00-09:15)**: Opening auction — can set key support/resistance for the day. First 15-min high/low is a significant intraday S/R level.
   - **ATC (14:30-14:45)**: Closing auction — closing price is the official price used for settlement, margin calculations, NAV. ATC price is the most important for daily price action analysis.
   - **Reference Price**: The previous session's closing price is the reference price around which bands are calculated. This is the psychological anchor for each session.

4. **Gap Behavior in Vietnam**:
   - Overnight gaps are common after significant news (earnings, regulatory changes).
   - Post-Tet gap: The first session after Tet holiday almost always gaps (up or down) due to accumulated global news during the break. This gap has significant predictive value for the subsequent 5-10 sessions.
   - Earnings gaps: Vietnamese companies report quarterly earnings. Gap-ups/downs on earnings tend to continue in the same direction for 2-3 sessions (unlike some mature markets where gaps often fill quickly).

5. **Support/Resistance at Round Numbers**:
   - Vietnamese retail investors are highly sensitive to round price numbers (10,000, 20,000, 50,000, 100,000 VND).
   - These round numbers act as strong psychological S/R levels — add them to the S/R map with a `ROUND_NUMBER_SR` flag.
   - The VN-Index itself has major round-number levels (1,000, 1,100, 1,200, 1,300 points) that affect market-wide sentiment.

6. **Foreign Investor Footprint**:
   - Foreign investors tend to buy/sell at specific price levels (often near technical S/R). When foreign net buy volume is concentrated at a price level, that level becomes stronger support.
   - If a breakout above High20 is accompanied by positive foreign net buying, the breakout is significantly more reliable. Flag `FOREIGN_CONFIRMED_BREAKOUT`.

7. **Sector Leader / Laggard Dynamics**:
   - In Vietnamese market rallies, VN30 sector leaders (VCB, FPT, VHM, HPG, MWG) tend to break out first.
   - Price action breakouts in sector leaders that are NOT followed by sector laggards within 3-5 sessions often fail — the sector needs breadth confirmation.
   - Flag `SECTOR_LEADER_BREAKOUT` when a top-3 stock in its sector breaks out.

8. **Tet and Holiday Patterns**:
   - **Pre-Tet (5 sessions)**: Price action tends toward consolidation as liquidity dries up. Score bias toward 0.
   - **Post-Tet (first session)**: Gap is almost certain — use gap direction as the primary signal. Score based on gap direction and magnitude.
   - **Post-Tet (sessions 2-5)**: Trend established by the post-Tet gap typically persists. Give trend signals higher quality during this window.
   - **September 2 (National Day)**: 1-2 day break — smaller gap effect.
   - **April 30 / May 1 (Reunification Day / Labor Day)**: 2-4 day break — moderate gap effect.

9. **Margin and Forced Selling Patterns**:
   - When HOSE/HNX tighten margin requirements, forced selling creates sharp breakdowns that may not reflect fundamentals.
   - Breakdowns during margin call cascades often produce V-shaped recoveries within 5-10 sessions.
   - Flag `MARGIN_CALL_CASCADE` when market drops > 3% and multiple stocks break support simultaneously.
   - Do NOT assign full -4 score weight to breakdowns during margin cascades — use -3 max with quality downgrade.

10. **Price Action and the KRX System**:
    - Post-KRX, the introduction of stop orders and other advanced order types may change breakout dynamics — breakouts may be faster and more decisive as stop orders trigger.
    - Monitor for structural changes in failed breakout rates post-KRX.

### Support/Resistance Identification Method for Vietnam

Use the following hierarchy for S/R level importance:

| Priority | S/R Type | Lookback | Weight |
|----------|----------|----------|--------|
| 1 | 52-week high/low | 260 sessions | Highest |
| 2 | Round number (10k, 20k, 50k, 100k VND) | N/A | Very High |
| 3 | 20-day high/low | 20 sessions | High |
| 4 | Previous ceiling/floor lock price | Variable | High |
| 5 | Gap levels (unfilled gaps) | 60 sessions | Medium |
| 6 | High-volume price levels (volume profile) | 20 sessions | Medium |
| 7 | SMA20 | Dynamic | Low-Medium |
| 8 | Previous swing highs/lows | 40 sessions | Low |

When multiple S/R levels cluster within 1% of each other, this creates a **confluence zone** — these zones are significantly stronger than individual levels. Flag `SR_CONFLUENCE` when 3+ levels cluster.
