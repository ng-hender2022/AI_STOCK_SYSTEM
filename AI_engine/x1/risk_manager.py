"""
Risk Manager
Controls portfolio risk limits: max positions, max exposure, drawdown.
"""

from dataclasses import dataclass


@dataclass
class RiskCheck:
    passed: bool
    reason: str
    current_exposure: float
    max_exposure: float
    position_count: int
    max_positions: int


class RiskManager:
    """
    Portfolio risk controls.

    Limits:
    - Max positions: 15 symbols
    - Max total exposure: 80% of portfolio
    - Max single position: 10%
    - Max sector exposure: 30%
    - Drawdown halt: if portfolio drawdown > 15%, reduce all positions by 50%

    Usage:
        rm = RiskManager()
        check = rm.check(current_positions, new_decision, portfolio_value)
    """

    MAX_POSITIONS = 15
    MAX_TOTAL_EXPOSURE = 0.80       # 80% max invested
    MAX_SINGLE_POSITION = 0.10      # 10% per symbol
    MAX_SECTOR_EXPOSURE = 0.30      # 30% per sector
    DRAWDOWN_HALT_THRESHOLD = 0.15  # 15% drawdown → reduce

    def __init__(self):
        self.drawdown_active = False

    def check(
        self,
        current_positions: dict[str, float],  # {symbol: weight}
        new_symbol: str,
        new_weight: float,
        sector_weights: dict[str, float] | None = None,  # {sector: total_weight}
        new_sector: str | None = None,
    ) -> RiskCheck:
        """
        Check if adding a new position passes risk limits.

        Args:
            current_positions: existing positions {symbol: weight}
            new_symbol: symbol to add
            new_weight: proposed weight
            sector_weights: current sector exposures
            new_sector: sector of new symbol
        """
        current_exposure = sum(current_positions.values())
        position_count = len(current_positions)

        # Already holds this symbol — update, not new position
        is_update = new_symbol in current_positions

        # Position count check
        if not is_update and position_count >= self.MAX_POSITIONS:
            return RiskCheck(
                passed=False,
                reason=f"Max positions reached ({self.MAX_POSITIONS})",
                current_exposure=current_exposure,
                max_exposure=self.MAX_TOTAL_EXPOSURE,
                position_count=position_count,
                max_positions=self.MAX_POSITIONS,
            )

        # Single position check
        if new_weight > self.MAX_SINGLE_POSITION:
            return RiskCheck(
                passed=False,
                reason=f"Single position {new_weight:.1%} > max {self.MAX_SINGLE_POSITION:.0%}",
                current_exposure=current_exposure,
                max_exposure=self.MAX_TOTAL_EXPOSURE,
                position_count=position_count,
                max_positions=self.MAX_POSITIONS,
            )

        # Total exposure check
        new_total = current_exposure + new_weight
        if is_update:
            new_total -= current_positions.get(new_symbol, 0)
        if new_total > self.MAX_TOTAL_EXPOSURE:
            return RiskCheck(
                passed=False,
                reason=f"Total exposure {new_total:.1%} > max {self.MAX_TOTAL_EXPOSURE:.0%}",
                current_exposure=current_exposure,
                max_exposure=self.MAX_TOTAL_EXPOSURE,
                position_count=position_count,
                max_positions=self.MAX_POSITIONS,
            )

        # Sector check
        if sector_weights and new_sector:
            sector_total = sector_weights.get(new_sector, 0) + new_weight
            if sector_total > self.MAX_SECTOR_EXPOSURE:
                return RiskCheck(
                    passed=False,
                    reason=f"Sector {new_sector} exposure {sector_total:.1%} > max {self.MAX_SECTOR_EXPOSURE:.0%}",
                    current_exposure=current_exposure,
                    max_exposure=self.MAX_TOTAL_EXPOSURE,
                    position_count=position_count,
                    max_positions=self.MAX_POSITIONS,
                )

        # Drawdown check
        if self.drawdown_active:
            new_weight *= 0.5  # halve during drawdown

        return RiskCheck(
            passed=True,
            reason="OK",
            current_exposure=current_exposure,
            max_exposure=self.MAX_TOTAL_EXPOSURE,
            position_count=position_count,
            max_positions=self.MAX_POSITIONS,
        )

    def set_drawdown(self, current_drawdown: float) -> bool:
        """Update drawdown state. Returns True if halt triggered."""
        if current_drawdown >= self.DRAWDOWN_HALT_THRESHOLD:
            self.drawdown_active = True
            return True
        self.drawdown_active = False
        return False
