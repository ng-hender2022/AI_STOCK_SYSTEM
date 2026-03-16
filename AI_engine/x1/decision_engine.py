"""
X1 Decision Engine
Reads master_summary, applies regime filters and signal thresholds,
outputs BUY / SELL / HOLD per symbol.
"""

import sqlite3
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Decision:
    symbol: str
    date: str
    action: str             # BUY / SELL / HOLD
    score: float            # ensemble_score
    confidence: float       # ensemble_confidence
    strength: str           # STRONG / MODERATE / WEAK
    regime_trend: float     # r4_trend_regime_score
    regime_blocked: bool    # True if regime blocked entry
    reason: str             # human-readable reason


# Thresholds
STRONG_BUY_SCORE = 2.0
STRONG_BUY_CONFIDENCE = 0.7
MODERATE_BUY_SCORE = 1.0
MODERATE_BUY_CONFIDENCE = 0.55
STRONG_SELL_SCORE = -2.0
MODERATE_SELL_SCORE = -1.0
REGIME_BLOCK_THRESHOLD = -3.0   # block aggressive longs when regime <= -3
REGIME_BULL_THRESHOLD = 2.0     # allow larger risk when regime >= +2


class DecisionEngine:
    """
    Generate BUY/SELL/HOLD decisions from Master Summary.

    Usage:
        engine = DecisionEngine(models_db, market_db)
        decisions = engine.decide("2025-01-15")
        decision = engine.decide_symbol("FPT", "2025-01-15")
    """

    def __init__(self, models_db: str | Path, market_db: str | Path):
        self.models_db = str(models_db)
        self.market_db = str(market_db)

    def _connect_models(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.models_db, timeout=30)
        conn.row_factory = sqlite3.Row
        return conn

    def _get_regime(self, date: str) -> dict:
        """Get regime scores from market.db."""
        conn = sqlite3.connect(self.market_db, timeout=30)
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT regime_score, volatility_score, liquidity_score FROM market_regime WHERE date=? AND snapshot_time='EOD'",
            (date,),
        ).fetchone()
        conn.close()

        if row:
            return {
                "trend": float(row["regime_score"]) if row["regime_score"] is not None else 0.0,
                "vol": float(row["volatility_score"]) if row["volatility_score"] is not None else 0.0,
                "liq": float(row["liquidity_score"]) if row["liquidity_score"] is not None else 0.0,
            }
        return {"trend": 0.0, "vol": 0.0, "liq": 0.0}

    def _get_index_symbols(self) -> set[str]:
        """Get symbols that are indices (not tradable)."""
        conn = sqlite3.connect(self.market_db, timeout=30)
        cols = {row[1] for row in conn.execute("PRAGMA table_info(symbols_master)")}
        if "is_index" in cols:
            rows = conn.execute("SELECT symbol FROM symbols_master WHERE is_index=1").fetchall()
            result = {r[0] for r in rows}
        else:
            rows = conn.execute("SELECT symbol FROM symbols_master WHERE is_tradable=0").fetchall()
            result = {r[0] for r in rows}
        conn.close()
        return result

    def decide(self, date: str) -> list[Decision]:
        """Generate decisions for all symbols on a date."""
        conn = self._connect_models()

        # Check if master_summary exists
        tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
        if "master_summary" not in tables:
            conn.close()
            return []

        rows = conn.execute(
            "SELECT * FROM master_summary WHERE date=? AND snapshot_time='EOD'",
            (date,),
        ).fetchall()
        conn.close()

        if not rows:
            return []

        regime = self._get_regime(date)
        index_symbols = self._get_index_symbols()

        decisions = []
        for row in rows:
            d = self._decide_row(row, regime, index_symbols)
            decisions.append(d)

        return decisions

    def decide_symbol(self, symbol: str, date: str) -> Decision | None:
        """Generate decision for a single symbol."""
        conn = self._connect_models()
        tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
        if "master_summary" not in tables:
            conn.close()
            return None

        row = conn.execute(
            "SELECT * FROM master_summary WHERE symbol=? AND date=? AND snapshot_time='EOD'",
            (symbol, date),
        ).fetchone()
        conn.close()

        if not row:
            return None

        regime = self._get_regime(date)
        index_symbols = self._get_index_symbols()
        return self._decide_row(row, regime, index_symbols)

    def _decide_row(self, row: sqlite3.Row, regime: dict, index_symbols: set) -> Decision:
        """Core decision logic for one symbol."""
        symbol = row["symbol"]
        date = row["date"]
        score = float(row["ensemble_score"]) if row["ensemble_score"] is not None else 0.0
        confidence = float(row["ensemble_confidence"]) if row["ensemble_confidence"] is not None else 0.0
        regime_trend = regime["trend"]
        regime_vol = regime["vol"]

        # X1 does NOT trade indices
        if symbol in index_symbols:
            return Decision(
                symbol=symbol, date=date, action="HOLD", score=score,
                confidence=confidence, strength="NONE",
                regime_trend=regime_trend, regime_blocked=False,
                reason="Index symbol — not tradable",
            )

        # Regime block: if trend <= -3, block aggressive longs
        regime_blocked = False
        if regime_trend <= REGIME_BLOCK_THRESHOLD and score > 0:
            regime_blocked = True

        # Decision logic
        if score >= STRONG_BUY_SCORE and confidence >= STRONG_BUY_CONFIDENCE:
            if regime_blocked:
                return Decision(
                    symbol=symbol, date=date, action="HOLD", score=score,
                    confidence=confidence, strength="BLOCKED",
                    regime_trend=regime_trend, regime_blocked=True,
                    reason=f"Strong buy signal blocked by bear regime ({regime_trend})",
                )
            return Decision(
                symbol=symbol, date=date, action="BUY", score=score,
                confidence=confidence, strength="STRONG",
                regime_trend=regime_trend, regime_blocked=False,
                reason=f"Strong buy: score={score:.2f}, conf={confidence:.2f}",
            )

        elif score >= MODERATE_BUY_SCORE and confidence >= MODERATE_BUY_CONFIDENCE:
            if regime_blocked:
                return Decision(
                    symbol=symbol, date=date, action="HOLD", score=score,
                    confidence=confidence, strength="BLOCKED",
                    regime_trend=regime_trend, regime_blocked=True,
                    reason=f"Moderate buy blocked by bear regime ({regime_trend})",
                )
            return Decision(
                symbol=symbol, date=date, action="BUY", score=score,
                confidence=confidence, strength="MODERATE",
                regime_trend=regime_trend, regime_blocked=False,
                reason=f"Moderate buy: score={score:.2f}, conf={confidence:.2f}",
            )

        elif score <= STRONG_SELL_SCORE:
            return Decision(
                symbol=symbol, date=date, action="SELL", score=score,
                confidence=confidence, strength="STRONG",
                regime_trend=regime_trend, regime_blocked=False,
                reason=f"Strong sell: score={score:.2f}",
            )

        elif score <= MODERATE_SELL_SCORE:
            return Decision(
                symbol=symbol, date=date, action="SELL", score=score,
                confidence=confidence, strength="MODERATE",
                regime_trend=regime_trend, regime_blocked=False,
                reason=f"Moderate sell: score={score:.2f}",
            )

        else:
            return Decision(
                symbol=symbol, date=date, action="HOLD", score=score,
                confidence=confidence, strength="WEAK",
                regime_trend=regime_trend, regime_blocked=False,
                reason=f"No clear signal: score={score:.2f}",
            )
