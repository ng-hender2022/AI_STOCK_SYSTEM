"""
Feature Matrix Writer
Writes meta_features to signals.db.
Also writes expert_conflicts when detected.
"""

import sqlite3
import json
from pathlib import Path

from .meta_builder import MetaBuilder, MetaFeatures
from .conflict_detector import ConflictDetector


class FeatureMatrixWriter:
    """
    End-to-end Meta Layer pipeline:
    Read expert signals → compute meta → detect conflicts → write to DB.

    Usage:
        writer = FeatureMatrixWriter(signals_db, market_db)
        stats = writer.run("2014-07-29")
        stats = writer.run_range("2014-03-06", "2014-07-29")
    """

    def __init__(self, signals_db: str | Path, market_db: str | Path):
        self.signals_db = str(signals_db)
        self.market_db = str(market_db)
        self.meta_builder = MetaBuilder(signals_db, market_db)
        self.conflict_detector = ConflictDetector()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.signals_db, timeout=30)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.row_factory = sqlite3.Row
        return conn

    def _write_meta(self, conn: sqlite3.Connection, meta: MetaFeatures) -> None:
        """Write meta_features row."""
        conn.execute(
            """INSERT OR REPLACE INTO meta_features (
                symbol, date, snapshot_time,
                bullish_expert_count, bearish_expert_count, neutral_expert_count,
                avg_score,
                trend_group_score, momentum_group_score,
                volume_group_score, volatility_group_score,
                structure_group_score, context_group_score,
                expert_conflict_score, expert_alignment_score,
                regime_score
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                meta.symbol, meta.date, meta.snapshot_time,
                meta.bullish_expert_count, meta.bearish_expert_count,
                meta.neutral_expert_count,
                round(meta.avg_score, 6),
                round(meta.trend_group_score, 6),
                round(meta.momentum_group_score, 6),
                round(meta.volume_group_score, 6),
                round(meta.volatility_group_score, 6),
                round(meta.structure_group_score, 6),
                round(meta.context_group_score, 6),
                round(meta.expert_conflict_score, 6),
                round(meta.expert_alignment_score, 6),
                round(meta.regime_score, 6),
            ),
        )

    def _write_conflicts(
        self, conn: sqlite3.Connection, symbol: str, date: str,
        norms: dict[str, float]
    ) -> int:
        """Detect and write expert_conflicts rows. Returns count written."""
        pairs = self.conflict_detector.find_conflicting_pairs(norms)
        for c in pairs:
            conn.execute(
                """INSERT OR REPLACE INTO expert_conflicts
                   (symbol, date, snapshot_time, expert_a, expert_b,
                    conflict_type, severity, description)
                   VALUES (?, ?, 'EOD', ?, ?, ?, ?, ?)""",
                (
                    symbol, date,
                    c["expert_a"], c["expert_b"],
                    c["type"],
                    int(min(4, c["diff"] * 4)),  # severity 1-4
                    f"{c['expert_a']}={c['score_a']} vs {c['expert_b']}={c['score_b']}",
                ),
            )
        return len(pairs)

    def run(self, date: str, symbols: list[str] | None = None) -> dict:
        """
        Run Meta Layer for a single date.

        Returns:
            dict with stats: symbols, meta_written, conflicts_written
        """
        meta_list = self.meta_builder.build_all(date, symbols)

        conn = self._connect()
        try:
            meta_written = 0
            conflicts_written = 0

            for meta in meta_list:
                if meta.expert_count == 0:
                    continue
                self._write_meta(conn, meta)
                meta_written += 1

                conflicts_written += self._write_conflicts(
                    conn, meta.symbol, date, meta.expert_norms
                )

            conn.commit()
        finally:
            conn.close()

        return {
            "date": date,
            "symbols": len(meta_list),
            "meta_written": meta_written,
            "conflicts_written": conflicts_written,
        }

    def run_range(
        self, start_date: str, end_date: str,
        symbols: list[str] | None = None,
    ) -> dict:
        """Run Meta Layer for a date range."""
        # Get dates with expert signals
        conn = self._connect()
        rows = conn.execute(
            """SELECT DISTINCT date FROM expert_signals
               WHERE date >= ? AND date <= ? ORDER BY date""",
            (start_date, end_date),
        ).fetchall()
        conn.close()

        dates = [r["date"] for r in rows]
        total_stats = {
            "dates": len(dates),
            "meta_written": 0,
            "conflicts_written": 0,
        }

        for d in dates:
            stats = self.run(d, symbols)
            total_stats["meta_written"] += stats["meta_written"]
            total_stats["conflicts_written"] += stats["conflicts_written"]

        return total_stats

    def get_feature_vector(
        self, symbol: str, date: str
    ) -> dict | None:
        """
        Get the complete feature vector for R Layer input.
        Returns dict with 34 features (20 norm scores + 11 meta + 3 regime).
        """
        meta = self.meta_builder.build(symbol, date)
        if meta.expert_count == 0:
            return None

        vector = {}

        # 20 expert norm scores
        for eid in sorted(meta.expert_norms.keys()):
            vector[f"{eid.lower()}_norm"] = round(meta.expert_norms[eid], 6)

        # 11 meta features
        vector["avg_score"] = round(meta.avg_score, 6)
        vector["trend_group_score"] = round(meta.trend_group_score, 6)
        vector["momentum_group_score"] = round(meta.momentum_group_score, 6)
        vector["volume_group_score"] = round(meta.volume_group_score, 6)
        vector["volatility_group_score"] = round(meta.volatility_group_score, 6)
        vector["structure_group_score"] = round(meta.structure_group_score, 6)
        vector["context_group_score"] = round(meta.context_group_score, 6)
        vector["expert_conflict_score"] = round(meta.expert_conflict_score, 6)
        vector["expert_alignment_score"] = round(meta.expert_alignment_score, 6)
        vector["bullish_count"] = meta.bullish_expert_count
        vector["bearish_count"] = meta.bearish_expert_count

        # 3 regime scores (from market.db)
        conn = sqlite3.connect(self.market_db)
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT regime_score, volatility_score, liquidity_score FROM market_regime WHERE date=? AND snapshot_time='EOD'",
            (date,),
        ).fetchone()
        conn.close()

        if row:
            vector["regime_trend"] = float(row["regime_score"]) if row["regime_score"] else 0.0
            vector["regime_vol"] = float(row["volatility_score"]) if row["volatility_score"] else 0.0
            vector["regime_liq"] = float(row["liquidity_score"]) if row["liquidity_score"] else 0.0
        else:
            vector["regime_trend"] = 0.0
            vector["regime_vol"] = 0.0
            vector["regime_liq"] = 0.0

        return vector
