"""
V4V — Volume Behavior Expert

Per-symbol expert computing volume-based signals.
Indicators: vol_ratio, vol_trend_5, climax flag, price return.

Output:
    volume_score    : -4 to +4
    volume_norm     : -1 to +1 (score/4, for Meta Layer)
    signal_code     : V4V_BULL_EXPAND / V4V_BEAR_EXPAND / ...
    signal_quality  : 0..4

Features exported for R Layer:
    vol_ratio, vol_trend_5, vol_trend_10, vol_price_confirm,
    vol_climax, vol_drying, vol_expansion

Ghi vao: signals.db -> expert_signals
Tuan thu: DATA_LEAKAGE_PREVENTION (chi dung data den T-1)
"""

from .feature_builder import VolFeatureBuilder
from .signal_logic import VolSignalLogic
from .expert_writer import VolExpertWriter

__all__ = ["VolFeatureBuilder", "VolSignalLogic", "VolExpertWriter"]
