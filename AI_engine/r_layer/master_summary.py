"""
Master Summary Layer
Collects R0-R5 outputs, computes aggregate and summary fields.
Official research output schema — X1 reads from here.

Writes to: models.db → master_summary table
"""

import sqlite3
import numpy as np
from pathlib import Path
from dataclasses import dataclass


@dataclass
class SummaryRow:
    """Master Summary for 1 symbol, 1 date."""
    symbol: str
    date: str

    # Raw R scores
    r0_score: float | None = None
    r1_score: float | None = None
    r2_score: float | None = None
    r3_score: float | None = None
    r4_score: float | None = None
    r5_score: float | None = None

    # Ensemble
    ensemble_score: float | None = None
    ensemble_confidence: float | None = None
    ensemble_direction: int | None = None

    # Aggregates
    agg_avg_score: float = 0.0
    agg_median_score: float = 0.0
    agg_dispersion: float = 0.0        # std of available R scores
    agg_agreement_score: float = 0.0    # 0=disagree, 1=all agree on direction
    agg_bullish_model_count: int = 0
    agg_bearish_model_count: int = 0
    agg_neutral_model_count: int = 0
    agg_available_models: int = 0

    # Summary
    summary_direction: int = 0          # -1 / 0 / +1
    summary_strength: float = 0.0       # 0..4 (absolute strength)


class MasterSummary:
    """
    Collect R0-R5 predictions and compute Master Summary.

    Usage:
        ms = MasterSummary(models_db)
        stats = ms.compute("2014-07-29")
        row = ms.get_summary("FPT", "2014-07-29")
    """

    DIRECTION_THRESHOLD = 0.5
    R_MODELS = ["r0", "r1", "r2", "r3", "r4", "r5"]

    def __init__(self, models_db: str | Path):
        self.models_db = str(models_db)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.models_db, timeout=30)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.row_factory = sqlite3.Row
        return conn

    def _ensure_table(self, conn: sqlite3.Connection) -> None:
        """Create master_summary table if not exists."""
        conn.execute("""
            CREATE TABLE IF NOT EXISTS master_summary (
                symbol              TEXT NOT NULL,
                date                DATE NOT NULL,
                snapshot_time       TEXT DEFAULT 'EOD',

                -- Raw R scores
                r0_score            REAL,
                r1_score            REAL,
                r2_score            REAL,
                r3_score            REAL,
                r4_score            REAL,
                r5_score            REAL,

                -- Ensemble
                ensemble_score      REAL,
                ensemble_confidence REAL,
                ensemble_direction  INTEGER,

                -- Aggregates
                agg_avg_score       REAL,
                agg_median_score    REAL,
                agg_dispersion      REAL,
                agg_agreement_score REAL,
                agg_bullish_model_count  INTEGER,
                agg_bearish_model_count  INTEGER,
                agg_neutral_model_count  INTEGER,
                agg_available_models     INTEGER,

                -- Summary
                summary_direction   INTEGER,
                summary_strength    REAL,

                created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (symbol, date, snapshot_time)
            )
        """)

    def compute(self, date: str) -> dict:
        """
        Compute Master Summary for all symbols on a date.
        Reads r_predictions, computes aggregates, writes master_summary.

        Returns:
            dict with stats
        """
        conn = self._connect()
        self._ensure_table(conn)

        rows = conn.execute(
            "SELECT * FROM r_predictions WHERE date=? AND snapshot_time='EOD'",
            (date,),
        ).fetchall()

        if not rows:
            conn.close()
            return {"date": date, "symbols": 0}

        written = 0
        for row in rows:
            summary = self._build_summary(row, date)
            self._write_summary(conn, summary)
            written += 1

        conn.commit()
        conn.close()
        return {"date": date, "symbols": written}

    def _build_summary(self, row: sqlite3.Row, date: str) -> SummaryRow:
        """Build SummaryRow from r_predictions row."""
        s = SummaryRow(symbol=row["symbol"], date=date)

        # Collect available R scores
        scores = {}
        for rid in self.R_MODELS:
            col = f"{rid}_score"
            val = row[col] if col in row.keys() else None
            setattr(s, col, val)
            if val is not None:
                scores[rid] = float(val)

        # Ensemble from r_predictions
        s.ensemble_score = float(row["ensemble_score"]) if row["ensemble_score"] is not None else None
        s.ensemble_confidence = float(row["ensemble_confidence"]) if row["ensemble_confidence"] is not None else None
        s.ensemble_direction = int(row["ensemble_direction"]) if row["ensemble_direction"] is not None else None

        if not scores:
            return s

        vals = list(scores.values())
        s.agg_available_models = len(vals)

        # Aggregates
        s.agg_avg_score = float(np.mean(vals))
        s.agg_median_score = float(np.median(vals))
        s.agg_dispersion = float(np.std(vals)) if len(vals) > 1 else 0.0

        # Direction counts
        for v in vals:
            if v > self.DIRECTION_THRESHOLD:
                s.agg_bullish_model_count += 1
            elif v < -self.DIRECTION_THRESHOLD:
                s.agg_bearish_model_count += 1
            else:
                s.agg_neutral_model_count += 1

        # Agreement: proportion of models agreeing on majority direction
        max_agree = max(s.agg_bullish_model_count, s.agg_bearish_model_count, s.agg_neutral_model_count)
        s.agg_agreement_score = max_agree / len(vals) if vals else 0.0

        # Summary direction
        if s.agg_avg_score > self.DIRECTION_THRESHOLD:
            s.summary_direction = 1
        elif s.agg_avg_score < -self.DIRECTION_THRESHOLD:
            s.summary_direction = -1
        else:
            s.summary_direction = 0

        # Summary strength: absolute avg, 0..4
        s.summary_strength = min(4.0, abs(s.agg_avg_score))

        return s

    def _write_summary(self, conn: sqlite3.Connection, s: SummaryRow) -> None:
        """Write summary row to master_summary table."""
        conn.execute(
            """INSERT OR REPLACE INTO master_summary (
                symbol, date, snapshot_time,
                r0_score, r1_score, r2_score, r3_score, r4_score, r5_score,
                ensemble_score, ensemble_confidence, ensemble_direction,
                agg_avg_score, agg_median_score, agg_dispersion,
                agg_agreement_score,
                agg_bullish_model_count, agg_bearish_model_count,
                agg_neutral_model_count, agg_available_models,
                summary_direction, summary_strength
            ) VALUES (?,?,'EOD',?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                s.symbol, s.date,
                s.r0_score, s.r1_score, s.r2_score,
                s.r3_score, s.r4_score, s.r5_score,
                s.ensemble_score, s.ensemble_confidence, s.ensemble_direction,
                round(s.agg_avg_score, 4), round(s.agg_median_score, 4),
                round(s.agg_dispersion, 4), round(s.agg_agreement_score, 4),
                s.agg_bullish_model_count, s.agg_bearish_model_count,
                s.agg_neutral_model_count, s.agg_available_models,
                s.summary_direction, round(s.summary_strength, 4),
            ),
        )

    def get_summary(self, symbol: str, date: str) -> SummaryRow | None:
        """Get computed summary for a symbol on a date."""
        conn = self._connect()
        self._ensure_table(conn)

        row = conn.execute(
            "SELECT * FROM master_summary WHERE symbol=? AND date=? AND snapshot_time='EOD'",
            (symbol, date),
        ).fetchone()
        conn.close()

        if not row:
            return None

        s = SummaryRow(symbol=symbol, date=date)
        for col in ["r0_score", "r1_score", "r2_score", "r3_score", "r4_score", "r5_score",
                     "ensemble_score", "ensemble_confidence"]:
            setattr(s, col, float(row[col]) if row[col] is not None else None)

        s.ensemble_direction = int(row["ensemble_direction"]) if row["ensemble_direction"] is not None else None
        s.agg_avg_score = float(row["agg_avg_score"]) if row["agg_avg_score"] else 0.0
        s.agg_median_score = float(row["agg_median_score"]) if row["agg_median_score"] else 0.0
        s.agg_dispersion = float(row["agg_dispersion"]) if row["agg_dispersion"] else 0.0
        s.agg_agreement_score = float(row["agg_agreement_score"]) if row["agg_agreement_score"] else 0.0
        s.agg_bullish_model_count = int(row["agg_bullish_model_count"]) if row["agg_bullish_model_count"] else 0
        s.agg_bearish_model_count = int(row["agg_bearish_model_count"]) if row["agg_bearish_model_count"] else 0
        s.agg_neutral_model_count = int(row["agg_neutral_model_count"]) if row["agg_neutral_model_count"] else 0
        s.agg_available_models = int(row["agg_available_models"]) if row["agg_available_models"] else 0
        s.summary_direction = int(row["summary_direction"]) if row["summary_direction"] else 0
        s.summary_strength = float(row["summary_strength"]) if row["summary_strength"] else 0.0

        return s

    def get_all_summaries(self, date: str) -> list[SummaryRow]:
        """Get all summaries for a date."""
        conn = self._connect()
        self._ensure_table(conn)

        rows = conn.execute(
            "SELECT DISTINCT symbol FROM master_summary WHERE date=? AND snapshot_time='EOD' ORDER BY symbol",
            (date,),
        ).fetchall()
        conn.close()

        return [self.get_summary(r["symbol"], date) for r in rows if self.get_summary(r["symbol"], date)]
