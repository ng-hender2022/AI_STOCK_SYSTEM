"""
V4TREND_PATTERN — Trend Pattern Expert

Per-symbol expert detecting classical chart patterns (flags, pennants,
double tops/bottoms, triangles) and scoring them based on pattern type,
confirmation, and target projection.

Output:
    pattern_score  : -4 to +4
    pattern_norm   : -1 to +1 (score/4, for Meta Layer)
    signal_quality : 0..4

Ghi vao: signals.db -> expert_signals
Tuan thu: DATA_LEAKAGE_PREVENTION (chi dung data den T-1)
"""

from .feature_builder import TPFeatureBuilder
from .signal_logic import TPSignalLogic
from .expert_writer import TPExpertWriter

__all__ = ["TPFeatureBuilder", "TPSignalLogic", "TPExpertWriter"]
