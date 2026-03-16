"""
V4OBV — On Balance Volume Expert

Per-symbol expert computing OBV-based volume signals.
Based on Joseph Granville's On Balance Volume methodology.

Output:
    obv_score       : -4 to +4
    obv_norm        : -1 to +1 (score/4, for Meta Layer)
    trend_score     : -2 to +2 (OBV slope direction)
    divergence_score: -1 to +1 (OBV vs price divergence)
    breakout_score  : -1 to +1 (OBV new high/low)
    signal_quality  : 0..4

Features exported for R Layer:
    obv_slope_norm, obv_divergence, obv_new_high, obv_new_low,
    obv_confirms_price, obv_norm, trend_score, divergence_score, breakout_score

Ghi vao: signals.db -> expert_signals
Tuan thu: DATA_LEAKAGE_PREVENTION (chi dung data den T-1)
"""

from .feature_builder import OBVFeatureBuilder
from .signal_logic import OBVSignalLogic
from .expert_writer import OBVExpertWriter

__all__ = ["OBVFeatureBuilder", "OBVSignalLogic", "OBVExpertWriter"]
