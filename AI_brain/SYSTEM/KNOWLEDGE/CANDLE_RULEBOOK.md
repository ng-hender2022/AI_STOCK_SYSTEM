# CANDLE_RULEBOOK — AI_STOCK v2
Generated: 2026-03-15
Expert ID: V4CANDLE
Scale: -4 → +4

---

## 1. INDICATORS / METRICS USED (with parameters)

### 1.1 Single Candle Patterns
| Pattern | Detection Logic | Params |
|---------|----------------|--------|
| **Hammer** | Lower shadow >= 2x real body, upper shadow <= 10% of range, appears after decline (min 3 candles down) | `body_ratio: 0.33`, `shadow_ratio: 2.0` |
| **Inverted Hammer** | Upper shadow >= 2x real body, lower shadow <= 10% of range, appears after decline | `body_ratio: 0.33`, `shadow_ratio: 2.0` |
| **Shooting Star** | Upper shadow >= 2x real body, lower shadow <= 10% of range, appears after advance (min 3 candles up) | `body_ratio: 0.33`, `shadow_ratio: 2.0` |
| **Hanging Man** | Same shape as hammer but appears after advance | `body_ratio: 0.33`, `shadow_ratio: 2.0` |
| **Doji** | Open == Close (tolerance <= 0.1% of range), classified as: Standard, Long-legged, Dragonfly, Gravestone | `body_tolerance: 0.001` |
| **Marubozu** | No shadows (tolerance <= 2% of range), strong conviction candle | `shadow_tolerance: 0.02` |
| **Spinning Top** | Small real body (< 25% of range), moderate shadows both sides | `body_max: 0.25` |

### 1.2 Double Candle Patterns
| Pattern | Detection Logic | Params |
|---------|----------------|--------|
| **Bullish Engulfing** | Day2 body fully contains Day1 body, Day1 bearish + Day2 bullish, Day2 close > Day1 open | `min_engulf: 1.0` |
| **Bearish Engulfing** | Day2 body fully contains Day1 body, Day1 bullish + Day2 bearish, Day2 close < Day1 open | `min_engulf: 1.0` |
| **Bullish Harami** | Day2 body contained within Day1 body, Day1 bearish + Day2 bullish | — |
| **Bearish Harami** | Day2 body contained within Day1 body, Day1 bullish + Day2 bearish | — |
| **Piercing Line** | Day1 bearish, Day2 opens below Day1 low, Day2 closes above 50% of Day1 body | `pierce_pct: 0.50` |
| **Dark Cloud Cover** | Day1 bullish, Day2 opens above Day1 high, Day2 closes below 50% of Day1 body | `pierce_pct: 0.50` |
| **Tweezer Top** | Two candles with matching highs (tolerance 0.3%), appears after advance | `match_tolerance: 0.003` |
| **Tweezer Bottom** | Two candles with matching lows (tolerance 0.3%), appears after decline | `match_tolerance: 0.003` |

### 1.3 Triple Candle Patterns
| Pattern | Detection Logic | Params |
|---------|----------------|--------|
| **Morning Star** | Day1 large bearish, Day2 small body (gap down preferred), Day3 large bullish closing above Day1 midpoint | `small_body: 0.30`, `min_close_pct: 0.50` |
| **Evening Star** | Day1 large bullish, Day2 small body (gap up preferred), Day3 large bearish closing below Day1 midpoint | `small_body: 0.30`, `min_close_pct: 0.50` |
| **Three White Soldiers** | Three consecutive bullish candles, each opens within prior body, each closes near its high, progressively higher | `close_near_high: 0.70` |
| **Three Black Crows** | Three consecutive bearish candles, each opens within prior body, each closes near its low, progressively lower | `close_near_low: 0.70` |
| **Three Inside Up** | Bullish harami + Day3 closes above Day1 high (harami confirmation) | — |
| **Three Inside Down** | Bearish harami + Day3 closes below Day1 low (harami confirmation) | — |

### 1.4 Context Indicators
| Indicator | Purpose | Params |
|-----------|---------|--------|
| **Prior Trend** | Determines if pattern is reversal-eligible. Min 3-5 candles trending. | `trend_lookback: 5` |
| **Support/Resistance Zone** | Pattern at S/R multiplies reliability. Uses pivot points + 20-day high/low. | `sr_proximity: 0.015` (1.5%) |
| **Volume Ratio** | Pattern-day volume vs 20-day avg volume. Confirmation requires >= 1.3x. | `vol_confirm: 1.3`, `vol_period: 20` |
| **Body Size Percentile** | Compare real body size to 20-day body size distribution. Large body = top 25%. | `large_pctile: 0.75` |

---

## 2. SCORING RULES (detailed score mapping table)

### 2.1 Base Pattern Scores

| Score | Bullish Patterns | Bearish Patterns |
|-------|-----------------|-----------------|
| **+1 / -1** | Spinning top at support, single doji | Spinning top at resistance, single doji |
| **+2 / -2** | Hammer (no vol confirm), bullish harami, inverted hammer | Shooting star (no vol confirm), bearish harami, hanging man |
| **+3 / -3** | Bullish engulfing, piercing line, morning star (no vol confirm), three inside up | Bearish engulfing, dark cloud cover, evening star (no vol confirm), three inside down |
| **+4 / -4** | Morning star + vol confirm + at support, three white soldiers + vol confirm | Evening star + vol confirm + at resistance, three black crows + vol confirm |

### 2.2 Score Modifiers

| Condition | Modifier | Notes |
|-----------|----------|-------|
| Volume >= 1.3x average | +1 (cap at +/-4) | Confirms institutional participation |
| Volume >= 2.0x average | +1 additional | Exceptional conviction |
| Pattern at support/resistance zone | +1 (cap at +/-4) | Within 1.5% of identified S/R level |
| Pattern in direction of prior trend (continuation) | -1 | Continuation patterns less significant than reversals |
| Gap present in multi-candle pattern | +1 | Gaps add conviction (morning/evening star) |
| Doji after extreme move (>5% in 3 days) | +1 | Exhaustion signal |

### 2.3 Score Combination Rules
- If multiple patterns detected on same day, take the **highest absolute score**
- If conflicting patterns exist (bullish + bearish), score = 0 with signal code `CANDLE_CONFLICT`
- Maximum final score after all modifiers: +4 or -4 (hard cap)

---

## 3. SIGNAL CODES (reference SIGNAL_CODEBOOK)

| Code | Meaning | Typical Score Range |
|------|---------|-------------------|
| `CANDLE_BULL_REVERSAL` | Bullish reversal pattern detected after downtrend | +2 to +4 |
| `CANDLE_BEAR_REVERSAL` | Bearish reversal pattern detected after uptrend | -2 to -4 |
| `CANDLE_BULL_CONTINUATION` | Bullish pattern in uptrend (continuation) | +1 to +2 |
| `CANDLE_BEAR_CONTINUATION` | Bearish pattern in downtrend (continuation) | -1 to -2 |
| `CANDLE_DOJI_INDECISION` | Doji without clear directional bias | 0 |
| `CANDLE_DOJI_EXHAUSTION` | Doji after extended move, potential reversal | +1 to +2 / -1 to -2 |
| `CANDLE_ENGULF_BULL` | Bullish engulfing specifically | +3 |
| `CANDLE_ENGULF_BEAR` | Bearish engulfing specifically | -3 |
| `CANDLE_MSTAR` | Morning star pattern | +3 to +4 |
| `CANDLE_ESTAR` | Evening star pattern | -3 to -4 |
| `CANDLE_3SOLDIERS` | Three white soldiers | +3 to +4 |
| `CANDLE_3CROWS` | Three black crows | -3 to -4 |
| `CANDLE_CONFLICT` | Conflicting patterns detected | 0 |
| `CANDLE_NONE` | No recognizable pattern | 0 |

---

## 4. SIGNAL QUALITY RULES

### 4.1 Confidence Levels
| Level | Criteria | Action |
|-------|----------|--------|
| **HIGH** | Pattern score +/-3 or +/-4, volume confirmed, at S/R, clear prior trend | Emit signal, weight = 1.0 |
| **MEDIUM** | Pattern score +/-2, partial confirmation (volume OR S/R) | Emit signal, weight = 0.7 |
| **LOW** | Pattern score +/-1, no confirmation | Emit signal, weight = 0.4 |
| **REJECT** | Pattern in sideways chop (ADX < 15 over 14 periods), conflicting signals | Do not emit, log only |

### 4.2 Staleness Rules
- Pattern signal valid for **2 trading days** after detection
- If price moves >3% against the pattern direction within 2 days, invalidate immediately
- After 2 days, signal decays: score = `original_score * 0.5` (rounded toward zero)

### 4.3 Minimum Data Requirements
- Single candle patterns: minimum 10 trading days of history
- Double candle patterns: minimum 15 trading days of history
- Triple candle patterns: minimum 20 trading days of history
- If data insufficient, output score = 0 with code `CANDLE_NONE` and quality flag `INSUFFICIENT_DATA`

---

## 5. EDGE CASES

### 5.1 Ceiling/Floor Price Hits (Vietnam-specific)
- **Ceiling price (tran)**: If candle high == ceiling price, upper shadow is artificial. Do NOT count as shooting star or gravestone doji. Flag: `CEILING_HIT`.
- **Floor price (san)**: If candle low == floor price, lower shadow is artificial. Do NOT count as hammer or dragonfly doji. Flag: `FLOOR_HIT`.
- When ceiling/floor is hit, reduce pattern confidence by one level.

### 5.2 T+ Settlement Effects
- Monday patterns may reflect T+2 settlement from prior Thursday/Friday. Weight Monday patterns at 0.8x.
- Patterns forming on the last day before a holiday break: reduce confidence (gap risk). Weight at 0.7x.

### 5.3 ATC/ATO Session Distortions
- ATC (closing auction) can create artificial shadows in last 15 minutes. If >50% of the candle range occurs in ATC, flag `ATC_DISTORTION` and reduce score by 1.
- ATO (opening auction) gaps are less reliable on HOSE due to auction mechanics. Flag `ATO_GAP` on gaps > 2%.

### 5.4 Low Liquidity Candles
- If daily traded value < 1 billion VND, all candle patterns receive maximum score of +/-1 regardless of pattern type. Flag: `LOW_LIQ_CANDLE`.
- If volume < 30% of 20-day average, treat as unreliable. Flag: `THIN_VOLUME`.

### 5.5 Stock-Specific Price Tick Issues
- Stocks priced < 10,000 VND: tick size = 10 VND. Body/shadow ratios may be distorted by tick granularity. Use wider tolerance for doji (`body_tolerance: 0.005`).
- Stocks priced 10,000-49,990 VND: tick size = 50 VND.
- Stocks priced >= 50,000 VND: tick size = 100 VND.

### 5.6 Missing Data / Halted Stocks
- If stock was halted (no trading), skip pattern detection. Output score = 0, code `CANDLE_NONE`, flag `HALTED`.
- If OHLC data has anomalies (O > H, L > C, etc.), reject data point and flag `BAD_OHLC`.

---

## 6. VIETNAM MARKET NOTES (specific adaptations for HOSE/HNX)

### 6.1 Price Limit Band
- HOSE: +/-7% daily limit. Patterns near ceiling/floor are constrained.
- HNX: +/-10% daily limit. Slightly more room for pattern formation.
- UPCoM: +/-15% daily limit.
- **Implication**: A marubozu hitting ceiling is NOT the same conviction as a free-range marubozu. Discount ceiling/floor marubozu by 1 point.

### 6.2 Trading Sessions
- HOSE continuous: 9:15 - 14:30, ATC: 14:30 - 14:45.
- HNX continuous: 9:00 - 14:30, ATC: 14:30 - 14:45.
- Intraday candle patterns (if used) should exclude ATC spike from shadow calculation.

### 6.3 VN30 vs Small-cap Interpretation
- VN30 stocks: standard candle rules apply, high liquidity ensures pattern reliability.
- Mid-cap (VN70): apply 0.9x confidence multiplier.
- Small-cap (outside VN100): apply 0.7x confidence multiplier due to manipulation risk.
- Penny stocks (< 5,000 VND): do not generate candle signals. Output `CANDLE_NONE` with flag `PENNY_STOCK`.

### 6.4 Foreign Ownership Impact
- Stocks near foreign ownership limit (FOL): buying patterns may be constrained. If FOL > 45%, flag `NEAR_FOL` and note that bullish patterns may have limited follow-through from foreign buyers.

### 6.5 Seasonal Considerations
- Tet holiday period (typically late Jan/early Feb): thin trading 1-2 weeks before. Reduce all pattern scores by 1 during this window.
- Derivatives expiry (3rd Thursday of each month): VN30 stocks may show artificial candle patterns from arbitrage. Flag `DERIV_EXPIRY`.

### 6.6 Cross-Reference Requirements
- Candle signals should be cross-referenced with V4LIQ (liquidity) expert. If V4LIQ score <= -3, reduce candle score magnitude by 1.
- Candle signals at +/-4 should align with V4REG (regime). A +4 candle in STRONG_BEAR regime gets capped at +2.
