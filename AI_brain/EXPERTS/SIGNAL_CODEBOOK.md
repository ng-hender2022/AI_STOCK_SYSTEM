# SIGNAL CODEBOOK — AI_STOCK v2

Generated: 2026-03-15
Status: ACTIVE

---

## 1. SIGNAL CODE FORMAT

```
{EXPERT_ID}_{DIRECTION}_{TYPE}_{QUALIFIER}
```

- **EXPERT_ID**: V4I, V4MA, V4RSI, etc.
- **DIRECTION**: BULL, BEAR, NEUT (neutral)
- **TYPE**: loại tín hiệu cụ thể
- **QUALIFIER**: optional, thêm context

---

## 2. COMMON SIGNAL TYPES

| Type | Nghĩa |
|---|---|
| CROSS | Đường cắt nhau (MA cross, signal line cross) |
| BREAK | Breakout / Breakdown |
| DIV | Divergence |
| EXTREME | Ở vùng quá mua / quá bán |
| TREND | Trend signal |
| REVERSAL | Reversal signal |
| CONFIRM | Confirmation signal |
| SQUEEZE | Squeeze / compression |
| EXPAND | Expansion |

---

## 3. SIGNAL CODES BY EXPERT

### V4I — Ichimoku
| Code | Nghĩa | Quality |
|---|---|---|
| V4I_BULL_CROSS_TK | Tenkan cắt lên Kijun | 2-3 |
| V4I_BEAR_CROSS_TK | Tenkan cắt xuống Kijun | 2-3 |
| V4I_BULL_BREAK_CLOUD | Price breakout lên khỏi cloud | 3-4 |
| V4I_BEAR_BREAK_CLOUD | Price breakdown xuống cloud | 3-4 |
| V4I_BULL_TREND_ABOVE | Price trên cloud, Chikou confirm | 2 |
| V4I_BEAR_TREND_BELOW | Price dưới cloud, Chikou confirm | 2 |
| V4I_NEUT_INSIDE_CLOUD | Price trong cloud | 1 |

### V4MA — Moving Average
| Code | Nghĩa | Quality |
|---|---|---|
| V4MA_BULL_CROSS_GOLDEN | Golden cross (MA50 > MA200) | 3 |
| V4MA_BEAR_CROSS_DEATH | Death cross (MA50 < MA200) | 3 |
| V4MA_BULL_CROSS_SHORT | Short-term MA cross up | 2 |
| V4MA_BEAR_CROSS_SHORT | Short-term MA cross down | 2 |
| V4MA_BULL_TREND_ALIGNED | All MAs aligned bullish | 3 |
| V4MA_BEAR_TREND_ALIGNED | All MAs aligned bearish | 3 |

### V4ADX — Trend Strength
| Code | Nghĩa | Quality |
|---|---|---|
| V4ADX_BULL_TREND_STRONG | ADX > 25, +DI > -DI | 3 |
| V4ADX_BEAR_TREND_STRONG | ADX > 25, -DI > +DI | 3 |
| V4ADX_NEUT_TREND_WEAK | ADX < 20 | 1 |
| V4ADX_BULL_TREND_START | ADX rising from < 20 | 2 |

### V4MACD — MACD
| Code | Nghĩa | Quality |
|---|---|---|
| V4MACD_BULL_CROSS | MACD cắt lên signal line | 2-3 |
| V4MACD_BEAR_CROSS | MACD cắt xuống signal line | 2-3 |
| V4MACD_BULL_DIV | Bullish divergence | 3 |
| V4MACD_BEAR_DIV | Bearish divergence | 3 |
| V4MACD_BULL_CROSS_ZERO | MACD cross zero lên | 2 |
| V4MACD_BEAR_CROSS_ZERO | MACD cross zero xuống | 2 |

### V4RSI — RSI
| Code | Nghĩa | Quality |
|---|---|---|
| V4RSI_BULL_EXTREME_OS | RSI < 30 (oversold) | 2 |
| V4RSI_BEAR_EXTREME_OB | RSI > 70 (overbought) | 2 |
| V4RSI_BULL_DIV | Bullish divergence | 3 |
| V4RSI_BEAR_DIV | Bearish divergence | 3 |
| V4RSI_BULL_REVERSAL | RSI bounce from oversold | 3 |
| V4RSI_BEAR_REVERSAL | RSI drop from overbought | 3 |

### V4STO — Stochastic
| Code | Nghĩa | Quality |
|---|---|---|
| V4STO_BULL_CROSS | %K cắt lên %D | 2 |
| V4STO_BEAR_CROSS | %K cắt xuống %D | 2 |
| V4STO_BULL_EXTREME_OS | Stochastic < 20 | 2 |
| V4STO_BEAR_EXTREME_OB | Stochastic > 80 | 2 |

### V4V — Volume Behavior
| Code | Nghĩa | Quality |
|---|---|---|
| V4V_BULL_EXPAND | Volume surge + price up | 3 |
| V4V_BEAR_EXPAND | Volume surge + price down | 3 |
| V4V_BULL_CONFIRM | Rising volume + uptrend | 2 |
| V4V_BEAR_CONFIRM | Rising volume + downtrend | 2 |
| V4V_BEAR_DIV | Price up but volume declining | 2 |
| V4V_NEUT_DRY | Volume drying up | 1 |

### V4OBV — OBV
| Code | Nghĩa | Quality |
|---|---|---|
| V4OBV_BULL_TREND | OBV trending up | 2 |
| V4OBV_BEAR_TREND | OBV trending down | 2 |
| V4OBV_BULL_DIV | Price down, OBV up | 3 |
| V4OBV_BEAR_DIV | Price up, OBV down | 3 |
| V4OBV_BULL_BREAK | OBV breakout | 3 |

### V4ATR — ATR
| Code | Nghĩa | Quality |
|---|---|---|
| V4ATR_BULL_EXPAND | ATR expanding (trend accelerating) | 2 |
| V4ATR_NEUT_SQUEEZE | ATR contracting (consolidation) | 1 |
| V4ATR_BEAR_EXTREME | ATR spike (panic/capitulation) | 3 |

### V4BB — Bollinger Bands
| Code | Nghĩa | Quality |
|---|---|---|
| V4BB_BULL_BREAK | Price break above upper band | 2 |
| V4BB_BEAR_BREAK | Price break below lower band | 2 |
| V4BB_BULL_SQUEEZE | Squeeze + break up | 3 |
| V4BB_BEAR_SQUEEZE | Squeeze + break down | 3 |
| V4BB_BULL_REVERSAL | Bounce from lower band | 2 |
| V4BB_BEAR_REVERSAL | Reject from upper band | 2 |

### V4P — Price Action
| Code | Nghĩa | Quality |
|---|---|---|
| V4P_BULL_BREAK | Break resistance | 3 |
| V4P_BEAR_BREAK | Break support | 3 |
| V4P_BULL_REVERSAL | Reversal at support | 3 |
| V4P_BEAR_REVERSAL | Reversal at resistance | 3 |
| V4P_BULL_TREND | Higher highs, higher lows | 2 |
| V4P_BEAR_TREND | Lower highs, lower lows | 2 |

### V4CANDLE — Candlestick
| Code | Nghĩa | Quality |
|---|---|---|
| V4CANDLE_BULL_ENGULF | Bullish engulfing | 3 |
| V4CANDLE_BEAR_ENGULF | Bearish engulfing | 3 |
| V4CANDLE_BULL_HAMMER | Hammer / inverted hammer | 2 |
| V4CANDLE_BEAR_SHOOTING | Shooting star | 2 |
| V4CANDLE_BULL_MORNING | Morning star / doji | 3 |
| V4CANDLE_BEAR_EVENING | Evening star / doji | 3 |
| V4CANDLE_BULL_THREE | Three white soldiers | 3 |
| V4CANDLE_BEAR_THREE | Three black crows | 3 |

### V4BR — Breadth
| Code | Nghĩa | Quality |
|---|---|---|
| V4BR_BULL_BROAD | Broad market advance | 3 |
| V4BR_BEAR_BROAD | Broad market decline | 3 |
| V4BR_BEAR_DIV | Index up but breadth declining | 3 |
| V4BR_BULL_EXTREME | Breadth extremely oversold | 2 |

### V4RS — Relative Strength
| Code | Nghĩa | Quality |
|---|---|---|
| V4RS_BULL_OUTPERFORM | Stock outperforming VNINDEX | 2 |
| V4RS_BEAR_UNDERPERFORM | Stock underperforming VNINDEX | 2 |
| V4RS_BULL_TREND | RS trending up | 2 |
| V4RS_BEAR_TREND | RS trending down | 2 |

### V4REG — Market Regime
| Code | Nghĩa | Quality |
|---|---|---|
| V4REG_BULL_STRONG | Strong bull regime | 3 |
| V4REG_BULL_WEAK | Weak bull regime | 2 |
| V4REG_NEUT_NEUTRAL | Neutral regime | 1 |
| V4REG_BEAR_WEAK | Weak bear regime | 2 |
| V4REG_BEAR_STRONG | Strong bear regime | 3 |
| V4REG_BULL_TRANSITION | Transitioning to bull | 2 |
| V4REG_BEAR_TRANSITION | Transitioning to bear | 2 |

### V4S — Sector Strength
| Code | Nghĩa | Quality |
|---|---|---|
| V4S_BULL_LEAD | Sector leading market | 3 |
| V4S_BEAR_LAG | Sector lagging market | 2 |
| V4S_BULL_ROTATE | Rotation into sector | 2 |
| V4S_BEAR_ROTATE | Rotation out of sector | 2 |

### V4LIQ — Liquidity
| Code | Nghĩa | Quality |
|---|---|---|
| V4LIQ_BULL_HIGH | High liquidity (easy to trade) | 2 |
| V4LIQ_BEAR_LOW | Low liquidity (risky) | 2 |
| V4LIQ_BULL_SURGE | Liquidity surge (institutional interest) | 3 |
| V4LIQ_BEAR_DRY | Liquidity drying up | 2 |

---

*Signal codes được dùng thống nhất trong expert_signals.signal_code*
*Thêm signal code mới phải cập nhật file này.*
