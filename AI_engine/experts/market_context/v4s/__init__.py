"""
V4S — Sector Strength Expert

Per-symbol expert: each stock gets a score based on its sector's strength.

Output:
    sector_score    : -4 to +4
    sector_norm     : -1 to +1 (score/4, for Meta Layer)
    signal_code     : SEC_TOP_SECTOR, SEC_STRONG_SECTOR, ...
    signal_quality  : 0..4

Sector metrics (equal-weighted across stocks in sector):
    sector_return_20d, sector_vs_market_20d, sector_rank_20d,
    sector_pct_above_sma50, sector_momentum, sector_rank_change_10d

Ghi vao: signals.db -> expert_signals
Tuan thu: DATA_LEAKAGE_PREVENTION (chi dung data den T-1)
"""

from .feature_builder import SectorFeatureBuilder
from .signal_logic import SectorSignalLogic
from .expert_writer import SectorExpertWriter

__all__ = ["SectorFeatureBuilder", "SectorSignalLogic", "SectorExpertWriter"]
