# SAFE EDIT RULES

Claude Code must follow these safety rules when editing the AI_STOCK system.

1.  Never modify multiple components simultaneously.

Components:
- Expert Layer (17 experts): V4I, V4MA, V4ADX, V4MACD, V4RSI, V4STO,
  V4V, V4OBV, V4ATR, V4BB, V4P, V4CANDLE, V4BR, V4RS, V4REG, V4S, V4LIQ
- R1 = Linear Model
- R2 = Random Forest
- R3 = Gradient Boosting
- R4 = Neural Network
- R5 = Sector Models
- X1 = Decision Engine

2.  Database schema changes require explicit approval.

3.  Prefer additive improvements rather than refactoring large sections
    of code.

4.  Avoid moving logic across layers.

Example: Expert features should not be moved into R Layer.
R Layer logic should not be moved into X1.

5.  Always update CHANGELOG/CHANGELOG.md after code modifications.
