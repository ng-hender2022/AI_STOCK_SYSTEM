"""
V4RSI -- RSI (Relative Strength Index) Expert

Per-symbol expert computing RSI-based momentum signals.
RSI period: 14 (Wilder smoothing).

Output:
    primary_score   : RSI value (0 to 100)
    secondary_score : rsi_norm = (rsi - 50) / 50 (-1 to +1)
    signal_code     : V4RSI_BULL_*, V4RSI_BEAR_*, V4RSI_NEUT_*
    signal_quality  : 0..4

Features exported for R Layer:
    rsi_value, rsi_norm, rsi_slope, rsi_ma10,
    rsi_above_50, rsi_zone, divergence_flag,
    failure_swing_flag, signal_quality

Ghi vao: signals.db -> expert_signals
Tuan thu: DATA_LEAKAGE_PREVENTION (chi dung data den T-1)
"""

from .feature_builder import RSIFeatureBuilder
from .signal_logic import RSISignalLogic
from .expert_writer import RSIExpertWriter

__all__ = ["RSIFeatureBuilder", "RSISignalLogic", "RSIExpertWriter"]
