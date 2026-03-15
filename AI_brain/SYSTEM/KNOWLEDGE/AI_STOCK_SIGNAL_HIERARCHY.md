
# AI_STOCK_SIGNAL_HIERARCHY

SYSTEM:
AI_STOCK KNOWLEDGE MODULE

MODULE NAME:
AI_STOCK_SIGNAL_HIERARCHY

PURPOSE:
Define the correct order in which AI interprets market data, structure, and signals.
This hierarchy prevents conflicts between rulebooks and ensures consistent reasoning.

RELATED RULEBOOKS:
PRICE_ACTION_RULEBOOK
VOLUME_BEHAVIOR_RULEBOOK
PATTERN_STRUCTURE_RULEBOOK
CANDLESTICK_RULEBOOK
MARKET_REGIME_RULEBOOK

---

# 1. CORE PRINCIPLE

AI must never interpret signals directly from raw data.

Correct evaluation order:

1 MARKET REGIME
2 MARKET STRUCTURE
3 SIGNAL DETECTION
4 VOLUME CONFIRMATION
5 PROBABILITY EVALUATION

---

# 2. STEP 1 — DETECT MARKET REGIME

Determine the global state of the market.

Possible regimes:

TREND_REGIME
RANGE_REGIME
TRANSITION_REGIME

Regime determines which signals are valid.

Example:

TREND → breakout and pullback signals valid  
RANGE → mean reversion signals valid

---

# 3. STEP 2 — DETECT MARKET STRUCTURE

Identify price structure from PRICE_ACTION_RULEBOOK.

Structure examples:

higher highs
higher lows
lower highs
lower lows

Also detect:

support levels
resistance levels
consolidation zones

Structure provides context for signals.

---

# 4. STEP 3 — SIGNAL DETECTION

Signals originate from:

PATTERN_STRUCTURE_RULEBOOK
CANDLESTICK_RULEBOOK

Examples:

breakout
reversal pattern
engulfing candle
hammer

AI rule:

signal_validity requires correct regime and structure context.

---

# 5. STEP 4 — VOLUME CONFIRMATION

Signals must be confirmed by volume behavior.

Volume rules from VOLUME_BEHAVIOR_RULEBOOK.

Example:

breakout_valid =
    breakout_structure
AND volume_expansion

Low volume signals are weak.

---

# 6. STEP 5 — PROBABILITY EVALUATION

After signal confirmation AI evaluates probability.

Factors:

trend_strength
volume_strength
pattern_quality
market_volatility

Output:

probability_score
confidence_level

---

# 7. SIGNAL PRIORITY

When multiple signals appear simultaneously:

priority order:

1 structural signals (trend break / breakout)
2 pattern signals
3 candlestick signals

Candlesticks provide early warning but lower reliability.

---

# 8. CONFLICT RESOLUTION

If signals conflict:

1 regime dominates
2 structure overrides candle signal
3 volume confirmation required

Example:

bearish candle during strong uptrend → ignore

---

# 9. AI_STOCK ARCHITECTURE FLOW

market data
→ feature extraction (V4D / V4H)
→ regime detection
→ structure detection
→ signal detection
→ volume confirmation
→ probability evaluation
→ R1 reasoning
→ X1 decision

---

# 10. FINAL PRINCIPLE

Signals must always be interpreted within hierarchy.

Wrong order leads to:

false signals
signal conflicts
incorrect market interpretation

Correct order ensures consistent AI reasoning.
