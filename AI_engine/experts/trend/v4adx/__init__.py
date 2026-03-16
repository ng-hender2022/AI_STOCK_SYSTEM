"""
V4ADX — Trend Strength / ADX Expert

Per-symbol expert computing ADX-based trend strength signals.
ADX period: 14 (Wilder smoothing)

Output:
    primary_score   : 0..4 (adx_score, trend strength only)
    secondary_score : di_score = +DI - -DI (raw directional difference)
    signal_quality  : 0..4
    signal_code     : V4ADX_BULL_TREND_STRONG, V4ADX_BEAR_TREND_STRONG, etc.

Features exported for R Layer:
    adx_value, plus_di, minus_di, di_diff, adx_slope,
    adx_rising, di_cross_bull, di_cross_bear, adx_score, di_score

Ghi vao: signals.db -> expert_signals
Tuan thu: DATA_LEAKAGE_PREVENTION (chi dung data < target_date)
"""

from .feature_builder import ADXFeatureBuilder
from .signal_logic import ADXSignalLogic
from .expert_writer import ADXExpertWriter

__all__ = ["ADXFeatureBuilder", "ADXSignalLogic", "ADXExpertWriter"]
