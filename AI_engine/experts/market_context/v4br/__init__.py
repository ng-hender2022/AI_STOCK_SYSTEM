"""
V4BR — Market Breadth Expert

Market-wide expert computing breadth scores across the 91-stock universe.
Outputs the SAME breadth score for every symbol on a given date.

Output:
    primary_score   : breadth_score (-4 to +4)
    secondary_score : breadth_norm  (breadth_score / 4)

Writes to: signals.db -> expert_signals (one row per symbol per date)
Data source: market.db -> prices_daily (all tradable stocks)
Complies with: DATA_LEAKAGE_PREVENTION (only data with date < target_date)
"""

from .feature_builder import BreadthFeatureBuilder
from .signal_logic import BreadthSignalLogic
from .expert_writer import BreadthExpertWriter

__all__ = ["BreadthFeatureBuilder", "BreadthSignalLogic", "BreadthExpertWriter"]
