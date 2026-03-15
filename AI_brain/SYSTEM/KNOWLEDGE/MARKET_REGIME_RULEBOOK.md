
# MARKET_REGIME_RULEBOOK

SYSTEM:
AI_STOCK KNOWLEDGE MODULE

MODULE NAME:
MARKET_REGIME_RULEBOOK

PRIMARY SOURCES:
- The Art and Science of Technical Analysis – Adam Grimes (2012)
- Technical Analysis of Stock Trends – Edwards & Magee (9th Edition)
- The Candlestick Course – Steve Nison (2003)

PURPOSE:
Define the overall market state before interpreting trading signals.
Market regime determines which signals are reliable.
Signals must always be interpreted within regime context.

---

# 1. CORE PRINCIPLE

Markets move through distinct structural states.

Primary regimes:

TREND_REGIME
RANGE_REGIME
TRANSITION_REGIME

AI must detect regime first before interpreting signals.

---

# 2. TREND REGIME

Definition based on classical trend theory (Edwards & Magee).

Structure:

Uptrend:
- Higher highs
- Higher lows

Downtrend:
- Lower highs
- Lower lows

AI rule:

trend_regime =
    directional_price_structure
AND sustained_momentum

Reliable signals in trend regime:

- breakout continuation
- pullback entries
- trend-following signals

---

# 3. RANGE REGIME

Also known as trading range (Edwards & Magee).

Characteristics:

- Price oscillates between support and resistance
- No persistent directional movement

Structure:

range_regime =
    repeated resistance rejection
AND repeated support bounce

Reliable signals in range regime:

- support bounce
- resistance rejection
- mean reversion

Signals unreliable in range:

- breakout signals without confirmation

---

# 4. TRANSITION REGIME

Occurs when the market shifts between regimes.

Typical conditions:

- trend exhaustion
- volatility expansion
- failed breakouts
- reversal patterns

AI rule:

transition_regime =
    trend_breakdown
OR repeated false breakouts
OR volatility expansion

Signals to monitor:

- reversal structures
- candlestick reversal patterns
- volume spikes

---

# 5. CANDLESTICK SENTIMENT CONTEXT

Candlestick analysis reveals short‑term sentiment.

Examples:

long bullish body → strong buying pressure
long upper shadow → rejection of higher price
doji → market indecision

Rule:

regime_shift_warning =
    reversal_candlestick
AND key_support_resistance

---

# 6. VOLUME CONTEXT

Volume confirms regime.

Trend regime:

- increasing volume in trend direction

Range regime:

- declining volume
- sporadic spikes at boundaries

AI rule:

volume_confirmation =
    volume_ratio > baseline

---

# 7. VOLATILITY STATE

Volatility modifies regime behavior.

States:

high_volatility
low_volatility

AI rule:

volatility_state =
    high if price_range expanding
    low if price_range contracting

High volatility often appears during regime transition.

---

# 8. REGIME DETECTION FEATURES

AI should compute:

trend_strength
range_width
volatility_level
breakout_frequency
false_breakout_rate

Derived logic:

if strong directional structure:
    TREND_REGIME

if oscillation between support and resistance:
    RANGE_REGIME

if trend breaks or volatility spikes:
    TRANSITION_REGIME

---

# 9. SIGNAL FILTER

Signals must pass regime filter.

valid_signal =
    signal
AND regime_compatible

Examples:

breakout_signal valid in TREND or TRANSITION

mean_reversion valid in RANGE

---

# 10. ROLE IN AI_STOCK ARCHITECTURE

market data
→ V4D / V4H features
→ regime detection
→ signal interpretation
→ R1 reasoning
→ X1 decision

Regime detection must occur before signal evaluation.

---

# 11. FINAL PRINCIPLE

Hierarchy of market interpretation:

1 detect regime
2 detect market structure
3 detect signal
4 evaluate probability

Signals without regime awareness are unreliable.
