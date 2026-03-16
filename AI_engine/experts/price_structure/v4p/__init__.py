"""
V4P — Price Action Expert

Per-symbol expert computing price action signals from swing structure,
support/resistance (20-day high/low), and SMA20 position.

Output:
    price_action_score : -4 to +4
    price_action_norm  : -1 to +1 (score/4, for Meta Layer)
    trend_structure    : UPTREND / DOWNTREND / CONSOLIDATION
    signal_quality     : 0..4

Features exported for R Layer:
    hh_count, hl_count, lh_count, ll_count
    range_position, sma20, sma20_slope
    high20, low20, breakout_flag, breakdown_flag

Ghi vao: signals.db -> expert_signals
Tuan thu: DATA_LEAKAGE_PREVENTION (chi dung data den T-1)
"""

from .feature_builder import PAFeatureBuilder
from .signal_logic import PASignalLogic
from .expert_writer import PAExpertWriter

__all__ = ["PAFeatureBuilder", "PASignalLogic", "PAExpertWriter"]
