"""
V4STO -- Stochastic Oscillator Expert

Per-symbol expert computing Stochastic-based momentum signals.
Stochastic params: (14, 3, 3) — Fast %K period=14, Slow %K=SMA(Fast %K,3), Slow %D=SMA(Slow %K,3).

Output:
    primary_score   : Slow %K value (0 to 100)
    secondary_score : sto_norm = (slow_k - 50) / 50 (-1 to +1)
    signal_code     : V4STO_BULL_*, V4STO_BEAR_*, V4STO_NEUT_*
    signal_quality  : 0..4

Features exported for R Layer:
    stoch_k, stoch_d, stoch_k_slope, k_above_d,
    stoch_zone, stoch_divergence, stoch_cross_in_zone, sto_norm

Ghi vao: signals.db -> expert_signals
Tuan thu: DATA_LEAKAGE_PREVENTION (chi dung data den T-1)
"""

from .feature_builder import STOFeatureBuilder
from .signal_logic import STOSignalLogic
from .expert_writer import STOExpertWriter

__all__ = ["STOFeatureBuilder", "STOSignalLogic", "STOExpertWriter"]
