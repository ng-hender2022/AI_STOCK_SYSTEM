# EXPERT MODULE STANDARD

Experts represent interpretable trading logic modules.
Experts are deterministic engines — they do NOT learn, do NOT predict.

## 17 Experts

V4I (Ichimoku), V4MA (Moving Average), V4ADX (Trend Strength),
V4MACD (MACD), V4RSI (RSI), V4STO (Stochastic),
V4V (Volume), V4OBV (OBV), V4ATR (ATR), V4BB (Bollinger),
V4P (Price Action), V4CANDLE (Candlestick),
V4BR (Breadth), V4RS (Relative Strength), V4REG (Regime),
V4S (Sector), V4LIQ (Liquidity)

## Directory structure

D:\AI\AI_engine\experts\
    base_expert.py
    expert_signal.py
    v4i_ichimoku.py
    v4ma_moving_average.py
    ... (one file per expert)

## Output

Experts output **numeric scores according to their own rulebook scale** — NOT BUY/SELL/NEUTRAL.
Each expert has its own scale (e.g., -4 to +4, 0 to 100, 0 to 4).
Output is written to signals.db → expert_signals table.

## Feeds into

Expert signals feed into the R Layer:
-   R1 Linear Model
-   R2 Random Forest
-   R3 Gradient Boosting
-   R4 Neural Network
-   R5 Sector Models

R Layer ensemble output then feeds into X1 Decision Engine.

Experts must not directly place trades or make decisions.
