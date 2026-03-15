"""
V4REG — Market Regime Expert

Market-wide expert tính regime scores cho toàn thị trường.
Dựa trên VNINDEX + breadth của 91 stocks.

Output:
    trend_regime_score  : -4 → +4  (xu hướng thị trường)
    vol_regime_score    :  0 → 4   (mức độ biến động)
    liquidity_regime_score: -2 → +2 (thanh khoản)

Ghi vào: market.db → market_regime
Tuân thủ: DATA_LEAKAGE_PREVENTION (chỉ dùng data đến T-1)
"""

from .feature_builder import RegimeFeatureBuilder
from .signal_logic import RegimeSignalLogic
from .regime_writer import RegimeWriter

__all__ = ["RegimeFeatureBuilder", "RegimeSignalLogic", "RegimeWriter"]
