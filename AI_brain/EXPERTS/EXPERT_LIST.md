# EXPERT LIST — AI_STOCK v2

Generated: 2026-03-15
Status: ACTIVE
Total: 17 experts

---

## TREND GROUP (3)

| # | ID | Name | Rulebook | Scale | Input |
|---|---|---|---|---|---|
| 1 | V4I | Ichimoku Expert | ICHIMOKU_RULEBOOK | -4 → +4 | prices_daily |
| 2 | V4MA | Moving Average Expert | MA_RULEBOOK | -4 → +4 | prices_daily |
| 3 | V4ADX | Trend Strength Expert | ADX_RULEBOOK | 0 → 4 | prices_daily |

## MOMENTUM GROUP (3)

| # | ID | Name | Rulebook | Scale | Input |
|---|---|---|---|---|---|
| 4 | V4MACD | MACD Expert | MACD_RULEBOOK | -4 → +4 | prices_daily |
| 5 | V4RSI | RSI Expert | RSI_RULEBOOK | 0 → 100 | prices_daily |
| 6 | V4STO | Stochastic Expert | STOCHASTIC_RULEBOOK | 0 → 100 | prices_daily |

## VOLUME GROUP (2)

| # | ID | Name | Rulebook | Scale | Input |
|---|---|---|---|---|---|
| 7 | V4V | Volume Behavior Expert | VOLUME_RULEBOOK | -4 → +4 | prices_daily |
| 8 | V4OBV | OBV Expert | OBV_RULEBOOK | -4 → +4 | prices_daily |

## VOLATILITY GROUP (2)

| # | ID | Name | Rulebook | Scale | Input |
|---|---|---|---|---|---|
| 9 | V4ATR | ATR Expert | ATR_RULEBOOK | 0 → 4 | prices_daily |
| 10 | V4BB | Bollinger Bands Expert | BOLLINGER_RULEBOOK | -4 → +4 | prices_daily |

## PRICE STRUCTURE GROUP (2)

| # | ID | Name | Rulebook | Scale | Input |
|---|---|---|---|---|---|
| 11 | V4P | Price Action Expert | PRICE_ACTION_RULEBOOK | -4 → +4 | prices_daily |
| 12 | V4CANDLE | Candlestick Expert | CANDLE_RULEBOOK | -4 → +4 | prices_daily |

## MARKET CONTEXT GROUP (3)

| # | ID | Name | Rulebook | Scale | Input |
|---|---|---|---|---|---|
| 13 | V4BR | Breadth Expert | BREADTH_RULEBOOK | -4 → +4 | prices_daily (all symbols) |
| 14 | V4RS | Relative Strength Expert | RS_RULEBOOK | -4 → +4 | prices_daily + VNINDEX |
| 15 | V4REG | Market Regime Expert | REGIME_RULEBOOK | -4 → +4 | prices_daily (all symbols) |

## STRUCTURE / ENVIRONMENT GROUP (2)

| # | ID | Name | Rulebook | Scale | Input |
|---|---|---|---|---|---|
| 16 | V4S | Sector Strength Expert | SECTOR_RULEBOOK | -4 → +4 | prices_daily + sectors |
| 17 | V4LIQ | Liquidity Expert | LIQUIDITY_RULEBOOK | -4 → +4 | prices_daily |

---

## BUILD ORDER (khuyến nghị)

1. **V4REG** (Market Regime) — build trước, nhiều expert khác cần regime context
2. **V4MA** → V4I → V4ADX (Trend group)
3. **V4RSI** → V4MACD → V4STO (Momentum group)
4. **V4V** → V4OBV (Volume group)
5. **V4ATR** → V4BB (Volatility group)
6. **V4P** → V4CANDLE (Price Structure group)
7. **V4BR** → V4RS → V4S → V4LIQ (Context + Structure)

---

*Mỗi expert có rulebook riêng tại AI_brain/SYSTEM/KNOWLEDGE/*
