"""
Master Summary Tests
Tests aggregate computation, direction, strength, DB writes.
Uses synthetic r_predictions data.
"""

import sqlite3
import numpy as np
from pathlib import Path
from datetime import date

import pytest

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from AI_engine.r_layer.master_summary import MasterSummary, SummaryRow


@pytest.fixture
def test_db(tmp_path):
    """Create test models.db with r_predictions and master_summary tables."""
    db_path = str(tmp_path / "models.db")
    conn = sqlite3.connect(db_path)
    conn.executescript("""
        CREATE TABLE r_predictions (
            symbol TEXT NOT NULL, date DATE NOT NULL,
            snapshot_time TEXT DEFAULT 'EOD',
            r0_score REAL, r1_score REAL, r2_score REAL,
            r3_score REAL, r4_score REAL, r5_score REAL,
            ensemble_score REAL, ensemble_confidence REAL,
            ensemble_direction INTEGER,
            model_version TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (symbol, date, snapshot_time)
        );
    """)

    # Insert test predictions: 3 symbols, all bullish
    for sym in ["FPT", "VNM", "HPG"]:
        conn.execute(
            """INSERT INTO r_predictions
               (symbol, date, snapshot_time, r0_score, r1_score, r2_score,
                r3_score, r4_score, r5_score,
                ensemble_score, ensemble_confidence, ensemble_direction)
               VALUES (?, '2025-01-15', 'EOD', ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (sym, 1.5, 2.0, 1.8, 2.5, 1.0, 1.2, 1.8, 0.85, 1),
        )

    # Insert mixed symbol
    conn.execute(
        """INSERT INTO r_predictions
           (symbol, date, snapshot_time, r0_score, r1_score, r2_score,
            r3_score, r4_score, r5_score,
            ensemble_score, ensemble_confidence, ensemble_direction)
           VALUES ('MIX', '2025-01-15', 'EOD', 2.0, -1.5, 1.0, -2.0, 0.5, -0.5, 0.1, 0.5, 0)""",
    )

    # Insert bearish symbol
    conn.execute(
        """INSERT INTO r_predictions
           (symbol, date, snapshot_time, r0_score, r1_score, r2_score,
            r3_score, r4_score, r5_score,
            ensemble_score, ensemble_confidence, ensemble_direction)
           VALUES ('BEAR', '2025-01-15', 'EOD', -2.0, -3.0, -1.5, -2.5, -1.0, -2.0, -2.1, 0.9, -1)""",
    )

    # Insert partial data (only R0, R1)
    conn.execute(
        """INSERT INTO r_predictions
           (symbol, date, snapshot_time, r0_score, r1_score,
            ensemble_score, ensemble_confidence, ensemble_direction)
           VALUES ('PARTIAL', '2025-01-15', 'EOD', 1.0, 0.5, 0.8, 0.7, 1)""",
    )

    conn.commit()
    conn.close()
    return db_path


class TestMasterSummary:

    def test_compute_writes_rows(self, test_db):
        ms = MasterSummary(test_db)
        stats = ms.compute("2025-01-15")
        assert stats["symbols"] == 6  # FPT, VNM, HPG, MIX, BEAR, PARTIAL

    def test_bullish_summary(self, test_db):
        ms = MasterSummary(test_db)
        ms.compute("2025-01-15")
        s = ms.get_summary("FPT", "2025-01-15")

        assert s is not None
        assert s.agg_available_models == 6
        assert s.agg_avg_score > 0
        assert s.agg_bullish_model_count >= 4
        assert s.summary_direction == 1
        assert s.summary_strength > 0

    def test_bearish_summary(self, test_db):
        ms = MasterSummary(test_db)
        ms.compute("2025-01-15")
        s = ms.get_summary("BEAR", "2025-01-15")

        assert s is not None
        assert s.agg_avg_score < 0
        assert s.agg_bearish_model_count >= 4
        assert s.summary_direction == -1

    def test_mixed_summary(self, test_db):
        ms = MasterSummary(test_db)
        ms.compute("2025-01-15")
        s = ms.get_summary("MIX", "2025-01-15")

        assert s is not None
        assert s.agg_dispersion > 0.5  # high disagreement
        assert s.agg_agreement_score < 0.8  # not fully aligned
        assert s.agg_bullish_model_count > 0
        assert s.agg_bearish_model_count > 0

    def test_partial_data(self, test_db):
        ms = MasterSummary(test_db)
        ms.compute("2025-01-15")
        s = ms.get_summary("PARTIAL", "2025-01-15")

        assert s is not None
        assert s.agg_available_models == 2  # only R0 and R1
        assert s.r2_score is None
        assert s.r0_score == 1.0

    def test_aggregate_ranges(self, test_db):
        ms = MasterSummary(test_db)
        ms.compute("2025-01-15")

        for sym in ["FPT", "VNM", "HPG", "MIX", "BEAR", "PARTIAL"]:
            s = ms.get_summary(sym, "2025-01-15")
            assert s is not None
            assert -4.0 <= s.agg_avg_score <= 4.0
            assert -4.0 <= s.agg_median_score <= 4.0
            assert 0.0 <= s.agg_dispersion <= 4.0
            assert 0.0 <= s.agg_agreement_score <= 1.0
            assert 0.0 <= s.summary_strength <= 4.0
            assert s.summary_direction in (-1, 0, 1)

    def test_model_counts_sum(self, test_db):
        ms = MasterSummary(test_db)
        ms.compute("2025-01-15")
        s = ms.get_summary("FPT", "2025-01-15")

        total = s.agg_bullish_model_count + s.agg_bearish_model_count + s.agg_neutral_model_count
        assert total == s.agg_available_models

    def test_ensemble_preserved(self, test_db):
        ms = MasterSummary(test_db)
        ms.compute("2025-01-15")
        s = ms.get_summary("FPT", "2025-01-15")

        assert s.ensemble_score == 1.8
        assert s.ensemble_confidence == 0.85
        assert s.ensemble_direction == 1

    def test_idempotent(self, test_db):
        ms = MasterSummary(test_db)
        ms.compute("2025-01-15")
        ms.compute("2025-01-15")  # run again

        conn = sqlite3.connect(test_db)
        count = conn.execute(
            "SELECT COUNT(*) FROM master_summary WHERE date='2025-01-15'"
        ).fetchone()[0]
        conn.close()
        assert count == 6  # no duplicates

    def test_no_data(self, test_db):
        ms = MasterSummary(test_db)
        stats = ms.compute("2099-01-01")
        assert stats["symbols"] == 0

    def test_get_summary_nonexistent(self, test_db):
        ms = MasterSummary(test_db)
        s = ms.get_summary("NOSYMBOL", "2025-01-15")
        assert s is None

    def test_db_schema(self, test_db):
        ms = MasterSummary(test_db)
        ms.compute("2025-01-15")

        conn = sqlite3.connect(test_db)
        cols = [row[1] for row in conn.execute("PRAGMA table_info(master_summary)")]
        conn.close()

        required = [
            "symbol", "date", "r0_score", "r1_score", "r2_score",
            "r3_score", "r4_score", "r5_score",
            "ensemble_score", "ensemble_confidence", "ensemble_direction",
            "agg_avg_score", "agg_median_score", "agg_dispersion",
            "agg_agreement_score", "agg_bullish_model_count",
            "agg_bearish_model_count", "agg_neutral_model_count",
            "agg_available_models", "summary_direction", "summary_strength",
        ]
        for col in required:
            assert col in cols, f"Missing column: {col}"

    def test_strength_is_abs_avg(self, test_db):
        ms = MasterSummary(test_db)
        ms.compute("2025-01-15")
        s = ms.get_summary("BEAR", "2025-01-15")
        assert s.summary_strength == pytest.approx(min(4.0, abs(s.agg_avg_score)), abs=0.01)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
