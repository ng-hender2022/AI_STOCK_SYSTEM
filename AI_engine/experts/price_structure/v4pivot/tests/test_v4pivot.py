"""
V4PIVOT Pivot Point Expert Tests
"""

import sqlite3
import json
from datetime import date, timedelta
from pathlib import Path

import pytest
import numpy as np

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[5]))

from AI_engine.experts.price_structure.v4pivot.feature_builder import (
    PivotFeatureBuilder,
    PivotFeatures,
    _compute_pivot_levels,
)
from AI_engine.experts.price_structure.v4pivot.signal_logic import PivotSignalLogic, PivotOutput
from AI_engine.experts.price_structure.v4pivot.expert_writer import PivotExpertWriter


def _create_test_db(db_path: str, num_days=400, trend="up"):
    conn = sqlite3.connect(db_path)
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS symbols_master (
            symbol TEXT PRIMARY KEY, name TEXT NOT NULL,
            exchange TEXT DEFAULT 'HOSE', sector TEXT, industry TEXT,
            is_tradable INTEGER DEFAULT 1, added_date DATE NOT NULL, notes TEXT
        );
        CREATE TABLE IF NOT EXISTS prices_daily (
            symbol TEXT NOT NULL, date DATE NOT NULL,
            open REAL, high REAL, low REAL, close REAL,
            volume INTEGER, value REAL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (symbol, date)
        );
    """)
    for s in ["VNINDEX", "FPT", "VNM", "HPG"]:
        t = 0 if s == "VNINDEX" else 1
        conn.execute(
            "INSERT OR IGNORE INTO symbols_master VALUES (?,?,?,?,?,?,?,?)",
            (s, s, "HOSE", None, None, t, "2024-01-01", None),
        )

    base = date(2024, 1, 1)
    np.random.seed(42)
    for s in ["FPT", "VNM", "HPG", "VNINDEX"]:
        price = 100.0 if s != "VNINDEX" else 1200.0
        for i in range(num_days):
            d = base + timedelta(days=i)
            if d.weekday() >= 5:
                continue
            drift = 0.0006 if trend == "up" else (-0.0006 if trend == "down" else 0)
            price *= 1 + drift + np.random.normal(0, 0.012)
            h = price * (1 + abs(np.random.normal(0, 0.005)) + 0.002)
            l = price * (1 - abs(np.random.normal(0, 0.005)) - 0.002)
            o = price * (1 + np.random.normal(0, 0.003))
            conn.execute(
                "INSERT OR IGNORE INTO prices_daily VALUES (?,?,?,?,?,?,?,NULL,CURRENT_TIMESTAMP)",
                (
                    s,
                    d.isoformat(),
                    round(o, 2),
                    round(h, 2),
                    round(l, 2),
                    round(price, 2),
                    int(np.random.uniform(1e6, 5e6)),
                ),
            )
    conn.commit()
    conn.close()


def _create_signals_db(db_path: str):
    conn = sqlite3.connect(db_path)
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS expert_signals (
            symbol TEXT NOT NULL, date DATE NOT NULL,
            snapshot_time TEXT DEFAULT 'EOD', expert_id TEXT NOT NULL,
            primary_score REAL NOT NULL, secondary_score REAL,
            signal_code TEXT, signal_quality INTEGER DEFAULT 0,
            metadata_json TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (symbol, date, snapshot_time, expert_id)
        );
    """)
    conn.commit()
    conn.close()


@pytest.fixture
def test_dbs(tmp_path):
    mdb = str(tmp_path / "market.db")
    sdb = str(tmp_path / "signals.db")
    _create_test_db(mdb)
    _create_signals_db(sdb)
    return mdb, sdb


@pytest.fixture
def bearish_dbs(tmp_path):
    mdb = str(tmp_path / "market.db")
    sdb = str(tmp_path / "signals.db")
    _create_test_db(mdb, trend="down")
    _create_signals_db(sdb)
    return mdb, sdb


# ---------------------------------------------------------------------------
# Pivot Formula Unit Tests
# ---------------------------------------------------------------------------

class TestPivotFormulas:

    def test_standard_pivot(self):
        levels = _compute_pivot_levels(h=110.0, l=90.0, c=105.0)
        p = (110 + 90 + 105) / 3.0
        assert abs(levels["P"] - p) < 1e-9
        assert abs(levels["R1"] - (2 * p - 90)) < 1e-9
        assert abs(levels["R2"] - (p + (110 - 90))) < 1e-9
        assert abs(levels["S1"] - (2 * p - 110)) < 1e-9
        assert abs(levels["S2"] - (p - (110 - 90))) < 1e-9

    def test_pivot_ordering(self):
        levels = _compute_pivot_levels(h=110.0, l=90.0, c=100.0)
        assert levels["S2"] < levels["S1"] < levels["P"] < levels["R1"] < levels["R2"]

    def test_symmetric_when_close_at_midpoint(self):
        levels = _compute_pivot_levels(h=110.0, l=90.0, c=100.0)
        # P = 100, R1 = 110, R2 = 120, S1 = 90, S2 = 80
        assert abs(levels["P"] - 100.0) < 1e-9
        assert abs(levels["R1"] - 110.0) < 1e-9
        assert abs(levels["S1"] - 90.0) < 1e-9

    def test_narrow_range(self):
        levels = _compute_pivot_levels(h=100.1, l=99.9, c=100.0)
        assert levels["R2"] - levels["S2"] < 1.0  # narrow range


# ---------------------------------------------------------------------------
# Feature Builder Tests
# ---------------------------------------------------------------------------

class TestPivotFeatureBuilder:

    def test_build(self, test_dbs):
        mdb, _ = test_dbs
        f = PivotFeatureBuilder(mdb).build("FPT", "2025-02-01")
        assert f.has_sufficient_data
        assert f.close > 0
        assert f.pivot > 0
        assert f.r1 > 0
        assert f.r2 > 0
        assert f.s1 > 0
        assert f.s2 > 0

    def test_data_leakage(self, test_dbs):
        mdb, _ = test_dbs
        f = PivotFeatureBuilder(mdb).build("FPT", "2025-02-01")
        assert f.data_cutoff_date < "2025-02-01"

    def test_pivot_level_ordering(self, test_dbs):
        mdb, _ = test_dbs
        f = PivotFeatureBuilder(mdb).build("FPT", "2025-02-01")
        assert f.s2 < f.s1 < f.pivot < f.r1 < f.r2

    def test_weekly_pivot_populated(self, test_dbs):
        mdb, _ = test_dbs
        f = PivotFeatureBuilder(mdb).build("FPT", "2025-02-01")
        assert f.weekly_pivot > 0

    def test_monthly_pivot_populated(self, test_dbs):
        mdb, _ = test_dbs
        f = PivotFeatureBuilder(mdb).build("FPT", "2025-02-01")
        assert f.monthly_pivot > 0

    def test_prev_pivot_populated(self, test_dbs):
        mdb, _ = test_dbs
        f = PivotFeatureBuilder(mdb).build("FPT", "2025-02-01")
        assert f.prev_pivot > 0

    def test_insufficient_data(self, test_dbs):
        mdb, _ = test_dbs
        f = PivotFeatureBuilder(mdb).build("FPT", "2024-02-01")
        assert not f.has_sufficient_data

    def test_batch(self, test_dbs):
        mdb, _ = test_dbs
        results = PivotFeatureBuilder(mdb).build_batch(["FPT", "VNM", "HPG"], "2025-02-01")
        assert len(results) == 3
        for r in results:
            assert r.has_sufficient_data

    def test_nonexistent_symbol(self, test_dbs):
        mdb, _ = test_dbs
        f = PivotFeatureBuilder(mdb).build("ZZZZZ", "2025-02-01")
        assert not f.has_sufficient_data
        assert f.data_cutoff_date == ""


# ---------------------------------------------------------------------------
# Signal Logic Tests
# ---------------------------------------------------------------------------

class TestPivotSignalLogic:

    def test_score_range(self, test_dbs):
        mdb, _ = test_dbs
        f = PivotFeatureBuilder(mdb).build("FPT", "2025-02-01")
        o = PivotSignalLogic().compute(f)
        assert -4.0 <= o.pivot_score <= 4.0

    def test_norm(self, test_dbs):
        mdb, _ = test_dbs
        f = PivotFeatureBuilder(mdb).build("FPT", "2025-02-01")
        o = PivotSignalLogic().compute(f)
        assert abs(o.pivot_norm - o.pivot_score / 4.0) < 1e-9

    def test_quality_range(self, test_dbs):
        mdb, _ = test_dbs
        f = PivotFeatureBuilder(mdb).build("FPT", "2025-02-01")
        o = PivotSignalLogic().compute(f)
        assert 0 <= o.signal_quality <= 4

    def test_signal_code_prefix(self, test_dbs):
        mdb, _ = test_dbs
        f = PivotFeatureBuilder(mdb).build("FPT", "2025-02-01")
        o = PivotSignalLogic().compute(f)
        assert o.signal_code.startswith("V4PIVOT_")

    def test_deterministic(self, test_dbs):
        mdb, _ = test_dbs
        f = PivotFeatureBuilder(mdb).build("FPT", "2025-02-01")
        o1 = PivotSignalLogic().compute(f)
        o2 = PivotSignalLogic().compute(f)
        assert o1.pivot_score == o2.pivot_score

    def test_strong_bullish(self):
        """Close above R2 with all timeframes bullish and rising pivots."""
        logic = PivotSignalLogic()
        f = PivotFeatures(
            symbol="TEST", date="2025-02-01", data_cutoff_date="2025-01-31",
            close=120.0,
            pivot=100.0, r1=110.0, r2=115.0, s1=95.0, s2=85.0,
            prev_pivot=98.0,
            weekly_pivot=99.0, weekly_r1=108.0, weekly_s1=94.0,
            prev_weekly_pivot=97.0,
            monthly_pivot=98.0, monthly_r1=107.0, monthly_s1=93.0,
            prev_monthly_pivot=96.0,
            has_sufficient_data=True,
        )
        o = logic.compute(f)
        # position=+2, confluence=+1 (all bullish), alignment=+1 (all rising) = +4
        assert o.pivot_score == 4.0
        assert o.signal_quality == 4
        assert o.signal_code in ("V4PIVOT_BULL_ABOVE_R2", "V4PIVOT_BULL_CONFLUENCE")

    def test_strong_bearish(self):
        """Close below S2 with all timeframes bearish and falling pivots."""
        logic = PivotSignalLogic()
        f = PivotFeatures(
            symbol="TEST", date="2025-02-01", data_cutoff_date="2025-01-31",
            close=80.0,
            pivot=100.0, r1=110.0, r2=115.0, s1=95.0, s2=85.0,
            prev_pivot=102.0,
            weekly_pivot=101.0, weekly_r1=108.0, weekly_s1=94.0,
            prev_weekly_pivot=103.0,
            monthly_pivot=102.0, monthly_r1=107.0, monthly_s1=93.0,
            prev_monthly_pivot=104.0,
            has_sufficient_data=True,
        )
        o = logic.compute(f)
        # position=-2, confluence=-1 (all bearish), alignment=-1 (all falling) = -4
        assert o.pivot_score == -4.0
        assert o.signal_quality == 4
        assert o.signal_code in ("V4PIVOT_BEAR_BELOW_S2", "V4PIVOT_BEAR_CONFLUENCE")

    def test_neutral_at_pivot(self):
        """Close exactly at pivot level."""
        logic = PivotSignalLogic()
        f = PivotFeatures(
            symbol="TEST", date="2025-02-01", data_cutoff_date="2025-01-31",
            close=100.0,
            pivot=100.0, r1=110.0, r2=115.0, s1=95.0, s2=85.0,
            prev_pivot=100.0,
            weekly_pivot=100.0, weekly_r1=108.0, weekly_s1=94.0,
            prev_weekly_pivot=100.0,
            monthly_pivot=100.0, monthly_r1=107.0, monthly_s1=93.0,
            prev_monthly_pivot=100.0,
            has_sufficient_data=True,
        )
        o = logic.compute(f)
        assert o.position_score == 0.0
        assert o.signal_code == "V4PIVOT_NEUT_AT_PIVOT"

    def test_r1_to_r2_position(self):
        """Close between R1 and R2."""
        logic = PivotSignalLogic()
        f = PivotFeatures(
            symbol="TEST", date="2025-02-01", data_cutoff_date="2025-01-31",
            close=112.0,
            pivot=100.0, r1=110.0, r2=115.0, s1=95.0, s2=85.0,
            prev_pivot=100.0,
            weekly_pivot=0.0, monthly_pivot=0.0,
            has_sufficient_data=True,
        )
        o = logic.compute(f)
        assert o.position_score == 1.5

    def test_s1_to_p_position(self):
        """Close between S1 and P."""
        logic = PivotSignalLogic()
        f = PivotFeatures(
            symbol="TEST", date="2025-02-01", data_cutoff_date="2025-01-31",
            close=97.0,
            pivot=100.0, r1=110.0, r2=115.0, s1=95.0, s2=85.0,
            prev_pivot=100.0,
            weekly_pivot=0.0, monthly_pivot=0.0,
            has_sufficient_data=True,
        )
        o = logic.compute(f)
        assert o.position_score == -1.0

    def test_insufficient_data_returns_zero(self):
        logic = PivotSignalLogic()
        f = PivotFeatures(
            symbol="TEST", date="2025-02-01", data_cutoff_date="",
            has_sufficient_data=False,
        )
        o = logic.compute(f)
        assert o.pivot_score == 0.0
        assert not o.has_sufficient_data

    def test_valid_signal_codes(self, test_dbs):
        mdb, _ = test_dbs
        valid_codes = {
            "V4PIVOT_BULL_ABOVE_R1", "V4PIVOT_BULL_ABOVE_R2",
            "V4PIVOT_BEAR_BELOW_S1", "V4PIVOT_BEAR_BELOW_S2",
            "V4PIVOT_BULL_CONFLUENCE", "V4PIVOT_BEAR_CONFLUENCE",
            "V4PIVOT_NEUT_AT_PIVOT",
            "V4PIVOT_BULL_BOUNCE_S1", "V4PIVOT_BEAR_REJECT_R1",
        }
        for sym in ["FPT", "VNM", "HPG"]:
            f = PivotFeatureBuilder(mdb).build(sym, "2025-02-01")
            o = PivotSignalLogic().compute(f)
            assert o.signal_code in valid_codes, f"{sym}: {o.signal_code}"

    def test_confluence_all_bullish(self):
        """All 3 timeframes bullish -> confluence = +1."""
        logic = PivotSignalLogic()
        f = PivotFeatures(
            symbol="TEST", date="2025-02-01", data_cutoff_date="2025-01-31",
            close=105.0,
            pivot=100.0, r1=110.0, r2=115.0, s1=95.0, s2=85.0,
            prev_pivot=100.0,
            weekly_pivot=100.0, weekly_r1=108.0, weekly_s1=94.0,
            prev_weekly_pivot=100.0,
            monthly_pivot=100.0, monthly_r1=107.0, monthly_s1=93.0,
            prev_monthly_pivot=100.0,
            has_sufficient_data=True,
        )
        o = logic.compute(f)
        assert o.confluence_score == 1.0

    def test_confluence_all_bearish(self):
        """All 3 timeframes bearish -> confluence = -1."""
        logic = PivotSignalLogic()
        f = PivotFeatures(
            symbol="TEST", date="2025-02-01", data_cutoff_date="2025-01-31",
            close=90.0,
            pivot=100.0, r1=110.0, r2=115.0, s1=95.0, s2=85.0,
            prev_pivot=100.0,
            weekly_pivot=100.0, weekly_r1=108.0, weekly_s1=94.0,
            prev_weekly_pivot=100.0,
            monthly_pivot=100.0, monthly_r1=107.0, monthly_s1=93.0,
            prev_monthly_pivot=100.0,
            has_sufficient_data=True,
        )
        o = logic.compute(f)
        assert o.confluence_score == -1.0

    def test_alignment_all_rising(self):
        """All pivots rising -> alignment = +1."""
        logic = PivotSignalLogic()
        f = PivotFeatures(
            symbol="TEST", date="2025-02-01", data_cutoff_date="2025-01-31",
            close=105.0,
            pivot=100.0, r1=110.0, r2=115.0, s1=95.0, s2=85.0,
            prev_pivot=98.0,
            weekly_pivot=100.0, weekly_r1=108.0, weekly_s1=94.0,
            prev_weekly_pivot=97.0,
            monthly_pivot=100.0, monthly_r1=107.0, monthly_s1=93.0,
            prev_monthly_pivot=96.0,
            has_sufficient_data=True,
        )
        o = logic.compute(f)
        assert o.alignment_score == 1.0

    def test_alignment_all_falling(self):
        """All pivots falling -> alignment = -1."""
        logic = PivotSignalLogic()
        f = PivotFeatures(
            symbol="TEST", date="2025-02-01", data_cutoff_date="2025-01-31",
            close=105.0,
            pivot=100.0, r1=110.0, r2=115.0, s1=95.0, s2=85.0,
            prev_pivot=102.0,
            weekly_pivot=100.0, weekly_r1=108.0, weekly_s1=94.0,
            prev_weekly_pivot=103.0,
            monthly_pivot=100.0, monthly_r1=107.0, monthly_s1=93.0,
            prev_monthly_pivot=104.0,
            has_sufficient_data=True,
        )
        o = logic.compute(f)
        assert o.alignment_score == -1.0


# ---------------------------------------------------------------------------
# Expert Writer Tests
# ---------------------------------------------------------------------------

class TestPivotExpertWriter:

    def test_run_symbol(self, test_dbs):
        mdb, sdb = test_dbs
        w = PivotExpertWriter(mdb, sdb)
        o = w.run_symbol("FPT", "2025-02-01")
        assert isinstance(o, PivotOutput)

        conn = sqlite3.connect(sdb)
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT * FROM expert_signals WHERE symbol='FPT' AND expert_id='V4PIVOT'"
        ).fetchone()
        conn.close()
        assert row is not None
        assert -4 <= row["primary_score"] <= 4

    def test_secondary_score_is_norm(self, test_dbs):
        mdb, sdb = test_dbs
        w = PivotExpertWriter(mdb, sdb)
        w.run_symbol("FPT", "2025-02-01")

        conn = sqlite3.connect(sdb)
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT primary_score, secondary_score FROM expert_signals "
            "WHERE symbol='FPT' AND expert_id='V4PIVOT'"
        ).fetchone()
        conn.close()
        assert abs(row["secondary_score"] - row["primary_score"] / 4.0) < 1e-9

    def test_metadata_fields(self, test_dbs):
        mdb, sdb = test_dbs
        w = PivotExpertWriter(mdb, sdb)
        w.run_symbol("FPT", "2025-02-01")

        conn = sqlite3.connect(sdb)
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT metadata_json FROM expert_signals WHERE symbol='FPT' AND expert_id='V4PIVOT'"
        ).fetchone()
        conn.close()

        meta = json.loads(row["metadata_json"])
        required_keys = [
            "pivot", "r1", "r2", "s1", "s2",
            "weekly_pivot", "monthly_pivot",
            "position_score", "confluence_score", "alignment_score",
            "pivot_norm",
        ]
        for key in required_keys:
            assert key in meta, f"Missing metadata key: {key}"

    def test_metadata_json_types(self, test_dbs):
        """Ensure numpy types are cast to native Python types for JSON."""
        mdb, sdb = test_dbs
        w = PivotExpertWriter(mdb, sdb)
        w.run_symbol("FPT", "2025-02-01")

        conn = sqlite3.connect(sdb)
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT metadata_json FROM expert_signals WHERE symbol='FPT' AND expert_id='V4PIVOT'"
        ).fetchone()
        conn.close()

        meta = json.loads(row["metadata_json"])
        # All numeric values should be native Python float
        for key in ["pivot", "r1", "r2", "s1", "s2", "pivot_norm"]:
            assert isinstance(meta[key], (int, float)), f"{key} is {type(meta[key])}"

    def test_run_all(self, test_dbs):
        mdb, sdb = test_dbs
        w = PivotExpertWriter(mdb, sdb)
        results = w.run_all("2025-02-01", symbols=["FPT", "VNM"])
        assert len(results) == 2

    def test_idempotent(self, test_dbs):
        mdb, sdb = test_dbs
        w = PivotExpertWriter(mdb, sdb)
        w.run_symbol("FPT", "2025-02-01")
        w.run_symbol("FPT", "2025-02-01")
        conn = sqlite3.connect(sdb)
        cnt = conn.execute(
            "SELECT COUNT(*) FROM expert_signals WHERE symbol='FPT' AND date='2025-02-01' AND expert_id='V4PIVOT'"
        ).fetchone()[0]
        conn.close()
        assert cnt == 1

    def test_bearish_market(self, bearish_dbs):
        mdb, sdb = bearish_dbs
        w = PivotExpertWriter(mdb, sdb)
        o = w.run_symbol("FPT", "2025-02-01")
        # In a bearish market, score should lean negative or neutral
        assert o.pivot_score <= 2.0

    def test_multiple_symbols_written(self, test_dbs):
        mdb, sdb = test_dbs
        w = PivotExpertWriter(mdb, sdb)
        w.run_all("2025-02-01", symbols=["FPT", "VNM", "HPG"])

        conn = sqlite3.connect(sdb)
        cnt = conn.execute(
            "SELECT COUNT(*) FROM expert_signals WHERE expert_id='V4PIVOT'"
        ).fetchone()[0]
        conn.close()
        assert cnt == 3


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
