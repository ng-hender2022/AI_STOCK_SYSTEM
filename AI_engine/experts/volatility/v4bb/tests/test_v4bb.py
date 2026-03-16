"""
V4BB Bollinger Bands Expert Tests
"""

import sqlite3
import json
from datetime import date, timedelta
from pathlib import Path

import pytest
import numpy as np

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[5]))

from AI_engine.experts.volatility.v4bb.feature_builder import BBFeatureBuilder, BBFeatures
from AI_engine.experts.volatility.v4bb.signal_logic import BBSignalLogic, BBOutput
from AI_engine.experts.volatility.v4bb.expert_writer import BBExpertWriter


def _create_test_db(db_path: str, num_days=500, trend="up"):
    """Create test market.db with price data for BB testing."""
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
                      (s, s, "HOSE", None, None, t, "2024-01-01", None))

    base = date(2024, 1, 1)
    np.random.seed(42)
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
            vol = int(np.random.uniform(1e6, 3e6))

            conn.execute(
                "INSERT OR IGNORE INTO prices_daily VALUES (?,?,?,?,?,?,?,NULL,CURRENT_TIMESTAMP)",
                (s, d.isoformat(), round(price * 1.001, 2), round(h, 2), round(l, 2), round(price, 2),
                 vol),
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

class TestBBFeatureBuilder:

    def test_build(self, test_dbs):
        mdb, _ = test_dbs
        f = BBFeatureBuilder(mdb).build("FPT", "2025-06-01")
        assert f.has_sufficient_data
        assert f.bb_middle > 0
        assert f.bb_upper > f.bb_middle
        assert f.bb_lower < f.bb_middle

    def test_data_leakage(self, test_dbs):
        mdb, _ = test_dbs
        f = BBFeatureBuilder(mdb).build("FPT", "2025-06-01")
        assert f.data_cutoff_date < "2025-06-01"

    def test_pct_b_range(self, test_dbs):
        """For normal data %B should be reasonable (can exceed 0-1 range)."""
        mdb, _ = test_dbs
        f = BBFeatureBuilder(mdb).build("FPT", "2025-06-01")
        assert isinstance(f.bb_pct_b, float)
        # %B can exceed 0-1 but should be reasonable
        assert -1.0 < f.bb_pct_b < 2.0

    def test_bandwidth_positive(self, test_dbs):
        mdb, _ = test_dbs
        f = BBFeatureBuilder(mdb).build("FPT", "2025-06-01")
        assert f.bb_bandwidth > 0

    def test_bandwidth_pctile_range(self, test_dbs):
        mdb, _ = test_dbs
        f = BBFeatureBuilder(mdb).build("FPT", "2025-06-01")
        assert 0.0 <= f.bb_bandwidth_pctile <= 100.0

    def test_squeeze_is_bool(self, test_dbs):
        mdb, _ = test_dbs
        f = BBFeatureBuilder(mdb).build("FPT", "2025-06-01")
        assert isinstance(f.bb_squeeze_active, bool)

    def test_band_walk_values(self, test_dbs):
        mdb, _ = test_dbs
        f = BBFeatureBuilder(mdb).build("FPT", "2025-06-01")
        assert f.bb_band_walk in (-1, 0, 1)

    def test_insufficient_data(self, test_dbs):
        mdb, _ = test_dbs
        f = BBFeatureBuilder(mdb).build("FPT", "2024-02-01")
        assert not f.has_sufficient_data

    def test_batch(self, test_dbs):
        mdb, _ = test_dbs
        results = BBFeatureBuilder(mdb).build_batch(["FPT", "VNM", "HPG"], "2025-06-01")
        assert len(results) == 3
        for r in results:
            assert r.has_sufficient_data

    def test_position_score_range(self, test_dbs):
        mdb, _ = test_dbs
        f = BBFeatureBuilder(mdb).build("FPT", "2025-06-01")
        assert -2.0 <= f.bb_position_score <= 2.0


# --- Signal Logic ---

class TestBBSignalLogic:

    def test_score_range(self, test_dbs):
        mdb, _ = test_dbs
        f = BBFeatureBuilder(mdb).build("FPT", "2025-06-01")
        o = BBSignalLogic().compute(f)
        assert -4.0 <= o.bb_score <= 4.0

    def test_norm(self, test_dbs):
        mdb, _ = test_dbs
        f = BBFeatureBuilder(mdb).build("FPT", "2025-06-01")
        o = BBSignalLogic().compute(f)
        assert abs(o.bb_norm - o.bb_score / 4.0) < 1e-9

    def test_quality_range(self, test_dbs):
        mdb, _ = test_dbs
        f = BBFeatureBuilder(mdb).build("FPT", "2025-06-01")
        o = BBSignalLogic().compute(f)
        assert 0 <= o.signal_quality <= 4

    def test_signal_code_prefix(self, test_dbs):
        mdb, _ = test_dbs
        f = BBFeatureBuilder(mdb).build("FPT", "2025-06-01")
        o = BBSignalLogic().compute(f)
        assert o.signal_code.startswith("V4BB_")

    def test_deterministic(self, test_dbs):
        mdb, _ = test_dbs
        f = BBFeatureBuilder(mdb).build("FPT", "2025-06-01")
        o1 = BBSignalLogic().compute(f)
        o2 = BBSignalLogic().compute(f)
        assert o1.bb_score == o2.bb_score

    def test_bull_break(self):
        """Close above upper band -> V4BB_BULL_BREAK."""
        logic = BBSignalLogic()
        f = BBFeatures(
            symbol="TEST", date="2025-06-01", data_cutoff_date="2025-05-31",
            close=110.0, bb_middle=100.0, bb_upper=105.0, bb_lower=95.0,
            bb_pct_b=1.5, bb_bandwidth=0.10,
            bb_squeeze_active=False, bb_bandwidth_pctile=50.0,
            bb_band_walk=0,
            bb_position_score=2.0, bb_squeeze_score=0.0,
            bb_band_walk_score=0.0, bb_reversal_score=0.0,
            has_sufficient_data=True,
        )
        o = logic.compute(f)
        assert o.position_score == 2.0
        assert o.bb_score > 0
        assert o.signal_code == "V4BB_BULL_BREAK"

    def test_bear_break(self):
        """Close below lower band -> V4BB_BEAR_BREAK."""
        logic = BBSignalLogic()
        f = BBFeatures(
            symbol="TEST", date="2025-06-01", data_cutoff_date="2025-05-31",
            close=90.0, bb_middle=100.0, bb_upper=105.0, bb_lower=95.0,
            bb_pct_b=-0.5, bb_bandwidth=0.10,
            bb_squeeze_active=False, bb_bandwidth_pctile=50.0,
            bb_band_walk=0,
            bb_position_score=-2.0, bb_squeeze_score=0.0,
            bb_band_walk_score=0.0, bb_reversal_score=0.0,
            has_sufficient_data=True,
        )
        o = logic.compute(f)
        assert o.position_score == -2.0
        assert o.bb_score < 0
        assert o.signal_code == "V4BB_BEAR_BREAK"

    def test_bull_squeeze(self):
        """Squeeze active + break above upper -> V4BB_BULL_SQUEEZE."""
        logic = BBSignalLogic()
        f = BBFeatures(
            symbol="TEST", date="2025-06-01", data_cutoff_date="2025-05-31",
            close=106.0, bb_middle=100.0, bb_upper=105.0, bb_lower=95.0,
            bb_pct_b=1.1, bb_bandwidth=0.02,
            bb_squeeze_active=True, bb_bandwidth_pctile=5.0,
            bb_band_walk=0,
            bb_position_score=2.0, bb_squeeze_score=1.0,
            bb_band_walk_score=0.0, bb_reversal_score=0.0,
            has_sufficient_data=True,
        )
        o = logic.compute(f)
        assert o.squeeze_score == 1.0
        assert o.signal_code == "V4BB_BULL_SQUEEZE"
        assert o.signal_quality >= 3

    def test_bear_squeeze(self):
        """Squeeze active + break below lower -> V4BB_BEAR_SQUEEZE."""
        logic = BBSignalLogic()
        f = BBFeatures(
            symbol="TEST", date="2025-06-01", data_cutoff_date="2025-05-31",
            close=94.0, bb_middle=100.0, bb_upper=105.0, bb_lower=95.0,
            bb_pct_b=-0.1, bb_bandwidth=0.02,
            bb_squeeze_active=True, bb_bandwidth_pctile=5.0,
            bb_band_walk=0,
            bb_position_score=-2.0, bb_squeeze_score=-1.0,
            bb_band_walk_score=0.0, bb_reversal_score=0.0,
            has_sufficient_data=True,
        )
        o = logic.compute(f)
        assert o.squeeze_score == -1.0
        assert o.signal_code == "V4BB_BEAR_SQUEEZE"

    def test_bull_walk(self):
        """Band walk upper -> V4BB_BULL_WALK."""
        logic = BBSignalLogic()
        f = BBFeatures(
            symbol="TEST", date="2025-06-01", data_cutoff_date="2025-05-31",
            close=104.0, bb_middle=100.0, bb_upper=105.0, bb_lower=95.0,
            bb_pct_b=0.9, bb_bandwidth=0.10,
            bb_squeeze_active=False, bb_bandwidth_pctile=50.0,
            bb_band_walk=1,
            bb_position_score=1.0, bb_squeeze_score=0.0,
            bb_band_walk_score=0.5, bb_reversal_score=0.0,
            has_sufficient_data=True,
        )
        o = logic.compute(f)
        assert o.band_walk_score == 0.5
        assert o.signal_code == "V4BB_BULL_WALK"

    def test_bear_walk(self):
        """Band walk lower -> V4BB_BEAR_WALK."""
        logic = BBSignalLogic()
        f = BBFeatures(
            symbol="TEST", date="2025-06-01", data_cutoff_date="2025-05-31",
            close=96.0, bb_middle=100.0, bb_upper=105.0, bb_lower=95.0,
            bb_pct_b=0.1, bb_bandwidth=0.10,
            bb_squeeze_active=False, bb_bandwidth_pctile=50.0,
            bb_band_walk=-1,
            bb_position_score=-1.0, bb_squeeze_score=0.0,
            bb_band_walk_score=-0.5, bb_reversal_score=0.0,
            has_sufficient_data=True,
        )
        o = logic.compute(f)
        assert o.band_walk_score == -0.5
        assert o.signal_code == "V4BB_BEAR_WALK"

    def test_bull_reversal(self):
        """W-bottom pattern -> V4BB_BULL_REVERSAL."""
        logic = BBSignalLogic()
        f = BBFeatures(
            symbol="TEST", date="2025-06-01", data_cutoff_date="2025-05-31",
            close=100.0, bb_middle=100.0, bb_upper=105.0, bb_lower=95.0,
            bb_pct_b=0.5, bb_bandwidth=0.10,
            bb_squeeze_active=False, bb_bandwidth_pctile=50.0,
            bb_band_walk=0,
            bb_position_score=0.0, bb_squeeze_score=0.0,
            bb_band_walk_score=0.0, bb_reversal_score=0.5,
            has_sufficient_data=True,
        )
        o = logic.compute(f)
        assert o.reversal_score == 0.5
        assert o.signal_code == "V4BB_BULL_REVERSAL"

    def test_bear_reversal(self):
        """M-top pattern -> V4BB_BEAR_REVERSAL."""
        logic = BBSignalLogic()
        f = BBFeatures(
            symbol="TEST", date="2025-06-01", data_cutoff_date="2025-05-31",
            close=100.0, bb_middle=100.0, bb_upper=105.0, bb_lower=95.0,
            bb_pct_b=0.5, bb_bandwidth=0.10,
            bb_squeeze_active=False, bb_bandwidth_pctile=50.0,
            bb_band_walk=0,
            bb_position_score=0.0, bb_squeeze_score=0.0,
            bb_band_walk_score=0.0, bb_reversal_score=-0.5,
            has_sufficient_data=True,
        )
        o = logic.compute(f)
        assert o.reversal_score == -0.5
        assert o.signal_code == "V4BB_BEAR_REVERSAL"

    def test_neut_squeeze(self):
        """Squeeze active, no break -> V4BB_NEUT_SQUEEZE."""
        logic = BBSignalLogic()
        f = BBFeatures(
            symbol="TEST", date="2025-06-01", data_cutoff_date="2025-05-31",
            close=100.0, bb_middle=100.0, bb_upper=105.0, bb_lower=95.0,
            bb_pct_b=0.5, bb_bandwidth=0.02,
            bb_squeeze_active=True, bb_bandwidth_pctile=5.0,
            bb_band_walk=0,
            bb_position_score=0.0, bb_squeeze_score=0.0,
            bb_band_walk_score=0.0, bb_reversal_score=0.0,
            has_sufficient_data=True,
        )
        o = logic.compute(f)
        assert o.signal_code == "V4BB_NEUT_SQUEEZE"

    def test_neut_mid(self):
        """Price near middle, no squeeze -> V4BB_NEUT_MID."""
        logic = BBSignalLogic()
        f = BBFeatures(
            symbol="TEST", date="2025-06-01", data_cutoff_date="2025-05-31",
            close=100.0, bb_middle=100.0, bb_upper=105.0, bb_lower=95.0,
            bb_pct_b=0.5, bb_bandwidth=0.10,
            bb_squeeze_active=False, bb_bandwidth_pctile=50.0,
            bb_band_walk=0,
            bb_position_score=0.0, bb_squeeze_score=0.0,
            bb_band_walk_score=0.0, bb_reversal_score=0.0,
            has_sufficient_data=True,
        )
        o = logic.compute(f)
        assert o.signal_code == "V4BB_NEUT_MID"
        assert o.signal_quality == 0

    def test_score_clamp(self):
        """Score must be clamped to -4..+4."""
        logic = BBSignalLogic()
        f = BBFeatures(
            symbol="TEST", date="2025-06-01", data_cutoff_date="2025-05-31",
            close=110.0, bb_middle=100.0, bb_upper=105.0, bb_lower=95.0,
            bb_pct_b=1.5, bb_bandwidth=0.02,
            bb_squeeze_active=True, bb_bandwidth_pctile=5.0,
            bb_band_walk=1,
            bb_position_score=2.0, bb_squeeze_score=1.0,
            bb_band_walk_score=0.5, bb_reversal_score=0.5,
            has_sufficient_data=True,
        )
        o = logic.compute(f)
        assert -4.0 <= o.bb_score <= 4.0

    def test_insufficient_data_zero(self):
        """Insufficient data should return zero scores."""
        logic = BBSignalLogic()
        f = BBFeatures(
            symbol="TEST", date="2025-06-01", data_cutoff_date="",
            has_sufficient_data=False,
        )
        o = logic.compute(f)
        assert o.bb_score == 0.0
        assert not o.has_sufficient_data


# --- Expert Writer ---

class TestBBExpertWriter:

    def test_run_symbol(self, test_dbs):
        mdb, sdb = test_dbs
        w = BBExpertWriter(mdb, sdb)
        o = w.run_symbol("FPT", "2025-06-01")
        assert isinstance(o, BBOutput)

        conn = sqlite3.connect(sdb)
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT * FROM expert_signals WHERE symbol='FPT' AND expert_id='V4BB'"
        ).fetchone()
        conn.close()
        assert row is not None
        assert -4 <= row["primary_score"] <= 4

    def test_metadata_fields(self, test_dbs):
        """Metadata must include all required fields."""
        mdb, sdb = test_dbs
        w = BBExpertWriter(mdb, sdb)
        w.run_symbol("FPT", "2025-06-01")

        conn = sqlite3.connect(sdb)
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT metadata_json FROM expert_signals WHERE symbol='FPT' AND expert_id='V4BB'"
        ).fetchone()
        conn.close()

        meta = json.loads(row["metadata_json"])
        required = [
            "bb_pct_b", "bb_bandwidth", "bb_squeeze_active", "bb_position",
            "bb_bandwidth_pctile", "bb_band_walk", "bb_score", "bb_norm",
        ]
        for key in required:
            assert key in meta, f"Missing metadata key: {key}"

    def test_metadata_types(self, test_dbs):
        """Ensure numpy bools are cast to Python bool/int for JSON."""
        mdb, sdb = test_dbs
        w = BBExpertWriter(mdb, sdb)
        w.run_symbol("FPT", "2025-06-01")

        conn = sqlite3.connect(sdb)
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT metadata_json FROM expert_signals WHERE symbol='FPT' AND expert_id='V4BB'"
        ).fetchone()
        conn.close()

        meta = json.loads(row["metadata_json"])
        assert isinstance(meta["bb_squeeze_active"], bool)
        assert isinstance(meta["bb_band_walk"], int)
        assert meta["bb_band_walk"] in (-1, 0, 1)
        assert isinstance(meta["bb_pct_b"], float)
        assert isinstance(meta["bb_bandwidth"], float)

    def test_run_all(self, test_dbs):
        mdb, sdb = test_dbs
        w = BBExpertWriter(mdb, sdb)
        results = w.run_all("2025-06-01", symbols=["FPT", "VNM"])
        assert len(results) == 2

    def test_idempotent(self, test_dbs):
        mdb, sdb = test_dbs
        w = BBExpertWriter(mdb, sdb)
        w.run_symbol("FPT", "2025-06-01")
        w.run_symbol("FPT", "2025-06-01")
        conn = sqlite3.connect(sdb)
        cnt = conn.execute(
            "SELECT COUNT(*) FROM expert_signals WHERE symbol='FPT' AND date='2025-06-01' AND expert_id='V4BB'"
        ).fetchone()[0]
        conn.close()
        assert cnt == 1

    def test_secondary_score_is_norm(self, test_dbs):
        """secondary_score in DB must equal bb_norm = bb_score / 4."""
        mdb, sdb = test_dbs
        w = BBExpertWriter(mdb, sdb)
        w.run_symbol("FPT", "2025-06-01")

        conn = sqlite3.connect(sdb)
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT primary_score, secondary_score FROM expert_signals WHERE symbol='FPT' AND expert_id='V4BB'"
        ).fetchone()
        conn.close()
        assert abs(row["secondary_score"] - row["primary_score"] / 4.0) < 1e-9


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
