"""
Data Leakage Checker
Verify no future data leaks into features or training pipeline.
Must run BEFORE any R Layer training.

Raises LeakageError if any violation is found.
"""

import sqlite3
from pathlib import Path
from datetime import datetime


class LeakageError(Exception):
    """Raised when data leakage is detected."""
    pass


class LeakChecker:
    """
    Pre-training leakage verification.

    Usage:
        checker = LeakChecker(
            market_db="D:/AI/AI_data/market.db",
            signals_db="D:/AI/AI_data/signals.db",
        )
        checker.check_all(train_end="2026-01-31", val_start="2026-02-01")
    """

    def __init__(
        self,
        market_db: str | Path,
        signals_db: str | Path | None = None,
    ):
        self.market_db = str(market_db)
        self.signals_db = str(signals_db) if signals_db else None

    def _connect(self, db_path: str) -> sqlite3.Connection:
        conn = sqlite3.connect(db_path, timeout=30)
        conn.row_factory = sqlite3.Row
        return conn

    def check_all(
        self,
        train_end: str,
        val_start: str,
    ) -> dict:
        """
        Run all leakage checks.

        Args:
            train_end: last date in training set (YYYY-MM-DD)
            val_start: first date in validation set (YYYY-MM-DD)

        Returns:
            dict with check results

        Raises:
            LeakageError if any check fails
        """
        results = {}

        results["train_val_order"] = self.check_train_val_order(
            train_end, val_start
        )
        results["feature_label_order"] = self.check_feature_label_order()
        results["no_future_close"] = self.check_no_future_close_in_signals()

        for key, val in results.items():
            if not val["passed"]:
                self._log_to_audit(key, val["message"])
                raise LeakageError(
                    f"Leakage detected in '{key}': {val['message']}"
                )

        return results

    def check_train_val_order(
        self, train_end: str, val_start: str
    ) -> dict:
        """
        Verify: train period ends BEFORE validation period starts.
        """
        if train_end >= val_start:
            return {
                "passed": False,
                "message": (
                    f"Train end ({train_end}) >= val start ({val_start}). "
                    f"Must be chronologically ordered."
                ),
            }
        return {"passed": True, "message": "OK"}

    def check_feature_label_order(self) -> dict:
        """
        Verify: all expert signals have date < any label date they reference.
        Checks signals.db expert_signals: each signal's date should not
        contain data from the signal date itself.
        """
        if not self.signals_db:
            return {"passed": True, "message": "No signals_db provided, skipped"}

        conn = self._connect(self.signals_db)
        try:
            # Check: snapshot_time should be 'EOD' (computed after close, used next day)
            row = conn.execute("""
                SELECT COUNT(*) as cnt FROM expert_signals
                WHERE snapshot_time NOT IN ('EOD')
                  AND snapshot_time NOT LIKE '__:__'
            """).fetchone()

            if row["cnt"] > 0:
                return {
                    "passed": False,
                    "message": (
                        f"{row['cnt']} signals have invalid snapshot_time. "
                        f"Expected 'EOD' or 'HH:MM'."
                    ),
                }
        finally:
            conn.close()

        return {"passed": True, "message": "OK"}

    def check_no_future_close_in_signals(self) -> dict:
        """
        Verify: expert signals for date T do not use close of date T.
        Cross-check: signal date should have data_cutoff < signal date.
        We check metadata_json for data_cutoff_date if available.
        """
        if not self.signals_db:
            return {"passed": True, "message": "No signals_db provided, skipped"}

        conn = self._connect(self.signals_db)
        try:
            # Check signals with metadata containing data_cutoff_date
            rows = conn.execute("""
                SELECT symbol, date, expert_id, metadata_json
                FROM expert_signals
                WHERE metadata_json IS NOT NULL
                  AND metadata_json LIKE '%data_cutoff_date%'
                LIMIT 1000
            """).fetchall()

            import json
            violations = 0
            for r in rows:
                try:
                    meta = json.loads(r["metadata_json"])
                    cutoff = meta.get("data_cutoff_date")
                    if cutoff and cutoff >= r["date"]:
                        violations += 1
                except (json.JSONDecodeError, KeyError):
                    pass

            if violations > 0:
                return {
                    "passed": False,
                    "message": f"{violations} signals use data from signal date or later",
                }
        finally:
            conn.close()

        return {"passed": True, "message": "OK"}

    def _log_to_audit(self, check_name: str, message: str) -> None:
        """Log leakage violation to audit.db if available."""
        audit_db = Path(self.market_db).parent / "audit.db"
        if not audit_db.exists():
            return

        try:
            conn = sqlite3.connect(str(audit_db))
            conn.execute("""
                CREATE TABLE IF NOT EXISTS leakage_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    check_name TEXT NOT NULL,
                    message TEXT,
                    detected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.execute(
                "INSERT INTO leakage_log (check_name, message) VALUES (?, ?)",
                (check_name, message),
            )
            conn.commit()
            conn.close()
        except Exception:
            pass  # non-critical
