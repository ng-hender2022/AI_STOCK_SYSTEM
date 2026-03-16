"""
Symbol Evaluator
Evaluates each symbol's recent trend and condition over 20 trading days.
Routes symbols to appropriate strategy (momentum / mean-reversion / avoid).

Used by X1 to adjust position sizing and filter based on symbol state.
"""

import sqlite3
from dataclasses import dataclass
from pathlib import Path

import numpy as np


@dataclass
class SymbolEvaluation:
    symbol: str
    date: str

    # Trend metrics (20-day)
    return_20d: float = 0.0         # 20-day return
    return_5d: float = 0.0          # 5-day return
    trend_direction: str = "FLAT"   # UP / DOWN / FLAT
    trend_strength: float = 0.0     # 0..1 (R-squared of linear fit)
    trend_slope: float = 0.0        # daily slope normalized

    # Volatility
    volatility_20d: float = 0.0     # std of daily returns
    avg_volume_ratio: float = 1.0   # recent 5d vol / 20d vol

    # Routing
    route: str = "NORMAL"           # MOMENTUM / MEAN_REVERSION / NORMAL
    route_reason: str = ""
    position_multiplier: float = 1.0  # from trend routing

    # Precision-based sizing (from symbol_phase_metrics)
    historical_precision: float = 0.5  # 0..1
    precision_multiplier: float = 1.0  # applied on top of position_multiplier

    has_sufficient_data: bool = False


# Routing thresholds
MOMENTUM_RETURN = 0.05          # >5% in 20d = momentum candidate
MOMENTUM_R2 = 0.3              # trend must be consistent
MEAN_REVERSION_RETURN = -0.10  # <-10% in 20d = potential bounce
MEAN_REVERSION_VOL = 0.03     # high vol = uncertain
AVOID_VOL = 0.05              # extreme vol = avoid
AVOID_VOLUME_DRY = 0.3        # volume ratio < 0.3 = no liquidity
MIN_HISTORY = 25               # need 25 bars


PRECISION_TIERS = [
    (0.75, 1.2),   # precision >= 75% -> 1.2x
    (0.60, 1.0),   # 60-75% -> 1.0x
    (0.50, 0.85),  # 50-60% -> 0.85x
    (0.00, 0.70),  # < 50% -> 0.7x
]


def _precision_multiplier(precision: float) -> float:
    """Map historical precision to position multiplier."""
    for threshold, mult in PRECISION_TIERS:
        if precision >= threshold:
            return mult
    return 0.70


class SymbolEvaluator:
    """
    Evaluate symbol trend and route to strategy.
    Loads historical precision from models.db symbol_phase_metrics.

    Usage:
        evaluator = SymbolEvaluator(market_db, models_db)
        ev = evaluator.evaluate("FPT", "2026-03-13")
    """

    def __init__(self, market_db: str | Path, models_db: str | Path | None = None):
        self.market_db = str(market_db)
        self.models_db = str(models_db) if models_db else None
        self._precision_cache = self._load_precision()

    def _load_precision(self) -> dict[str, float]:
        """Load latest ensemble precision per symbol from symbol_phase_metrics."""
        if not self.models_db:
            return {}
        try:
            conn = sqlite3.connect(self.models_db, timeout=10)
            conn.row_factory = sqlite3.Row
            # Get ensemble precision from the most recent phase (ALL_OOS or latest year)
            rows = conn.execute("""
                SELECT symbol, precision_t10, buy_signals
                FROM symbol_phase_metrics
                WHERE model_id = 'ENSEMBLE' AND buy_signals >= 3
                ORDER BY phase DESC
            """).fetchall()
            conn.close()

            # Keep first (latest phase) per symbol
            result = {}
            for r in rows:
                sym = r["symbol"]
                if sym not in result:
                    result[sym] = float(r["precision_t10"])
            return result
        except Exception:
            return {}

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.market_db, timeout=30)
        conn.row_factory = sqlite3.Row
        return conn

    def evaluate(self, symbol: str, date: str) -> SymbolEvaluation:
        """Evaluate a single symbol. Uses data < date (no leakage)."""
        ev = SymbolEvaluation(symbol=symbol, date=date)

        conn = self._connect()
        rows = conn.execute(
            "SELECT date, close, volume FROM prices_daily "
            "WHERE symbol=? AND date<? ORDER BY date DESC LIMIT ?",
            (symbol, date, MIN_HISTORY + 5),
        ).fetchall()
        conn.close()

        if len(rows) < MIN_HISTORY:
            ev.route = "AVOID"
            ev.route_reason = "insufficient data"
            ev.position_multiplier = 0.0
            return ev

        # Reverse to chronological
        rows = list(reversed(rows))
        closes = np.array([float(r["close"]) for r in rows])
        volumes = np.array([float(r["volume"]) for r in rows if r["volume"]])

        n = len(closes)
        ev.has_sufficient_data = True

        # Returns
        if n >= 21:
            ev.return_20d = (closes[-1] - closes[-21]) / (closes[-21] + 1e-9)
        if n >= 6:
            ev.return_5d = (closes[-1] - closes[-6]) / (closes[-6] + 1e-9)

        # Daily returns for volatility
        if n >= 22:
            window = closes[-21:]
            daily_rets = np.diff(window) / (window[:-1] + 1e-9)
        else:
            daily_rets = np.diff(closes) / (closes[:-1] + 1e-9)
        ev.volatility_20d = float(np.std(daily_rets)) if len(daily_rets) > 1 else 0.0

        # Trend: linear regression on last 20 closes
        lookback = min(20, n)
        y = closes[-lookback:]
        x = np.arange(lookback)
        if lookback >= 5:
            slope, intercept = np.polyfit(x, y, 1)
            y_pred = slope * x + intercept
            ss_res = np.sum((y - y_pred) ** 2)
            ss_tot = np.sum((y - np.mean(y)) ** 2)
            r_squared = 1 - ss_res / (ss_tot + 1e-9)

            ev.trend_slope = float(slope / (np.mean(y) + 1e-9))  # normalized
            ev.trend_strength = float(max(0, min(1, r_squared)))

            if ev.trend_slope > 0.001 and ev.trend_strength > 0.1:
                ev.trend_direction = "UP"
            elif ev.trend_slope < -0.001 and ev.trend_strength > 0.1:
                ev.trend_direction = "DOWN"
            else:
                ev.trend_direction = "FLAT"

        # Volume ratio
        if len(volumes) >= 20:
            vol_5d = np.mean(volumes[-5:])
            vol_20d = np.mean(volumes[-20:])
            ev.avg_volume_ratio = float(vol_5d / (vol_20d + 1e-9))

        # Routing logic (trend-based)
        ev.route, ev.route_reason, ev.position_multiplier = self._route(ev)

        # Precision-based sizing (from historical data)
        ev.historical_precision = self._precision_cache.get(symbol, 0.5)
        ev.precision_multiplier = _precision_multiplier(ev.historical_precision)

        return ev

    def evaluate_all(
        self, symbols: list[str], date: str
    ) -> list[SymbolEvaluation]:
        """Evaluate all symbols."""
        return [self.evaluate(sym, date) for sym in symbols]

    @staticmethod
    def _route(ev: SymbolEvaluation) -> tuple[str, str, float]:
        """Determine routing based on trend evaluation. No hard AVOID."""
        # Extreme volatility: soft penalty (0.5x), not blocked
        if ev.volatility_20d >= AVOID_VOL:
            return "NORMAL", f"high vol {ev.volatility_20d:.3f} (0.5x)", 0.5

        # Volume dried up: soft penalty (0.3x)
        if ev.avg_volume_ratio < AVOID_VOLUME_DRY:
            return "NORMAL", f"low volume {ev.avg_volume_ratio:.2f} (0.3x)", 0.3

        # MOMENTUM: strong uptrend with consistency
        if (ev.return_20d >= MOMENTUM_RETURN
                and ev.trend_strength >= MOMENTUM_R2
                and ev.trend_direction == "UP"):
            mult = min(1.5, 1.0 + ev.trend_strength)
            return "MOMENTUM", f"uptrend {ev.return_20d:+.1%} R2={ev.trend_strength:.2f}", mult

        # MEAN_REVERSION: sharp decline, potential bounce
        if (ev.return_20d <= MEAN_REVERSION_RETURN
                and ev.volatility_20d < MEAN_REVERSION_VOL):
            return "MEAN_REVERSION", f"oversold {ev.return_20d:+.1%}", 0.7

        # NORMAL
        return "NORMAL", "no special condition", 1.0
