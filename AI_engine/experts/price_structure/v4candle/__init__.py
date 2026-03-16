"""
V4CANDLE — Candlestick Pattern Expert

Per-symbol expert computing candlestick pattern signals from OHLCV data.
Detects single, double, and triple candlestick patterns with volume
confirmation and swing-context modifiers.

Output:
    candle_score : -4 to +4
    candle_norm  : -1 to +1 (score/4, for Meta Layer)
    signal_quality : 0..4

Features exported for R Layer:
    pattern_name, pattern_direction, body_pct,
    upper_shadow_pct, lower_shadow_pct,
    volume_confirm, at_swing, candle_norm

Ghi vao: signals.db -> expert_signals
Tuan thu: DATA_LEAKAGE_PREVENTION (chi dung data den T-1)
"""

from .feature_builder import CandleFeatureBuilder
from .signal_logic import CandleSignalLogic
from .expert_writer import CandleExpertWriter

__all__ = ["CandleFeatureBuilder", "CandleSignalLogic", "CandleExpertWriter"]
