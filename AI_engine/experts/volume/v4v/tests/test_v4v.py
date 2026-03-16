"""
V4V Volume Behavior Expert Tests
"""

import sqlite3
import json
from datetime import date, timedelta
from pathlib import Path

import pytest
import numpy as np

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[5]))

from AI_engine.experts.volume.v4v.feature_builder import VolFeatureBuilder, VolFeatures
from AI_engine.experts.volume.v4v.signal_logic import VolSignalLogic, VolOutput
from AI_engine.experts.volume.v4v.expert_writer import VolExpertWriter


def _create_test_db(db_path: str, num_days=400, trend="up", vol_pattern="normal"):
    """Create test market.db with price and volume data.

    vol_pattern:
        normal  - random volume around 2M
        surge   - last 5 days have 3x normal volume
        drying  - last 10 days have very low volume
    """
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
    np.random.seed(42)
    for s in ["FPT", "VNM", "HPG", "VNINDEX"]:
        price = 100.0 if s != "VNINDEX" else 1200.0
        day_count = 0
        for i in range(num_days):
            d = base + timedelta(days=i)
            if d.weekday() >= 5:
                continue
            day_count += 1
            drift = 0.0004 if trend == "up" else (-0.0004 if trend == "down" else 0)
            price *= 1 + drift + np.random.normal(0, 0.01)
            h = price * 1.005
            l = price * 0.995

            # Volume pattern
            base_vol = 2_000_000
            if vol_pattern == "surge" and day_count > (num_days * 0.7 - 5):
                vol = int(np.random.uniform(5e6, 8e6))  # 3-4x normal
            elif vol_pattern == "drying" and day_count > (num_days * 0.7 - 10):
                vol = int(np.random.uniform(200_000, 500_000))  # very low
            else:
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
def surge_dbs(tmp_path):
    mdb = str(tmp_path / "market.db")
    sdb = str(tmp_path / "signals.db")
    _create_test_db(mdb, vol_pattern="surge")
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

class TestVolFeatureBuilder:

    def test_build(self, test_dbs):
        mdb, _ = test_dbs
        f = VolFeatureBuilder(mdb).build("FPT", "2025-02-01")
        assert f.has_sufficient_data
        assert f.vol_ratio > 0
        assert f.volume > 0

    def test_data_leakage(self, test_dbs):
        mdb, _ = test_dbs
        f = VolFeatureBuilder(mdb).build("FPT", "2025-02-01")
        assert f.data_cutoff_date < "2025-02-01"

    def test_vol_ratio_positive(self, test_dbs):
        mdb, _ = test_dbs
        f = VolFeatureBuilder(mdb).build("FPT", "2025-02-01")
        assert f.vol_ratio > 0

    def test_vol_trend(self, test_dbs):
        mdb, _ = test_dbs
        f = VolFeatureBuilder(mdb).build("FPT", "2025-02-01")
        assert isinstance(f.vol_trend_5, float)
        assert isinstance(f.vol_trend_10, float)
        assert f.vol_trend_5 > 0
        assert f.vol_trend_10 > 0

    def test_price_return(self, test_dbs):
        mdb, _ = test_dbs
        f = VolFeatureBuilder(mdb).build("FPT", "2025-02-01")
        assert isinstance(f.price_return, float)
        assert -1.0 < f.price_return < 1.0

    def test_climax_is_bool(self, test_dbs):
        mdb, _ = test_dbs
        f = VolFeatureBuilder(mdb).build("FPT", "2025-02-01")
        assert isinstance(f.climax, bool)

    def test_insufficient_data(self, test_dbs):
        mdb, _ = test_dbs
        f = VolFeatureBuilder(mdb).build("FPT", "2024-01-10")
        assert not f.has_sufficient_data

    def test_batch(self, test_dbs):
        mdb, _ = test_dbs
        results = VolFeatureBuilder(mdb).build_batch(["FPT", "VNM", "HPG"], "2025-02-01")
        assert len(results) == 3
        for r in results:
            assert r.has_sufficient_data


# --- Signal Logic ---

class TestVolSignalLogic:

    def test_score_range(self, test_dbs):
        mdb, _ = test_dbs
        f = VolFeatureBuilder(mdb).build("FPT", "2025-02-01")
        o = VolSignalLogic().compute(f)
        assert -4.0 <= o.volume_score <= 4.0

    def test_norm(self, test_dbs):
        mdb, _ = test_dbs
        f = VolFeatureBuilder(mdb).build("FPT", "2025-02-01")
        o = VolSignalLogic().compute(f)
        assert abs(o.volume_norm - o.volume_score / 4.0) < 1e-9

    def test_quality_range(self, test_dbs):
        mdb, _ = test_dbs
        f = VolFeatureBuilder(mdb).build("FPT", "2025-02-01")
        o = VolSignalLogic().compute(f)
        assert 0 <= o.signal_quality <= 4

    def test_signal_code_prefix(self, test_dbs):
        mdb, _ = test_dbs
        f = VolFeatureBuilder(mdb).build("FPT", "2025-02-01")
        o = VolSignalLogic().compute(f)
        assert o.signal_code.startswith("V4V_")

    def test_deterministic(self, test_dbs):
        mdb, _ = test_dbs
        f = VolFeatureBuilder(mdb).build("FPT", "2025-02-01")
        o1 = VolSignalLogic().compute(f)
        o2 = VolSignalLogic().compute(f)
        assert o1.volume_score == o2.volume_score

    def test_bull_expand(self):
        """Price up + volume surge = V4V_BULL_EXPAND, score positive."""
        logic = VolSignalLogic()
        f = VolFeatures(
            symbol="TEST", date="2025-02-01", data_cutoff_date="2025-01-31",
            close=105.0, prev_close=100.0, volume=5_000_000,
            price_return=0.05, vol_ratio=2.5, vol_trend_5=1.5,
            vol_trend_10=1.2, climax=False,
            has_sufficient_data=True,
        )
        o = logic.compute(f)
        assert o.confirmation_score == 2.0
        assert o.trend_score == 1.0
        assert o.volume_score > 0
        assert o.signal_code == "V4V_BULL_EXPAND"

    def test_bear_expand(self):
        """Price down + volume surge = V4V_BEAR_EXPAND, score negative."""
        logic = VolSignalLogic()
        f = VolFeatures(
            symbol="TEST", date="2025-02-01", data_cutoff_date="2025-01-31",
            close=95.0, prev_close=100.0, volume=5_000_000,
            price_return=-0.05, vol_ratio=2.5, vol_trend_5=1.5,
            vol_trend_10=1.2, climax=False,
            has_sufficient_data=True,
        )
        o = logic.compute(f)
        assert o.confirmation_score == -2.0
        assert o.volume_score < 0
        assert o.signal_code == "V4V_BEAR_EXPAND"

    def test_bear_div_weak_rally(self):
        """Price up + volume declining = V4V_BEAR_DIV (weak rally)."""
        logic = VolSignalLogic()
        f = VolFeatures(
            symbol="TEST", date="2025-02-01", data_cutoff_date="2025-01-31",
            close=102.0, prev_close=100.0, volume=1_500_000,
            price_return=0.02, vol_ratio=0.9, vol_trend_5=0.8,
            vol_trend_10=0.85, climax=False,
            has_sufficient_data=True,
        )
        o = logic.compute(f)
        assert o.divergence_score == -1.0
        assert o.signal_code == "V4V_BEAR_DIV"

    def test_bull_div_exhaustion(self):
        """Price down + volume declining = V4V_BULL_DIV (exhausted selling)."""
        logic = VolSignalLogic()
        f = VolFeatures(
            symbol="TEST", date="2025-02-01", data_cutoff_date="2025-01-31",
            close=98.0, prev_close=100.0, volume=1_500_000,
            price_return=-0.02, vol_ratio=0.9, vol_trend_5=0.8,
            vol_trend_10=0.85, climax=False,
            has_sufficient_data=True,
        )
        o = logic.compute(f)
        assert o.divergence_score == 1.0
        assert o.signal_code == "V4V_BULL_DIV"

    def test_climax_bottom(self):
        """Climax volume + price down = V4V_BULL_CLIMAX_BOT."""
        logic = VolSignalLogic()
        f = VolFeatures(
            symbol="TEST", date="2025-02-01", data_cutoff_date="2025-01-31",
            close=90.0, prev_close=100.0, volume=10_000_000,
            price_return=-0.10, vol_ratio=3.5, vol_trend_5=2.0,
            vol_trend_10=1.5, climax=True,
            has_sufficient_data=True,
        )
        o = logic.compute(f)
        assert o.signal_code == "V4V_BULL_CLIMAX_BOT"
        assert o.signal_quality == 4

    def test_climax_top(self):
        """Climax volume + price up = V4V_BEAR_CLIMAX_TOP."""
        logic = VolSignalLogic()
        f = VolFeatures(
            symbol="TEST", date="2025-02-01", data_cutoff_date="2025-01-31",
            close=110.0, prev_close=100.0, volume=10_000_000,
            price_return=0.10, vol_ratio=3.5, vol_trend_5=2.0,
            vol_trend_10=1.5, climax=True,
            has_sufficient_data=True,
        )
        o = logic.compute(f)
        assert o.signal_code == "V4V_BEAR_CLIMAX_TOP"
        assert o.signal_quality == 4

    def test_drying(self):
        """Very low volume = V4V_NEUT_DRY."""
        logic = VolSignalLogic()
        f = VolFeatures(
            symbol="TEST", date="2025-02-01", data_cutoff_date="2025-01-31",
            close=100.0, prev_close=100.0, volume=300_000,
            price_return=0.0, vol_ratio=0.3, vol_trend_5=0.6,
            vol_trend_10=0.7, climax=False,
            has_sufficient_data=True,
        )
        o = logic.compute(f)
        assert o.signal_code == "V4V_NEUT_DRY"

    def test_score_clamp(self):
        """Score must be clamped to -4..+4."""
        logic = VolSignalLogic()
        # Max possible: confirmation=+2, trend=+1, divergence=0 (can't have div with surge)
        f = VolFeatures(
            symbol="TEST", date="2025-02-01", data_cutoff_date="2025-01-31",
            close=110.0, prev_close=100.0, volume=8_000_000,
            price_return=0.10, vol_ratio=2.5, vol_trend_5=1.5,
            vol_trend_10=1.3, climax=False,
            has_sufficient_data=True,
        )
        o = logic.compute(f)
        assert -4.0 <= o.volume_score <= 4.0

    def test_insufficient_data_zero(self):
        """Insufficient data should return zero scores."""
        logic = VolSignalLogic()
        f = VolFeatures(
            symbol="TEST", date="2025-02-01", data_cutoff_date="",
            has_sufficient_data=False,
        )
        o = logic.compute(f)
        assert o.volume_score == 0.0
        assert not o.has_sufficient_data


# --- Expert Writer ---

class TestVolExpertWriter:

    def test_run_symbol(self, test_dbs):
        mdb, sdb = test_dbs
        w = VolExpertWriter(mdb, sdb)
        o = w.run_symbol("FPT", "2025-02-01")
        assert isinstance(o, VolOutput)

        conn = sqlite3.connect(sdb)
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT * FROM expert_signals WHERE symbol='FPT' AND expert_id='V4V'"
        ).fetchone()
        conn.close()
        assert row is not None
        assert -4 <= row["primary_score"] <= 4

    def test_metadata_fields(self, test_dbs):
        """Metadata must include all required fields."""
        mdb, sdb = test_dbs
        w = VolExpertWriter(mdb, sdb)
        w.run_symbol("FPT", "2025-02-01")

        conn = sqlite3.connect(sdb)
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT metadata_json FROM expert_signals WHERE symbol='FPT' AND expert_id='V4V'"
        ).fetchone()
        conn.close()

        meta = json.loads(row["metadata_json"])
        required = [
            "vol_ratio", "vol_trend_5", "vol_trend_10",
            "vol_price_confirm", "vol_climax", "vol_drying", "vol_expansion",
            "volume_norm", "confirmation_score", "trend_score", "divergence_score",
        ]
        for key in required:
            assert key in meta, f"Missing metadata key: {key}"

    def test_metadata_types(self, test_dbs):
        """Ensure numpy bools are cast to Python bool/int for JSON."""
        mdb, sdb = test_dbs
        w = VolExpertWriter(mdb, sdb)
        w.run_symbol("FPT", "2025-02-01")

        conn = sqlite3.connect(sdb)
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT metadata_json FROM expert_signals WHERE symbol='FPT' AND expert_id='V4V'"
        ).fetchone()
        conn.close()

        meta = json.loads(row["metadata_json"])
        # vol_climax and vol_drying should be int 0 or 1
        assert meta["vol_climax"] in (0, 1)
        assert meta["vol_drying"] in (0, 1)
        assert meta["vol_expansion"] in (0, 1)
        assert meta["vol_price_confirm"] in (-1, 0, 1)

    def test_run_all(self, test_dbs):
        mdb, sdb = test_dbs
        w = VolExpertWriter(mdb, sdb)
        results = w.run_all("2025-02-01", symbols=["FPT", "VNM"])
        assert len(results) == 2

    def test_idempotent(self, test_dbs):
        mdb, sdb = test_dbs
        w = VolExpertWriter(mdb, sdb)
        w.run_symbol("FPT", "2025-02-01")
        w.run_symbol("FPT", "2025-02-01")
        conn = sqlite3.connect(sdb)
        cnt = conn.execute(
            "SELECT COUNT(*) FROM expert_signals WHERE symbol='FPT' AND date='2025-02-01' AND expert_id='V4V'"
        ).fetchone()[0]
        conn.close()
        assert cnt == 1

    def test_secondary_score_is_norm(self, test_dbs):
        """secondary_score in DB must equal volume_norm = volume_score / 4."""
        mdb, sdb = test_dbs
        w = VolExpertWriter(mdb, sdb)
        w.run_symbol("FPT", "2025-02-01")

        conn = sqlite3.connect(sdb)
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT primary_score, secondary_score FROM expert_signals WHERE symbol='FPT' AND expert_id='V4V'"
        ).fetchone()
        conn.close()
        assert abs(row["secondary_score"] - row["primary_score"] / 4.0) < 1e-9


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
