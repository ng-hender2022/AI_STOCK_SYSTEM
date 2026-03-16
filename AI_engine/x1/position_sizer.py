"""
Position Sizer
Calculates position size based on ensemble_score, confidence, and regime.
"""

from dataclasses import dataclass


@dataclass
class PositionSize:
    symbol: str
    date: str
    weight: float           # 0..1 portfolio weight
    risk_budget: float      # % of portfolio at risk
    size_reason: str


# Base allocation per signal strength
BASE_WEIGHTS = {
    "STRONG": 0.08,     # 8% max per strong signal
    "MODERATE": 0.05,   # 5% per moderate
    "WEAK": 0.02,       # 2% per weak
    "NONE": 0.0,
    "BLOCKED": 0.0,
}

MAX_SINGLE_POSITION = 0.10  # 10% max per symbol
MIN_POSITION = 0.01         # 1% minimum meaningful position


class PositionSizer:
    """
    Calculate position sizes.

    Rules:
    - Base weight from signal strength
    - Confidence multiplier: weight *= confidence
    - Regime adjustment:
      + regime >= +2 AND vol <= 2 → 1.5x risk budget
      + regime 0 to +2 → 1.0x (normal)
      + regime -2 to 0 → 0.7x
      + regime <= -2 → 0.4x
    - Cap at MAX_SINGLE_POSITION
    """

    def size(
        self,
        symbol: str,
        date: str,
        action: str,
        strength: str,
        confidence: float,
        regime_trend: float,
        regime_vol: float = 2.0,
    ) -> PositionSize:
        if action == "HOLD" or strength in ("NONE", "BLOCKED"):
            return PositionSize(symbol=symbol, date=date, weight=0.0,
                                risk_budget=0.0, size_reason="No position")

        base = BASE_WEIGHTS.get(strength, 0.02)

        # Confidence multiplier
        conf_mult = max(0.5, min(1.5, confidence))
        weight = base * conf_mult

        # Regime adjustment
        if regime_trend >= 2.0 and regime_vol <= 2.0:
            regime_mult = 1.5
            reason_regime = "bull regime + low vol → 1.5x"
        elif regime_trend >= 0:
            regime_mult = 1.0
            reason_regime = "normal regime"
        elif regime_trend >= -2:
            regime_mult = 0.7
            reason_regime = "weak regime → 0.7x"
        else:
            regime_mult = 0.4
            reason_regime = "bear regime → 0.4x"

        weight *= regime_mult

        # Cap
        weight = max(MIN_POSITION, min(MAX_SINGLE_POSITION, weight))

        risk_budget = weight * 0.02  # assume 2% stop-loss

        reason = f"{strength} {action}, conf={confidence:.2f}, {reason_regime}, weight={weight:.3f}"

        return PositionSize(
            symbol=symbol, date=date,
            weight=round(weight, 4),
            risk_budget=round(risk_budget, 6),
            size_reason=reason,
        )
