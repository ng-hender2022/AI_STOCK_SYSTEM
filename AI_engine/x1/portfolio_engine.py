"""
Portfolio Engine
Combines decisions + position sizing + risk checks into final portfolio.
"""

from dataclasses import dataclass, field

from .decision_engine import DecisionEngine, Decision
from .position_sizer import PositionSizer, PositionSize
from .risk_manager import RiskManager, RiskCheck


@dataclass
class PortfolioEntry:
    symbol: str
    date: str
    action: str
    weight: float
    score: float
    confidence: float
    strength: str
    reason: str
    risk_passed: bool


@dataclass
class Portfolio:
    date: str
    entries: list[PortfolioEntry] = field(default_factory=list)
    total_buy_weight: float = 0.0
    total_sell_count: int = 0
    total_hold_count: int = 0
    cash_weight: float = 1.0


class PortfolioEngine:
    """
    Build portfolio from decisions.

    Usage:
        pe = PortfolioEngine(models_db, market_db)
        portfolio = pe.build("2025-01-15")
    """

    def __init__(self, models_db, market_db):
        self.decision_engine = DecisionEngine(models_db, market_db)
        self.position_sizer = PositionSizer()
        self.risk_manager = RiskManager()
        self.market_db = market_db

    def _get_regime(self, date: str) -> dict:
        return self.decision_engine._get_regime(date)

    def build(self, date: str) -> Portfolio:
        """Build complete portfolio for a date."""
        decisions = self.decision_engine.decide(date)
        if not decisions:
            return Portfolio(date=date)

        regime = self._get_regime(date)
        portfolio = Portfolio(date=date)
        current_positions: dict[str, float] = {}

        # Sort by absolute score (strongest signals first)
        decisions.sort(key=lambda d: abs(d.score), reverse=True)

        for dec in decisions:
            if dec.action == "HOLD":
                portfolio.total_hold_count += 1
                portfolio.entries.append(PortfolioEntry(
                    symbol=dec.symbol, date=date, action="HOLD",
                    weight=0.0, score=dec.score, confidence=dec.confidence,
                    strength=dec.strength, reason=dec.reason, risk_passed=True,
                ))
                continue

            # Size position
            ps = self.position_sizer.size(
                symbol=dec.symbol, date=date,
                action=dec.action, strength=dec.strength,
                confidence=dec.confidence,
                regime_trend=regime["trend"],
                regime_vol=regime["vol"],
            )

            if ps.weight <= 0:
                portfolio.entries.append(PortfolioEntry(
                    symbol=dec.symbol, date=date, action=dec.action,
                    weight=0.0, score=dec.score, confidence=dec.confidence,
                    strength=dec.strength, reason="Zero weight", risk_passed=False,
                ))
                continue

            # Risk check (for BUY only — SELL doesn't add exposure)
            if dec.action == "BUY":
                risk_check = self.risk_manager.check(
                    current_positions, dec.symbol, ps.weight,
                )
                if not risk_check.passed:
                    portfolio.entries.append(PortfolioEntry(
                        symbol=dec.symbol, date=date, action="HOLD",
                        weight=0.0, score=dec.score, confidence=dec.confidence,
                        strength=dec.strength,
                        reason=f"Risk blocked: {risk_check.reason}",
                        risk_passed=False,
                    ))
                    continue

                current_positions[dec.symbol] = ps.weight
                portfolio.total_buy_weight += ps.weight

            elif dec.action == "SELL":
                portfolio.total_sell_count += 1

            portfolio.entries.append(PortfolioEntry(
                symbol=dec.symbol, date=date, action=dec.action,
                weight=ps.weight, score=dec.score, confidence=dec.confidence,
                strength=dec.strength, reason=dec.reason, risk_passed=True,
            ))

        portfolio.cash_weight = max(0.0, 1.0 - portfolio.total_buy_weight)
        return portfolio
