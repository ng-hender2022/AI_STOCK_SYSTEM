"""
Meta Builder
Reads expert_signals from signals.db, normalizes scores,
computes group averages, alignment/conflict scores.

Output: meta_features row per symbol per date.
"""

import sqlite3
import json
from dataclasses import dataclass, field
from pathlib import Path

# Expert groups — must match config.py
EXPERT_GROUPS = {
    "TREND":      ["V4I", "V4MA", "V4ADX"],
    "MOMENTUM":   ["V4MACD", "V4RSI", "V4STO"],
    "VOLUME":     ["V4V", "V4OBV"],
    "VOLATILITY": ["V4ATR", "V4BB"],
    "STRUCTURE":  ["V4P", "V4CANDLE", "V4PIVOT", "V4SR", "V4TREND_PATTERN"],
    "CONTEXT":    ["V4BR", "V4RS", "V4REG", "V4S", "V4LIQ"],
}

# Experts with 0-100 scale (need different normalization)
SCALE_0_100 = {"V4RSI", "V4STO"}
# Experts with 0-4 scale (direction-neutral)
SCALE_0_4 = {"V4ADX", "V4ATR"}

ALL_EXPERT_IDS = sorted(set(
    eid for group in EXPERT_GROUPS.values() for eid in group
))


def _normalize_score(expert_id: str, primary_score: float) -> float:
    """
    Normalize expert score to -1..+1 range for cross-expert comparison.
    - Standard experts (-4..+4): score / 4
    - RSI/STO (0..100): (score - 50) / 50
    - ADX/ATR (0..4): score / 4 (stays 0..1, no negative)
    """
    if expert_id in SCALE_0_100:
        return (primary_score - 50.0) / 50.0
    elif expert_id in SCALE_0_4:
        return primary_score / 4.0
    else:
        return primary_score / 4.0


@dataclass
class MetaFeatures:
    """Aggregated meta features for 1 symbol, 1 date."""
    symbol: str
    date: str
    snapshot_time: str = "EOD"

    # Expert counts
    bullish_expert_count: int = 0
    bearish_expert_count: int = 0
    neutral_expert_count: int = 0

    # Normalized scores per expert (dict for flexibility)
    expert_norms: dict = field(default_factory=dict)

    # Group scores (average of normalized scores in each group)
    avg_score: float = 0.0
    trend_group_score: float = 0.0
    momentum_group_score: float = 0.0
    volume_group_score: float = 0.0
    volatility_group_score: float = 0.0
    structure_group_score: float = 0.0
    context_group_score: float = 0.0

    # Conflict & alignment
    expert_conflict_score: float = 0.0   # 0=aligned, 1=max conflict
    expert_alignment_score: float = 0.0  # 0=no alignment, 1=perfect

    # Regime (from V4REG)
    regime_score: float = 0.0

    # Count of experts that contributed
    expert_count: int = 0


class MetaBuilder:
    """
    Build meta features from expert signals.

    Usage:
        builder = MetaBuilder(signals_db, market_db)
        meta = builder.build("FPT", "2014-07-29")
        batch = builder.build_all("2014-07-29")
    """

    def __init__(self, signals_db: str | Path, market_db: str | Path):
        self.signals_db = str(signals_db)
        self.market_db = str(market_db)

    def _connect_signals(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.signals_db, timeout=30)
        conn.row_factory = sqlite3.Row
        return conn

    def _connect_market(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.market_db, timeout=30)
        conn.row_factory = sqlite3.Row
        return conn

    def _fetch_expert_signals(
        self, conn: sqlite3.Connection, symbol: str, date: str
    ) -> dict[str, dict]:
        """Fetch all expert signals for a symbol on a date."""
        rows = conn.execute(
            """SELECT expert_id, primary_score, secondary_score,
                      signal_code, signal_quality, metadata_json
               FROM expert_signals
               WHERE symbol=? AND date=? AND snapshot_time='EOD'""",
            (symbol, date),
        ).fetchall()

        result = {}
        for r in rows:
            meta = {}
            if r["metadata_json"]:
                try:
                    meta = json.loads(r["metadata_json"])
                except json.JSONDecodeError:
                    pass
            result[r["expert_id"]] = {
                "primary_score": r["primary_score"],
                "secondary_score": r["secondary_score"],
                "signal_code": r["signal_code"],
                "signal_quality": r["signal_quality"],
                "metadata": meta,
            }
        return result

    def _fetch_regime(self, date: str) -> float:
        """Fetch regime score from market.db."""
        conn = self._connect_market()
        try:
            row = conn.execute(
                "SELECT regime_score FROM market_regime WHERE date=? AND snapshot_time='EOD'",
                (date,),
            ).fetchone()
            return float(row["regime_score"]) if row else 0.0
        finally:
            conn.close()

    def build(self, symbol: str, date: str) -> MetaFeatures:
        """Build meta features for 1 symbol on 1 date."""
        conn = self._connect_signals()
        try:
            signals = self._fetch_expert_signals(conn, symbol, date)
        finally:
            conn.close()

        meta = MetaFeatures(symbol=symbol, date=date)

        if not signals:
            return meta

        # Normalize all scores
        norms = {}
        for eid, sig in signals.items():
            norm = _normalize_score(eid, sig["primary_score"])
            norms[eid] = norm

        meta.expert_norms = norms
        meta.expert_count = len(norms)

        # Bullish / bearish / neutral counts
        for norm in norms.values():
            if norm > 0.05:
                meta.bullish_expert_count += 1
            elif norm < -0.05:
                meta.bearish_expert_count += 1
            else:
                meta.neutral_expert_count += 1

        # Average normalized score
        if norms:
            meta.avg_score = sum(norms.values()) / len(norms)

        # Group scores
        meta.trend_group_score = self._group_avg(norms, "TREND")
        meta.momentum_group_score = self._group_avg(norms, "MOMENTUM")
        meta.volume_group_score = self._group_avg(norms, "VOLUME")
        meta.volatility_group_score = self._group_avg(norms, "VOLATILITY")
        meta.structure_group_score = self._group_avg(norms, "STRUCTURE")
        meta.context_group_score = self._group_avg(norms, "CONTEXT")

        # Conflict & alignment
        from .conflict_detector import ConflictDetector
        detector = ConflictDetector()
        meta.expert_conflict_score = detector.compute_conflict_score(norms)
        meta.expert_alignment_score = detector.compute_alignment_score(norms)

        # Regime
        meta.regime_score = self._fetch_regime(date)

        return meta

    def build_all(
        self, date: str, symbols: list[str] | None = None
    ) -> list[MetaFeatures]:
        """Build meta features for all symbols on a date."""
        conn = self._connect_signals()
        try:
            if symbols is None:
                rows = conn.execute(
                    "SELECT DISTINCT symbol FROM expert_signals WHERE date=?",
                    (date,),
                ).fetchall()
                symbols = [r["symbol"] for r in rows]
        finally:
            conn.close()

        return [self.build(sym, date) for sym in symbols]

    @staticmethod
    def _group_avg(norms: dict[str, float], group_name: str) -> float:
        """Average normalized score for a group."""
        group_ids = EXPERT_GROUPS.get(group_name, [])
        values = [norms[eid] for eid in group_ids if eid in norms]
        return sum(values) / len(values) if values else 0.0
