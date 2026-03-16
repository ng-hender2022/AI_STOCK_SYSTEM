"""
V4OBV On Balance Volume Expert Tests
"""

import sqlite3
import json
from datetime import date, timedelta
from pathlib import Path

import pytest
import numpy as np

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[5]))

from AI_engine.experts.volume.v4obv.feature_builder import OBVFeatureBuilder, OBVFeatures
from AI_engine.experts.volume.v4obv.signal_logic import OBVSignalLogic, OBVOutput
from AI_engine.experts.volume.v4obv.expert_writer import OBVExpertWriter


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

class TestOBVFeatureBuilder:

    def test_build(self, test_dbs):
        mdb, _ = test_dbs
        f = OBVFeatureBuilder(mdb).build("FPT", "2025-02-01")
        assert f.has_sufficient_data
        assert isinstance(f.obv_slope_norm, float)
        assert f.obv_divergence in (-1, 0, 1)

    def test_data_leakage(self, test_dbs):
        mdb, _ = test_dbs
        f = OBVFeatureBuilder(mdb).build("FPT", "2025-02-01")
        assert f.data_cutoff_date < "2025-02-01"

    def test_obv_slope_norm(self, test_dbs):
        mdb, _ = test_dbs
        f = OBVFeatureBuilder(mdb).build("FPT", "2025-02-01")
        assert isinstance(f.obv_slope_norm, float)
        # Slope should be finite
        assert np.isfinite(f.obv_slope_norm)

    def test_divergence_values(self, test_dbs):
        mdb, _ = test_dbs
        f = OBVFeatureBuilder(mdb).build("FPT", "2025-02-01")
        assert f.obv_divergence in (-1, 0, 1)

    def test_breakout_flags(self, test_dbs):
        mdb, _ = test_dbs
        f = OBVFeatureBuilder(mdb).build("FPT", "2025-02-01")
        assert f.obv_new_high in (0, 1)
        assert f.obv_new_low in (0, 1)
        assert f.price_new_high in (0, 1)
        assert f.price_new_low in (0, 1)

    def test_confirms_price(self, test_dbs):
        mdb, _ = test_dbs
        f = OBVFeatureBuilder(mdb).build("FPT", "2025-02-01")
        assert f.obv_confirms_price in (-1, 0, 1)

    def test_insufficient_data(self, test_dbs):
        mdb, _ = test_dbs
        # Very early date, not enough history
        f = OBVFeatureBuilder(mdb).build("FPT", "2024-02-01")
        assert not f.has_sufficient_data

    def test_batch(self, test_dbs):
        mdb, _ = test_dbs
        results = OBVFeatureBuilder(mdb).build_batch(["FPT", "VNM", "HPG"], "2025-02-01")
        assert len(results) == 3
        for r in results:
            assert r.has_sufficient_data


# --- Signal Logic ---

class TestOBVSignalLogic:

    def test_score_range(self, test_dbs):
        mdb, _ = test_dbs
        f = OBVFeatureBuilder(mdb).build("FPT", "2025-02-01")
        o = OBVSignalLogic().compute(f)
        assert -4.0 <= o.obv_score <= 4.0

    def test_norm(self, test_dbs):
        mdb, _ = test_dbs
        f = OBVFeatureBuilder(mdb).build("FPT", "2025-02-01")
        o = OBVSignalLogic().compute(f)
        assert abs(o.obv_norm - o.obv_score / 4.0) < 1e-9

    def test_quality_range(self, test_dbs):
        mdb, _ = test_dbs
        f = OBVFeatureBuilder(mdb).build("FPT", "2025-02-01")
        o = OBVSignalLogic().compute(f)
        assert 0 <= o.signal_quality <= 4

    def test_signal_code_prefix(self, test_dbs):
        mdb, _ = test_dbs
        f = OBVFeatureBuilder(mdb).build("FPT", "2025-02-01")
        o = OBVSignalLogic().compute(f)
        assert o.signal_code.startswith("V4OBV_")

    def test_deterministic(self, test_dbs):
        mdb, _ = test_dbs
        f = OBVFeatureBuilder(mdb).build("FPT", "2025-02-01")
        o1 = OBVSignalLogic().compute(f)
        o2 = OBVSignalLogic().compute(f)
        assert o1.obv_score == o2.obv_score

    def test_strong_bullish_trend(self):
        logic = OBVSignalLogic()
        f = OBVFeatures(
            symbol="TEST", date="2025-02-01", data_cutoff_date="2025-01-31",
            close=120.0, obv_current=1000000.0,
            obv_slope_norm=0.8,  # > 0.5 threshold
            obv_divergence=0, obv_new_high=0, obv_new_low=0,
            price_new_high=0, price_new_low=0, obv_confirms_price=1,
            has_sufficient_data=True,
        )
        o = logic.compute(f)
        assert o.trend_score == 2.0
        assert o.obv_score == 2.0
        assert o.signal_code == "V4OBV_BULL_TREND"
        assert o.signal_quality == 2

    def test_strong_bearish_trend(self):
        logic = OBVSignalLogic()
        f = OBVFeatures(
            symbol="TEST", date="2025-02-01", data_cutoff_date="2025-01-31",
            close=80.0, obv_current=-500000.0,
            obv_slope_norm=-0.8,  # < -0.5 threshold
            obv_divergence=0, obv_new_high=0, obv_new_low=0,
            price_new_high=0, price_new_low=0, obv_confirms_price=1,
            has_sufficient_data=True,
        )
        o = logic.compute(f)
        assert o.trend_score == -2.0
        assert o.obv_score == -2.0
        assert o.signal_code == "V4OBV_BEAR_TREND"
        assert o.signal_quality == 2

    def test_bullish_divergence(self):
        logic = OBVSignalLogic()
        f = OBVFeatures(
            symbol="TEST", date="2025-02-01", data_cutoff_date="2025-01-31",
            close=90.0, obv_current=500000.0,
            obv_slope_norm=0.1,
            obv_divergence=1,  # bullish div
            obv_new_high=0, obv_new_low=0,
            price_new_high=0, price_new_low=0, obv_confirms_price=-1,
            has_sufficient_data=True,
        )
        o = logic.compute(f)
        assert o.divergence_score == 1.0
        assert o.signal_code == "V4OBV_BULL_DIV"
        assert o.signal_quality == 3

    def test_bearish_divergence(self):
        logic = OBVSignalLogic()
        f = OBVFeatures(
            symbol="TEST", date="2025-02-01", data_cutoff_date="2025-01-31",
            close=120.0, obv_current=-200000.0,
            obv_slope_norm=-0.1,
            obv_divergence=-1,  # bearish div
            obv_new_high=0, obv_new_low=0,
            price_new_high=0, price_new_low=0, obv_confirms_price=-1,
            has_sufficient_data=True,
        )
        o = logic.compute(f)
        assert o.divergence_score == -1.0
        assert o.signal_code == "V4OBV_BEAR_DIV"
        assert o.signal_quality == 3

    def test_obv_breakout_high(self):
        logic = OBVSignalLogic()
        f = OBVFeatures(
            symbol="TEST", date="2025-02-01", data_cutoff_date="2025-01-31",
            close=105.0, obv_current=800000.0,
            obv_slope_norm=0.3,
            obv_divergence=0,
            obv_new_high=1, obv_new_low=0,
            price_new_high=0, price_new_low=0,  # OBV high but NOT price high = leading
            obv_confirms_price=1,
            has_sufficient_data=True,
        )
        o = logic.compute(f)
        assert o.breakout_score == 1.0
        assert o.signal_code == "V4OBV_BULL_BREAK"
        assert o.signal_quality == 3

    def test_obv_breakout_low(self):
        logic = OBVSignalLogic()
        f = OBVFeatures(
            symbol="TEST", date="2025-02-01", data_cutoff_date="2025-01-31",
            close=95.0, obv_current=-800000.0,
            obv_slope_norm=-0.3,
            obv_divergence=0,
            obv_new_high=0, obv_new_low=1,
            price_new_high=0, price_new_low=0,  # OBV low but NOT price low = leading
            obv_confirms_price=1,
            has_sufficient_data=True,
        )
        o = logic.compute(f)
        assert o.breakout_score == -1.0
        assert o.signal_code == "V4OBV_BEAR_BREAK"
        assert o.signal_quality == 3

    def test_div_plus_breakout_quality_4(self):
        logic = OBVSignalLogic()
        f = OBVFeatures(
            symbol="TEST", date="2025-02-01", data_cutoff_date="2025-01-31",
            close=90.0, obv_current=900000.0,
            obv_slope_norm=0.6,
            obv_divergence=1,  # bullish div
            obv_new_high=1, obv_new_low=0,
            price_new_high=0, price_new_low=0,  # OBV breakout
            obv_confirms_price=-1,
            has_sufficient_data=True,
        )
        o = logic.compute(f)
        assert o.signal_quality == 4
        assert o.obv_score == 4.0  # 2 + 1 + 1 = 4

    def test_flat_signal(self):
        logic = OBVSignalLogic()
        f = OBVFeatures(
            symbol="TEST", date="2025-02-01", data_cutoff_date="2025-01-31",
            close=100.0, obv_current=0.0,
            obv_slope_norm=0.0,
            obv_divergence=0, obv_new_high=0, obv_new_low=0,
            price_new_high=0, price_new_low=0, obv_confirms_price=0,
            has_sufficient_data=True,
        )
        o = logic.compute(f)
        assert o.obv_score == 0.0
        assert o.signal_code == "V4OBV_NEUT_FLAT"
        assert o.signal_quality == 0

    def test_clamp_max(self):
        logic = OBVSignalLogic()
        f = OBVFeatures(
            symbol="TEST", date="2025-02-01", data_cutoff_date="2025-01-31",
            close=90.0, obv_current=1000000.0,
            obv_slope_norm=0.8,   # trend +2
            obv_divergence=1,     # div +1
            obv_new_high=1, obv_new_low=0,
            price_new_high=0, price_new_low=0,  # breakout +1
            obv_confirms_price=-1,
            has_sufficient_data=True,
        )
        o = logic.compute(f)
        assert o.obv_score == 4.0  # clamped

    def test_clamp_min(self):
        logic = OBVSignalLogic()
        f = OBVFeatures(
            symbol="TEST", date="2025-02-01", data_cutoff_date="2025-01-31",
            close=110.0, obv_current=-1000000.0,
            obv_slope_norm=-0.8,   # trend -2
            obv_divergence=-1,     # div -1
            obv_new_high=0, obv_new_low=1,
            price_new_high=0, price_new_low=0,  # breakout -1
            obv_confirms_price=-1,
            has_sufficient_data=True,
        )
        o = logic.compute(f)
        assert o.obv_score == -4.0  # clamped

    def test_insufficient_data(self):
        logic = OBVSignalLogic()
        f = OBVFeatures(
            symbol="TEST", date="2025-02-01", data_cutoff_date="",
            has_sufficient_data=False,
        )
        o = logic.compute(f)
        assert o.obv_score == 0.0
        assert not o.has_sufficient_data


# --- Expert Writer ---

class TestOBVExpertWriter:

    def test_run_symbol(self, test_dbs):
        mdb, sdb = test_dbs
        w = OBVExpertWriter(mdb, sdb)
        o = w.run_symbol("FPT", "2025-02-01")
        assert isinstance(o, OBVOutput)

        conn = sqlite3.connect(sdb)
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT * FROM expert_signals WHERE symbol='FPT' AND expert_id='V4OBV'"
        ).fetchone()
        conn.close()
        assert row is not None
        assert -4 <= row["primary_score"] <= 4

    def test_metadata_fields(self, test_dbs):
        """Metadata must include all OBV features."""
        mdb, sdb = test_dbs
        w = OBVExpertWriter(mdb, sdb)
        w.run_symbol("FPT", "2025-02-01")

        conn = sqlite3.connect(sdb)
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT metadata_json FROM expert_signals WHERE symbol='FPT' AND expert_id='V4OBV'"
        ).fetchone()
        conn.close()

        meta = json.loads(row["metadata_json"])
        assert "obv_slope_norm" in meta
        assert "obv_divergence" in meta
        assert "obv_new_high" in meta
        assert "obv_new_low" in meta
        assert "obv_confirms_price" in meta
        assert "obv_norm" in meta
        assert "trend_score" in meta
        assert "divergence_score" in meta
        assert "breakout_score" in meta

    def test_metadata_json_serializable(self, test_dbs):
        """All metadata values must be JSON-serializable (no numpy types)."""
        mdb, sdb = test_dbs
        w = OBVExpertWriter(mdb, sdb)
        w.run_symbol("FPT", "2025-02-01")

        conn = sqlite3.connect(sdb)
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT metadata_json FROM expert_signals WHERE symbol='FPT' AND expert_id='V4OBV'"
        ).fetchone()
        conn.close()

        meta = json.loads(row["metadata_json"])
        # Re-serialize to ensure no numpy types leaked
        reserialized = json.dumps(meta)
        assert isinstance(reserialized, str)

    def test_run_all(self, test_dbs):
        mdb, sdb = test_dbs
        w = OBVExpertWriter(mdb, sdb)
        results = w.run_all("2025-02-01", symbols=["FPT", "VNM"])
        assert len(results) == 2

    def test_idempotent(self, test_dbs):
        mdb, sdb = test_dbs
        w = OBVExpertWriter(mdb, sdb)
        w.run_symbol("FPT", "2025-02-01")
        w.run_symbol("FPT", "2025-02-01")
        conn = sqlite3.connect(sdb)
        cnt = conn.execute(
            "SELECT COUNT(*) FROM expert_signals WHERE symbol='FPT' AND date='2025-02-01' AND expert_id='V4OBV'"
        ).fetchone()[0]
        conn.close()
        assert cnt == 1

    def test_secondary_score_is_norm(self, test_dbs):
        mdb, sdb = test_dbs
        w = OBVExpertWriter(mdb, sdb)
        w.run_symbol("FPT", "2025-02-01")

        conn = sqlite3.connect(sdb)
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT primary_score, secondary_score FROM expert_signals WHERE symbol='FPT' AND expert_id='V4OBV'"
        ).fetchone()
        conn.close()

        expected_norm = row["primary_score"] / 4.0
        assert abs(row["secondary_score"] - expected_norm) < 1e-9

    def test_bearish_market(self, bearish_dbs):
        mdb, sdb = bearish_dbs
        w = OBVExpertWriter(mdb, sdb)
        o = w.run_symbol("FPT", "2025-02-01")
        assert isinstance(o, OBVOutput)
        assert o.has_sufficient_data


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
