"""
V4RS — Relative Strength Expert

Per-symbol expert comparing each stock vs VNINDEX.
Computes RS ratios (5d, 20d, 60d), percentile ranks among 91 stocks,
RS trend (SMA10 vs SMA30 of RS_Line), and a decile×trend scoring matrix.

Output:
    rs_score        : -4 to +4
    rs_norm         : -1 to +1 (score/4, for Meta Layer)
    rs_decile       : 1..10 (1 = top 10%)
    rs_trend        : RISING / FLAT / FALLING
    signal_quality  : 0..4

Features exported for R Layer:
    rs_5d, rs_20d, rs_60d, rs_rank_20d, rs_decile,
    rs_trend, rs_rank_change_10d, rs_norm

Ghi vao: signals.db -> expert_signals
Tuan thu: DATA_LEAKAGE_PREVENTION (chi dung data den T-1)
"""

from .feature_builder import RSFeatureBuilder
from .signal_logic import RSSignalLogic
from .expert_writer import RSExpertWriter

__all__ = ["RSFeatureBuilder", "RSSignalLogic", "RSExpertWriter"]
