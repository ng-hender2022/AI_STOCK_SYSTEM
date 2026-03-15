
# R2 Ichimoku Feature Map for AI_STOCK

This document defines the feature engineering structure used by **R2 Research AI**
for learning market behavior using Ichimoku, Price Action, and RSI.

Universe: Same as V4D (91 stocks + VNINDEX).

Training method:
- Historical learning from AmiBroker data (10 years)
- Data packaged by V15
- R2 reads sequential packages (9 trading days per package)
- After each package, R2 predicts next movement and validates with next data

---

# 1. Raw Market Data

OHLCV:
- open
- high
- low
- close
- volume

---

# 2. Core Ichimoku Lines

Tenkan (9):
    (highest high 9 + lowest low 9) / 2

Kijun (26):
    (highest high 26 + lowest low 26) / 2

Senkou Span A:
    (Tenkan + Kijun) / 2 projected forward 26 periods

Senkou Span B:
    (highest high 52 + lowest low 52) / 2 projected forward 26 periods

Chikou Span:
    close shifted back 26 periods

---

# 3. Structure Features

price_vs_cloud
cloud_thickness
future_cloud_direction
cloud_twist_flag

---

# 4. Tenkan / Kijun Features

tenkan_vs_kijun
tk_spread
tk_cross_up
tk_cross_down
days_since_tk_cross

tenkan_slope
kijun_slope
kijun_direction

---

# 5. Distance / Equilibrium Features

dist_close_tenkan
dist_close_kijun
dist_close_cloud_mid

equilibrium_stretch_score

---

# 6. Chikou Confirmation

chikou_vs_price_26
chikou_vs_cloud_26
chikou_breakout_flag

---

# 7. Time Theory Features

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

Features:

days_since_pivot
near_time_cycle_flag
time_resonance_score

---

# 8. Wave Features

higher_high
higher_low
lower_high
lower_low

wave_direction
wave_expand_flag
wave_contract_flag

---

# 9. Price Range Targets

target_v
target_n
target_e
target_nt

dist_to_target_pct

---

# 10. Price Action

body_percent
upper_wick_percent
lower_wick_percent

bull_run_length
bear_run_length

---

# 11. RSI Features

rsi14
rsi_slope
rsi_divergence_flag

---

# 12. Meta AI Features

ichimoku_regime_score

bullish_alignment_flag:
- price above cloud
- tenkan > kijun
- bullish future cloud
- chikou confirmation

bearish_alignment_flag

reversal_setup_score
continuation_setup_score
trend_failure_risk

---

# 13. Minimal Feature Set for R2 v1

Recommended 18 core features:

tenkan
kijun
span_a
span_b
close

price_vs_cloud
future_cloud_direction
cloud_thickness

tenkan_vs_kijun
tk_spread

kijun_direction

dist_close_kijun
dist_close_cloud

chikou_vs_price
chikou_vs_cloud

near_9
near_26
time_resonance_score

---

# 14. Training Pipeline

Data Source:
- V15 (vnstock intraday + daily)
- AmiBroker historical export

Packaging:

9-day learning window

Process:

Package 1 → R2 learn
Package 2 → R2 predict
Compare prediction with actual result
Update knowledge

Repeat sequentially through entire dataset.

---

END
