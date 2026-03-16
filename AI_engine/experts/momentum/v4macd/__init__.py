"""
V4MACD — MACD Expert

Per-symbol expert computing MACD-based momentum signals.
MACD params: EMA(12), EMA(26), Signal EMA(9).

Output:
    macd_score      : -4 to +4
    macd_norm       : -1 to +1 (score/4, for Meta Layer)
    signal_code     : V4MACD_BULL_CROSS / V4MACD_BEAR_CROSS / ...
    signal_quality  : 0..4

Features exported for R Layer:
    macd_value, signal_value, histogram_value,
    macd_slope, histogram_slope,
    macd_above_signal, macd_above_zero, divergence_flag,
    cross_score, zero_line_score, histogram_score, divergence_score, macd_norm

Ghi vao: signals.db -> expert_signals
Tuan thu: DATA_LEAKAGE_PREVENTION (chi dung data < target_date)
"""

from .feature_builder import MACDFeatureBuilder
from .signal_logic import MACDSignalLogic
from .expert_writer import MACDExpertWriter

__all__ = ["MACDFeatureBuilder", "MACDSignalLogic", "MACDExpertWriter"]
