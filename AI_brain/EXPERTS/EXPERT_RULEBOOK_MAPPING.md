# EXPERT → RULEBOOK MAPPING

Version: 1.0
Date: 2026-03-16
Status: ACTIVE

---

## CORE 20 EXPERTS

| Expert ID | Name | Scale | Rulebooks (KNOWLEDGE/) | Build Status |
|---|---|---|---|---|
| V4I | Ichimoku Expert | -4..+4 | `ICHIMOKU_RULEBOOK_FOR_AI.md`, `ICHIMOKU_FEATURE_MAP.md` | BUILT |
| V4MA | Moving Average Expert | -4..+4 | *(rules in config.yaml)* | BUILT |
| V4ADX | Trend Strength Expert | 0..4 | `ADX_RULEBOOK.md` | RULEBOOK READY |
| V4MACD | MACD Expert | -4..+4 | `MACD_RULEBOOK.md` | RULEBOOK READY |
| V4RSI | RSI Expert | 0..100 | `RSI_RULEBOOK.md` | RULEBOOK READY |
| V4STO | Stochastic Expert | 0..100 | `STOCHASTIC_RULEBOOK.md` | RULEBOOK READY |
| V4V | Volume Behavior Expert | -4..+4 | `VOLUME_RULEBOOK.md` | RULEBOOK READY |
| V4OBV | OBV Expert | -4..+4 | `OBV_RULEBOOK.md` | RULEBOOK READY |
| V4ATR | ATR Volatility Expert | 0..4 | `ATR_RULEBOOK.md` | RULEBOOK READY |
| V4BB | Bollinger Bands Expert | -4..+4 | `BOLLINGER_RULEBOOK.md` | RULEBOOK READY |
| V4P | Price Action Expert | -4..+4 | `PRICE_ACTION_RULEBOOK.md` | RULEBOOK READY |
| V4CANDLE | Candlestick Expert | -4..+4 | `CANDLE_RULEBOOK.md` | RULEBOOK READY |
| V4BR | Breadth Expert | -4..+4 | `BREADTH_RULEBOOK.md` | RULEBOOK READY |
| V4RS | Relative Strength Expert | -4..+4 | `RS_RULEBOOK.md` | RULEBOOK READY |
| V4REG | Market Regime Expert | -4..+4 | `REGIME_RULEBOOK.md` | BUILT |
| V4S | Sector Strength Expert | -4..+4 | `SECTOR_RULEBOOK.md` | RULEBOOK READY |
| V4LIQ | Liquidity Expert | -4..+4 | `LIQUIDITY_RULEBOOK.md` | RULEBOOK READY |
| V4PIVOT | Pivot Point Expert | -4..+4 | `V4PIVOT_RULEBOOK.md` | RULEBOOK READY |
| V4SR | Support/Resistance Expert | -4..+4 | `V4SR_RULEBOOK.md` | RULEBOOK READY |
| V4TREND_PATTERN | Trend Pattern Expert | -4..+4 | `V4TREND_PATTERN_RULEBOOK.md` | RULEBOOK READY |

## REFERENCE FILES (not expert-specific)

| File | Purpose | Used by |
|---|---|---|
| `AI_STOCK_SIGNAL_HIERARCHY.md` | Signal priority hierarchy | All experts, Meta Layer |
| `KNOWLEDGE_TO_FEATURE_MAP.md` | Knowledge → feature mapping | R Layer |
| `PATTERN_STRUCTURE_RULEBOOK.md` | Pattern theory (Edwards & Magee) | V4P, V4TREND_PATTERN |

---

## BUILD STATUS SUMMARY

| Status | Count | Experts |
|---|---|---|
| BUILT | 3 | V4REG, V4I, V4MA |
| RULEBOOK READY | 17 | V4ADX, V4MACD, V4RSI, V4STO, V4V, V4OBV, V4ATR, V4BB, V4P, V4CANDLE, V4BR, V4RS, V4S, V4LIQ, V4PIVOT, V4SR, V4TREND_PATTERN |

---

*Update this file when building new experts or adding rulebooks.*
