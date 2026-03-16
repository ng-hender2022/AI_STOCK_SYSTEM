"""
Output Writer
Writes X1 decisions to models.db x1_decisions table.
"""

import sqlite3
from pathlib import Path

from .portfolio_engine import Portfolio


class OutputWriter:
    """
    Write portfolio decisions to models.db.

    Usage:
        writer = OutputWriter(models_db)
        writer.write(portfolio)
    """

    def __init__(self, models_db: str | Path):
        self.models_db = str(models_db)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.models_db, timeout=30)
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def _ensure_table(self, conn: sqlite3.Connection) -> None:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS x1_decisions (
                symbol          TEXT NOT NULL,
                date            DATE NOT NULL,
                snapshot_time   TEXT DEFAULT 'EOD',
                action          TEXT NOT NULL,
                weight          REAL,
                score           REAL,
                confidence      REAL,
                strength        TEXT,
                reason          TEXT,
                risk_passed     INTEGER,
                created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (symbol, date, snapshot_time)
            )
        """)

    def write(self, portfolio: Portfolio) -> dict:
        """Write portfolio entries to DB. Returns stats."""
        conn = self._connect()
        self._ensure_table(conn)

        written = 0
        for entry in portfolio.entries:
            conn.execute(
                """INSERT OR REPLACE INTO x1_decisions
                   (symbol, date, snapshot_time, action, weight, score,
                    confidence, strength, reason, risk_passed)
                   VALUES (?, ?, 'EOD', ?, ?, ?, ?, ?, ?, ?)""",
                (
                    entry.symbol, entry.date, entry.action,
                    round(entry.weight, 4), round(entry.score, 4),
                    round(entry.confidence, 4), entry.strength,
                    entry.reason, 1 if entry.risk_passed else 0,
                ),
            )
            written += 1

        conn.commit()
        conn.close()

        return {
            "date": portfolio.date,
            "written": written,
            "buys": sum(1 for e in portfolio.entries if e.action == "BUY"),
            "sells": sum(1 for e in portfolio.entries if e.action == "SELL"),
            "holds": sum(1 for e in portfolio.entries if e.action == "HOLD"),
            "total_buy_weight": round(portfolio.total_buy_weight, 4),
            "cash_weight": round(portfolio.cash_weight, 4),
        }
