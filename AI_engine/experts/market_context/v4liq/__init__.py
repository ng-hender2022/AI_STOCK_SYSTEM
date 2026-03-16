"""
V4LIQ — Liquidity Expert

Per-symbol expert computing liquidity-based signals for all 92 symbols.
Composite of 4 sub-scores: ADTV tier, volume consistency, spread proxy, liquidity trend.

Output:
    liq_score       : -4 to +4  (primary_score)
    liq_norm        : -1 to +1  (liq_score / 4, secondary_score)
    signal_code     : LIQ_MEGA / LIQ_HIGH / LIQ_GOOD / ...
    signal_quality  : 0..4

Metadata: adtv_20d, adtv_60d, adtv_ratio, volume_cv, zero_volume_days,
          hl_spread_avg, adtv_sub, consistency_sub, spread_sub, trend_sub, liq_norm

Ghi vao: signals.db -> expert_signals
Tuan thu: DATA_LEAKAGE_PREVENTION (chi dung data den T-1)
"""

from .feature_builder import LiqFeatureBuilder
from .signal_logic import LiqSignalLogic
from .expert_writer import LiqExpertWriter

__all__ = ["LiqFeatureBuilder", "LiqSignalLogic", "LiqExpertWriter"]
