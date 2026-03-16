"""
V4MA Moving Average Expert Tests
"""

import sqlite3
import json
from datetime import date, timedelta
from pathlib import Path

import pytest
import numpy as np

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[5]))

from AI_engine.experts.trend.v4ma.feature_builder import MAFeatureBuilder, MAFeatures
from AI_engine.experts.trend.v4ma.signal_logic import MASignalLogic, MAOutput
from AI_engine.experts.trend.v4ma.expert_writer import MAExpertWriter


def _create_test_db(db_path: str, num_days=450, trend="up"):
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
        conn.execute("INSERT OR IGNORE INTO symbols_master VALUES (?,?,?,?,?,?,?,?)",
                      (s, s, "HOSE", None, None, t, "2025-01-01", None))

    base = date(2024, 1, 1)
    np.random.seed(99)
    for s in ["FPT", "VNM", "HPG", "VNINDEX"]:
        price = 100.0 if s != "VNINDEX" else 1200.0
        for i in range(num_days):
            d = base + timedelta(days=i)
            if d.weekday() >= 5:
                continue
            drift = 0.0004 if trend == "up" else (-0.0004 if trend == "down" else 0)
            price *= 1 + drift + np.random.normal(0, 0.01)
            h = price * 1.005
            l = price * 0.995
            conn.execute(
                "INSERT OR IGNORE INTO prices_daily VALUES (?,?,?,?,?,?,?,NULL,CURRENT_TIMESTAMP)",
                (s, d.isoformat(), round(price * 1.001, 2), round(h, 2), round(l, 2), round(price, 2),
                 int(np.random.uniform(1e6, 5e6))),
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


# --- Feature Builder ---

class TestMAFeatureBuilder:

    def test_build(self, test_dbs):
        mdb, _ = test_dbs
        f = MAFeatureBuilder(mdb).build("FPT", "2025-06-01")
        assert f.has_sufficient_data
        assert f.ema10 > 0
        assert f.sma100 > 0
        assert f.sma200 > 0

    def test_data_leakage(self, test_dbs):
        mdb, _ = test_dbs
        f = MAFeatureBuilder(mdb).build("FPT", "2025-06-01")
        assert f.data_cutoff_date < "2025-06-01"

    def test_ma100_features(self, test_dbs):
        """MA100 features: dist_ma100, ma50_over_ma100, ma100_over_ma200, ma100_slope."""
        mdb, _ = test_dbs
        f = MAFeatureBuilder(mdb).build("FPT", "2025-06-01")
        assert f.sma100 > 0
        assert isinstance(f.dist_ma100, float)
        assert f.ma50_over_ma100 in (1, -1)
        assert f.ma100_over_ma200 in (1, -1)
        assert isinstance(f.ma100_slope, float)

    def test_distances(self, test_dbs):
        mdb, _ = test_dbs
        f = MAFeatureBuilder(mdb).build("FPT", "2025-06-01")
        # Distance should be reasonable
        for d in [f.dist_ema10, f.dist_ema20, f.dist_ma50, f.dist_ma100, f.dist_ma200]:
            assert -1.0 < d < 1.0  # within 100%

    def test_slopes(self, test_dbs):
        mdb, _ = test_dbs
        f = MAFeatureBuilder(mdb).build("FPT", "2025-06-01")
        for s in [f.ema10_slope, f.ema20_slope, f.ma50_slope, f.ma100_slope, f.ma200_slope]:
            assert isinstance(s, float)

    def test_cross_flags(self, test_dbs):
        mdb, _ = test_dbs
        f = MAFeatureBuilder(mdb).build("FPT", "2025-06-01")
        assert f.ema10_over_ema20 in (1, -1)
        assert f.ma50_over_ma100 in (1, -1)
        assert f.ma100_over_ma200 in (1, -1)
        assert f.ma50_over_ma200 in (1, -1)

    def test_insufficient_data(self, test_dbs):
        mdb, _ = test_dbs
        f = MAFeatureBuilder(mdb).build("FPT", "2024-07-01")
        assert not f.has_sufficient_data

    def test_batch(self, test_dbs):
        mdb, _ = test_dbs
        results = MAFeatureBuilder(mdb).build_batch(["FPT", "VNM", "HPG"], "2025-06-01")
        assert len(results) == 3


# --- Signal Logic ---

class TestMASignalLogic:

    def test_score_range(self, test_dbs):
        mdb, _ = test_dbs
        f = MAFeatureBuilder(mdb).build("FPT", "2025-06-01")
        o = MASignalLogic().compute(f)
        assert -4.0 <= o.ma_score <= 4.0

    def test_norm(self, test_dbs):
        mdb, _ = test_dbs
        f = MAFeatureBuilder(mdb).build("FPT", "2025-06-01")
        o = MASignalLogic().compute(f)
        assert abs(o.ma_norm - o.ma_score / 4.0) < 1e-9

    def test_alignment_valid(self, test_dbs):
        mdb, _ = test_dbs
        f = MAFeatureBuilder(mdb).build("FPT", "2025-06-01")
        o = MASignalLogic().compute(f)
        valid = {"all_bullish", "strong_bullish", "mild_bullish", "neutral",
                 "mild_bearish", "strong_bearish", "all_bearish"}
        assert o.alignment in valid

    def test_quality_range(self, test_dbs):
        mdb, _ = test_dbs
        f = MAFeatureBuilder(mdb).build("FPT", "2025-06-01")
        o = MASignalLogic().compute(f)
        assert 0 <= o.signal_quality <= 4

    def test_signal_code_prefix(self, test_dbs):
        mdb, _ = test_dbs
        f = MAFeatureBuilder(mdb).build("FPT", "2025-06-01")
        o = MASignalLogic().compute(f)
        assert o.signal_code.startswith("V4MA_")

    def test_deterministic(self, test_dbs):
        mdb, _ = test_dbs
        f = MAFeatureBuilder(mdb).build("FPT", "2025-06-01")
        o1 = MASignalLogic().compute(f)
        o2 = MASignalLogic().compute(f)
        assert o1.ma_score == o2.ma_score

    def test_full_bullish(self):
        logic = MASignalLogic()
        f = MAFeatures(
            symbol="TEST", date="2026-01-15", data_cutoff_date="2026-01-14",
            close=120, ema10=118, ema20=115, sma50=110, sma100=105, sma200=100,
            dist_ema10=0.017, dist_ema20=0.043, dist_ma50=0.091,
            dist_ma100=0.143, dist_ma200=0.200,
            ema10_slope=0.01, ema20_slope=0.008, ma50_slope=0.005,
            ma100_slope=0.003, ma200_slope=0.002,
            ema10_over_ema20=1, ma50_over_ma100=1, ma100_over_ma200=1, ma50_over_ma200=1,
            has_sufficient_data=True,
        )
        o = logic.compute(f)
        assert o.alignment == "all_bullish"
        assert o.ma_score == 3.0  # alignment=3, no cross
        assert o.signal_quality == 4

    def test_full_bearish(self):
        logic = MASignalLogic()
        f = MAFeatures(
            symbol="TEST", date="2026-01-15", data_cutoff_date="2026-01-14",
            close=80, ema10=82, ema20=85, sma50=90, sma100=95, sma200=100,
            dist_ema10=-0.024, dist_ema20=-0.059, dist_ma50=-0.111,
            dist_ma100=-0.158, dist_ma200=-0.200,
            ema10_slope=-0.01, ema20_slope=-0.008, ma50_slope=-0.005,
            ma100_slope=-0.003, ma200_slope=-0.002,
            ema10_over_ema20=-1, ma50_over_ma100=-1, ma100_over_ma200=-1, ma50_over_ma200=-1,
            has_sufficient_data=True,
        )
        o = logic.compute(f)
        assert o.alignment == "all_bearish"
        assert o.ma_score == -3.0
        assert o.signal_quality == 4

    def test_golden_cross_bonus(self):
        logic = MASignalLogic()
        f = MAFeatures(
            symbol="TEST", date="2026-01-15", data_cutoff_date="2026-01-14",
            close=120, ema10=118, ema20=115, sma50=110, sma100=105, sma200=100,
            ema10_over_ema20=1, ma50_over_ma100=1, ma100_over_ma200=1, ma50_over_ma200=1,
            golden_cross=True,
            has_sufficient_data=True,
        )
        o = logic.compute(f)
        assert o.cross_signal == "golden_cross"
        assert o.ma_score == 4.0  # 3 + 1, clamped at 4


# --- Expert Writer ---

class TestMAExpertWriter:

    def test_run_symbol(self, test_dbs):
        mdb, sdb = test_dbs
        w = MAExpertWriter(mdb, sdb)
        o = w.run_symbol("FPT", "2025-06-01")
        assert isinstance(o, MAOutput)

        conn = sqlite3.connect(sdb)
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT * FROM expert_signals WHERE symbol='FPT' AND expert_id='V4MA'"
        ).fetchone()
        conn.close()
        assert row is not None
        assert -4 <= row["primary_score"] <= 4

    def test_metadata_has_ma100(self, test_dbs):
        """Metadata must include MA100 features."""
        mdb, sdb = test_dbs
        w = MAExpertWriter(mdb, sdb)
        w.run_symbol("FPT", "2025-06-01")

        conn = sqlite3.connect(sdb)
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT metadata_json FROM expert_signals WHERE symbol='FPT' AND expert_id='V4MA'"
        ).fetchone()
        conn.close()

        meta = json.loads(row["metadata_json"])
        assert "dist_ma100" in meta
        assert "ma50_over_ma100" in meta
        assert "ma100_over_ma200" in meta
        assert "ma100_slope" in meta

    def test_run_all(self, test_dbs):
        mdb, sdb = test_dbs
        w = MAExpertWriter(mdb, sdb)
        results = w.run_all("2025-06-01", symbols=["FPT", "VNM"])
        assert len(results) == 2

    def test_idempotent(self, test_dbs):
        mdb, sdb = test_dbs
        w = MAExpertWriter(mdb, sdb)
        w.run_symbol("FPT", "2025-06-01")
        w.run_symbol("FPT", "2025-06-01")
        conn = sqlite3.connect(sdb)
        cnt = conn.execute(
            "SELECT COUNT(*) FROM expert_signals WHERE symbol='FPT' AND date='2025-06-01' AND expert_id='V4MA'"
        ).fetchone()[0]
        conn.close()
        assert cnt == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
