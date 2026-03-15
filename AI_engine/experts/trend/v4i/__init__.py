"""
V4I — Ichimoku Expert

Per-symbol expert computing Ichimoku-based trend signals.

Output:
    ichimoku_score      : -4 → +4
    ichimoku_norm       : -1 → +1 (score / 4, for Meta Layer)
    cloud_position      : above / inside / below
    tk_signal           : bullish / bearish / neutral
    chikou_confirm      : bullish / bearish / neutral
    future_cloud        : bullish / bearish / flat
    time_resonance      : 0..1
    signal_quality      : 0..4

Ghi vào: signals.db → expert_signals
Tuân thủ: DATA_LEAKAGE_PREVENTION (chỉ dùng data đến T-1)
"""

from .feature_builder import IchimokuFeatureBuilder
from .signal_logic import IchimokuSignalLogic
from .expert_writer import IchimokuExpertWriter

__all__ = ["IchimokuFeatureBuilder", "IchimokuSignalLogic", "IchimokuExpertWriter"]
