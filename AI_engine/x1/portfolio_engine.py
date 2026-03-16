"""
Portfolio Engine
Combines decisions + position sizing + risk checks into final portfolio.
"""

from dataclasses import dataclass, field

from .decision_engine import DecisionEngine, Decision
from .position_sizer import PositionSizer, PositionSize
from .risk_manager import RiskManager, RiskCheck
from .symbol_evaluator import SymbolEvaluator


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
    route: str = "NORMAL"
    position_multiplier: float = 1.0


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
        self.symbol_evaluator = SymbolEvaluator(market_db)
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

        # Evaluate all symbols for routing
        eval_map = {}
        syms = list(set(d.symbol for d in decisions))
        evals = self.symbol_evaluator.evaluate_all(syms, date)
        for ev in evals:
            eval_map[ev.symbol] = ev

        # Sort by absolute score (strongest signals first)
        decisions.sort(key=lambda d: abs(d.score), reverse=True)

        for dec in decisions:
            ev = eval_map.get(dec.symbol)
            route = ev.route if ev else "NORMAL"
            pos_mult = ev.position_multiplier if ev else 1.0

            # AVOID route: force HOLD
            if route == "AVOID" and dec.action == "BUY":
                portfolio.total_hold_count += 1
                portfolio.entries.append(PortfolioEntry(
                    symbol=dec.symbol, date=date, action="HOLD",
                    weight=0.0, score=dec.score, confidence=dec.confidence,
                    strength=dec.strength,
                    reason=f"Symbol AVOID: {ev.route_reason if ev else 'no eval'}",
                    risk_passed=False, route=route, position_multiplier=0.0,
                ))
                continue

            if dec.action == "HOLD":
                portfolio.total_hold_count += 1
                portfolio.entries.append(PortfolioEntry(
                    symbol=dec.symbol, date=date, action="HOLD",
                    weight=0.0, score=dec.score, confidence=dec.confidence,
                    strength=dec.strength, reason=dec.reason, risk_passed=True,
                    route=route, position_multiplier=pos_mult,
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

            # Apply symbol routing multiplier
            adjusted_weight = ps.weight * pos_mult

            if adjusted_weight <= 0:
                portfolio.entries.append(PortfolioEntry(
                    symbol=dec.symbol, date=date, action=dec.action,
                    weight=0.0, score=dec.score, confidence=dec.confidence,
                    strength=dec.strength, reason=f"Zero weight (route={route})",
                    risk_passed=False, route=route, position_multiplier=pos_mult,
                ))
                continue

            # Risk check (for BUY only)
            if dec.action == "BUY":
                risk_check = self.risk_manager.check(
                    current_positions, dec.symbol, adjusted_weight,
                )
                if not risk_check.passed:
                    portfolio.entries.append(PortfolioEntry(
                        symbol=dec.symbol, date=date, action="HOLD",
                        weight=0.0, score=dec.score, confidence=dec.confidence,
                        strength=dec.strength,
                        reason=f"Risk blocked: {risk_check.reason}",
                        risk_passed=False, route=route, position_multiplier=pos_mult,
                    ))
                    continue

                current_positions[dec.symbol] = adjusted_weight
                portfolio.total_buy_weight += adjusted_weight

            elif dec.action == "SELL":
                portfolio.total_sell_count += 1

            portfolio.entries.append(PortfolioEntry(
                symbol=dec.symbol, date=date, action=dec.action,
                weight=round(adjusted_weight, 4), score=dec.score,
                confidence=dec.confidence, strength=dec.strength,
                reason=dec.reason, risk_passed=True,
                route=route, position_multiplier=pos_mult,
            ))

        portfolio.cash_weight = max(0.0, 1.0 - portfolio.total_buy_weight)
        return portfolio
