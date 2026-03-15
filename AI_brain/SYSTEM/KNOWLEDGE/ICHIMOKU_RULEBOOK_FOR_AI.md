
# ICHIMOKU RULEBOOK FOR AI_STOCK

Purpose:
Define interpretable Ichimoku rules for AI systems (R2, X1).

These rules describe how to interpret Ichimoku signals for trend,
continuation, and reversal detection.

Universe:
91 Vietnamese stocks + VNINDEX.

Timeframe:
Daily (historical learning for R2).

------------------------------------------------

# CORE COMPONENTS

Tenkan (9)
Kijun (26)
Senkou Span A
Senkou Span B
Chikou Span

Cloud = area between Span A and Span B

------------------------------------------------

# TREND REGIME RULES

Rule T1

name: price_above_cloud

definition:

close > max(span_a, span_b)

meaning:

bullish trend environment

strength:

strong


Rule T2

name: price_inside_cloud

definition:

min(span_a, span_b) <= close <= max(span_a, span_b)

meaning:

market equilibrium / consolidation

strength:

neutral


Rule T3

name: price_below_cloud

definition:

close < min(span_a, span_b)

meaning:

bearish trend environment

strength:

strong

------------------------------------------------

# TENKAN / KIJUN CROSS

Rule TK1

name: bullish_tk_cross

definition:

tenkan[t] > kijun[t]
and
tenkan[t-1] <= kijun[t-1]

meaning:

bullish momentum start

strength:

medium


Rule TK2

name: bearish_tk_cross

definition:

tenkan[t] < kijun[t]
and
tenkan[t-1] >= kijun[t-1]

meaning:

bearish momentum start

strength:

medium

------------------------------------------------

# TK CROSS CONTEXT

Rule TK3

name: bullish_tk_cross_above_cloud

definition:

bullish_tk_cross
and
close > cloud

meaning:

strong bullish continuation

strength:

very strong


Rule TK4

name: bearish_tk_cross_below_cloud

definition:

bearish_tk_cross
and
close < cloud

meaning:

strong bearish continuation

strength:

very strong

------------------------------------------------

# KIJUN BASELINE RULES

Rule K1

name: kijun_support

definition:

price pulls back to kijun
and
trend is bullish

meaning:

trend continuation support

strength:

medium


Rule K2

name: kijun_resistance

definition:

price rallies to kijun
and
trend is bearish

meaning:

trend continuation resistance

strength:

medium

------------------------------------------------

# CLOUD STRUCTURE

Rule C1

name: thick_cloud

definition:

abs(span_a - span_b) > cloud_thickness_threshold

meaning:

strong support or resistance zone


Rule C2

name: thin_cloud

definition:

abs(span_a - span_b) small

meaning:

weak support/resistance
potential breakout

------------------------------------------------

# FUTURE CLOUD DIRECTION

Rule FC1

name: bullish_future_cloud

definition:

span_a_future > span_b_future

meaning:

future bullish structure


Rule FC2

name: bearish_future_cloud

definition:

span_a_future < span_b_future

meaning:

future bearish structure

------------------------------------------------

# CLOUD TWIST

Rule CT1

name: bullish_kumo_twist

definition:

span_a crosses above span_b

meaning:

future bullish transition


Rule CT2

name: bearish_kumo_twist

definition:

span_a crosses below span_b

meaning:

future bearish transition

------------------------------------------------

# CHIKOU CONFIRMATION

Rule CH1

name: chikou_above_price

definition:

chikou > price_26

meaning:

trend confirmation


Rule CH2

name: chikou_breakout

definition:

chikou crosses above historical resistance

meaning:

strong bullish confirmation

------------------------------------------------

# EQUILIBRIUM THEORY

Rule E1

name: equilibrium_stretch

definition:

distance(close, kijun) large

meaning:

price extended from equilibrium

likely pullback

------------------------------------------------

# TIME THEORY

Important Ichimoku time numbers:

9
17
26
33
42
65
76
129
172
257

Rule TIME1

name: time_cycle_9

definition:

days_since_pivot ≈ 9

meaning:

potential turning point


Rule TIME2

name: time_cycle_26

definition:

days_since_pivot ≈ 26

meaning:

major turning point candidate

------------------------------------------------

# WAVE STRUCTURE

Rule W1

name: bullish_wave

definition:

higher_high
and
higher_low

meaning:

uptrend structure


Rule W2

name: bearish_wave

definition:

lower_high
and
lower_low

meaning:

downtrend structure

------------------------------------------------

# SIGNAL STRENGTH COMBINATION

Strong bullish alignment:

conditions:

price_above_cloud
tenkan > kijun
bullish_future_cloud
chikou_above_price

signal:

high_probability_uptrend


Strong bearish alignment:

conditions:

price_below_cloud
tenkan < kijun
bearish_future_cloud
chikou_below_price

signal:

high_probability_downtrend

------------------------------------------------

# AI SIGNAL OUTPUT

R2 may generate:

trend_direction

values:

bullish
bearish
neutral

confidence_score

range:

0 – 1

------------------------------------------------

END
