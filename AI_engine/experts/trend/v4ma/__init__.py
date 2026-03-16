"""
V4MA — Moving Average Expert

Per-symbol expert computing MA-based trend signals.
MAs: EMA10, EMA20, SMA50, SMA100, SMA200.

Output:
    ma_score        : -4 to +4
    ma_norm         : -1 to +1 (score/4, for Meta Layer)
    alignment       : all_bullish / strong_bullish / ... / all_bearish
    cross_signal    : golden_cross / death_cross / short_cross_up/down / none
    signal_quality  : 0..4

Features exported for R Layer:
    dist_ema10, dist_ema20, dist_ma50, dist_ma100, dist_ma200
    ema10_slope, ema20_slope, ma50_slope, ma100_slope, ma200_slope
    ema10_over_ema20, ma50_over_ma100, ma100_over_ma200, ma50_over_ma200

Ghi vao: signals.db -> expert_signals
Tuan thu: DATA_LEAKAGE_PREVENTION (chi dung data den T-1)
"""

from .feature_builder import MAFeatureBuilder
from .signal_logic import MASignalLogic
from .expert_writer import MAExpertWriter

__all__ = ["MAFeatureBuilder", "MASignalLogic", "MAExpertWriter"]
