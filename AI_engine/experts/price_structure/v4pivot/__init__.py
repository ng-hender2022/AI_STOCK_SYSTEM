"""
V4PIVOT — Pivot Point Expert

Per-symbol expert computing pivot point signals from standard pivot formulas
across daily, weekly, and monthly timeframes.

Output:
    pivot_score     : -4 to +4
    pivot_norm      : -1 to +1 (score/4, for Meta Layer)
    signal_quality  : 0..4

Features exported for R Layer:
    pivot, r1, r2, s1, s2
    weekly_pivot, monthly_pivot
    position_score, confluence_score, alignment_score

Ghi vao: signals.db -> expert_signals
Tuan thu: DATA_LEAKAGE_PREVENTION (chi dung data den T-1)
"""

from .feature_builder import PivotFeatureBuilder
from .signal_logic import PivotSignalLogic
from .expert_writer import PivotExpertWriter

__all__ = ["PivotFeatureBuilder", "PivotSignalLogic", "PivotExpertWriter"]
