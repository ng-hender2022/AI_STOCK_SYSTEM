"""
V4ATR ATR Volatility Expert Tests
"""

import sqlite3
import json
from datetime import date, timedelta
from pathlib import Path

import pytest
import numpy as np

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[5]))

from AI_engine.experts.volatility.v4atr.feature_builder import ATRFeatureBuilder, ATRFeatures
from AI_engine.experts.volatility.v4atr.signal_logic import ATRSignalLogic, ATROutput
from AI_engine.experts.volatility.v4atr.expert_writer import ATRExpertWriter


def _create_test_db(db_path: str, num_days=500, trend="up", vol_mode="normal"):
    """Create test market.db with OHLC data.

    vol_mode:
        normal   - steady volatility
        spike    - last 10 days have large range (high ATR)
        squeeze  - last 20 days have very tight range (low ATR)
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
                      (s, s, "HOSE", None, None, t, "2024-01-01", None))

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

            # Volatility pattern for range
            if vol_mode == "spike" and day_count > (num_days * 0.7 - 10):
                spread = 0.04  # 4% range
            elif vol_mode == "squeeze" and day_count > (num_days * 0.7 - 20):
                spread = 0.002  # 0.2% range
            else:
                spread = 0.01  # 1% range

            h = price * (1 + spread / 2)
            l = price * (1 - spread / 2)
            vol = int(np.random.uniform(1e6, 3e6))

            conn.execute(
                "INSERT OR IGNORE INTO prices_daily VALUES (?,?,?,?,?,?,?,NULL,CURRENT_TIMESTAMP)",
                (s, d.isoformat(), round(price * 1.001, 2), round(h, 2),
                 round(l, 2), round(price, 2), vol),
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
def spike_dbs(tmp_path):
    mdb = str(tmp_path / "market.db")
    sdb = str(tmp_path / "signals.db")
    _create_test_db(mdb, vol_mode="spike")
    _create_signals_db(sdb)
    return mdb, sdb


@pytest.fixture
def squeeze_dbs(tmp_path):
    mdb = str(tmp_path / "market.db")
    sdb = str(tmp_path / "signals.db")
    _create_test_db(mdb, vol_mode="squeeze")
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

class TestATRFeatureBuilder:

    def test_build(self, test_dbs):
        mdb, _ = test_dbs
        f = ATRFeatureBuilder(mdb).build("FPT", "2025-06-01")
        assert f.has_sufficient_data
        assert f.atr_value > 0
        assert f.atr_pct > 0
        assert f.close > 0

    def test_data_leakage(self, test_dbs):
        mdb, _ = test_dbs
        f = ATRFeatureBuilder(mdb).build("FPT", "2025-06-01")
        assert f.data_cutoff_date < "2025-06-01"

    def test_atr_pct_positive(self, test_dbs):
        mdb, _ = test_dbs
        f = ATRFeatureBuilder(mdb).build("FPT", "2025-06-01")
        assert f.atr_pct > 0

    def test_percentile_range(self, test_dbs):
        mdb, _ = test_dbs
        f = ATRFeatureBuilder(mdb).build("FPT", "2025-06-01")
        assert 0 <= f.atr_percentile <= 100

    def test_score_range(self, test_dbs):
        mdb, _ = test_dbs
        f = ATRFeatureBuilder(mdb).build("FPT", "2025-06-01")
        assert 0 <= f.atr_score <= 4

    def test_norm_equals_score_div_4(self, test_dbs):
        mdb, _ = test_dbs
        f = ATRFeatureBuilder(mdb).build("FPT", "2025-06-01")
        assert abs(f.atr_norm - f.atr_score / 4.0) < 1e-9

    def test_atr_ratio_positive(self, test_dbs):
        mdb, _ = test_dbs
        f = ATRFeatureBuilder(mdb).build("FPT", "2025-06-01")
        assert f.atr_ratio > 0

    def test_atr_change_5d(self, test_dbs):
        mdb, _ = test_dbs
        f = ATRFeatureBuilder(mdb).build("FPT", "2025-06-01")
        assert isinstance(f.atr_change_5d, float)

    def test_expanding_contracting_are_bool(self, test_dbs):
        mdb, _ = test_dbs
        f = ATRFeatureBuilder(mdb).build("FPT", "2025-06-01")
        assert isinstance(f.atr_expanding, bool)
        assert isinstance(f.atr_contracting, bool)
        # Cannot be both expanding and contracting
        assert not (f.atr_expanding and f.atr_contracting)

    def test_vol_regime_valid(self, test_dbs):
        mdb, _ = test_dbs
        f = ATRFeatureBuilder(mdb).build("FPT", "2025-06-01")
        assert f.vol_regime in ("SQUEEZE", "NORMAL", "EXPANSION", "CLIMAX")

    def test_insufficient_data(self, test_dbs):
        mdb, _ = test_dbs
        f = ATRFeatureBuilder(mdb).build("FPT", "2024-02-01")
        assert not f.has_sufficient_data

    def test_batch(self, test_dbs):
        mdb, _ = test_dbs
        results = ATRFeatureBuilder(mdb).build_batch(["FPT", "VNM", "HPG"], "2025-06-01")
        assert len(results) == 3
        for r in results:
            assert r.has_sufficient_data

    def test_price_return(self, test_dbs):
        mdb, _ = test_dbs
        f = ATRFeatureBuilder(mdb).build("FPT", "2025-06-01")
        assert isinstance(f.price_return, float)
        assert -1.0 < f.price_return < 1.0


# --- Signal Logic ---

class TestATRSignalLogic:

    def test_score_range(self, test_dbs):
        mdb, _ = test_dbs
        f = ATRFeatureBuilder(mdb).build("FPT", "2025-06-01")
        o = ATRSignalLogic().compute(f)
        assert 0 <= o.atr_score <= 4

    def test_norm(self, test_dbs):
        mdb, _ = test_dbs
        f = ATRFeatureBuilder(mdb).build("FPT", "2025-06-01")
        o = ATRSignalLogic().compute(f)
        assert abs(o.atr_norm - o.atr_score / 4.0) < 1e-9

    def test_quality_range(self, test_dbs):
        mdb, _ = test_dbs
        f = ATRFeatureBuilder(mdb).build("FPT", "2025-06-01")
        o = ATRSignalLogic().compute(f)
        assert 0 <= o.signal_quality <= 4

    def test_signal_code_prefix(self, test_dbs):
        mdb, _ = test_dbs
        f = ATRFeatureBuilder(mdb).build("FPT", "2025-06-01")
        o = ATRSignalLogic().compute(f)
        assert o.signal_code.startswith("V4ATR_")

    def test_valid_signal_codes(self, test_dbs):
        mdb, _ = test_dbs
        f = ATRFeatureBuilder(mdb).build("FPT", "2025-06-01")
        o = ATRSignalLogic().compute(f)
        valid_codes = {
            "V4ATR_NEUT_SQUEEZE", "V4ATR_BULL_EXPAND", "V4ATR_BEAR_EXPAND",
            "V4ATR_BEAR_EXTREME", "V4ATR_NEUT_CLIMAX", "V4ATR_NEUT_NORMAL",
        }
        assert o.signal_code in valid_codes

    def test_deterministic(self, test_dbs):
        mdb, _ = test_dbs
        f = ATRFeatureBuilder(mdb).build("FPT", "2025-06-01")
        o1 = ATRSignalLogic().compute(f)
        o2 = ATRSignalLogic().compute(f)
        assert o1.atr_score == o2.atr_score
        assert o1.signal_code == o2.signal_code

    def test_squeeze_signal(self):
        """Low percentile + contracting = V4ATR_NEUT_SQUEEZE."""
        logic = ATRSignalLogic()
        f = ATRFeatures(
            symbol="TEST", date="2025-06-01", data_cutoff_date="2025-05-30",
            atr_value=0.5, atr_pct=0.5, atr_percentile=10.0,
            atr_change_5d=-0.15, atr_ratio=0.6, atr_expanding=False,
            atr_contracting=True, atr_score=0, atr_norm=0.0,
            vol_regime="SQUEEZE", price_return=0.001, close=100.0,
            has_sufficient_data=True,
        )
        o = logic.compute(f)
        assert o.signal_code == "V4ATR_NEUT_SQUEEZE"

    def test_bull_expand_signal(self):
        """Expanding ATR + price up = V4ATR_BULL_EXPAND."""
        logic = ATRSignalLogic()
        f = ATRFeatures(
            symbol="TEST", date="2025-06-01", data_cutoff_date="2025-05-30",
            atr_value=2.0, atr_pct=2.0, atr_percentile=70.0,
            atr_change_5d=0.15, atr_ratio=1.3, atr_expanding=True,
            atr_contracting=False, atr_score=3, atr_norm=0.75,
            vol_regime="NORMAL", price_return=0.02, close=100.0,
            has_sufficient_data=True,
        )
        o = logic.compute(f)
        assert o.signal_code == "V4ATR_BULL_EXPAND"

    def test_bear_expand_signal(self):
        """Expanding ATR + price down = V4ATR_BEAR_EXPAND."""
        logic = ATRSignalLogic()
        f = ATRFeatures(
            symbol="TEST", date="2025-06-01", data_cutoff_date="2025-05-30",
            atr_value=2.0, atr_pct=2.0, atr_percentile=70.0,
            atr_change_5d=0.15, atr_ratio=1.3, atr_expanding=True,
            atr_contracting=False, atr_score=3, atr_norm=0.75,
            vol_regime="NORMAL", price_return=-0.02, close=100.0,
            has_sufficient_data=True,
        )
        o = logic.compute(f)
        assert o.signal_code == "V4ATR_BEAR_EXPAND"

    def test_bear_extreme_signal(self):
        """Very high percentile + price down = V4ATR_BEAR_EXTREME."""
        logic = ATRSignalLogic()
        f = ATRFeatures(
            symbol="TEST", date="2025-06-01", data_cutoff_date="2025-05-30",
            atr_value=5.0, atr_pct=5.0, atr_percentile=97.0,
            atr_change_5d=0.25, atr_ratio=2.0, atr_expanding=True,
            atr_contracting=False, atr_score=4, atr_norm=1.0,
            vol_regime="CLIMAX", price_return=-0.05, close=100.0,
            has_sufficient_data=True,
        )
        o = logic.compute(f)
        assert o.signal_code == "V4ATR_BEAR_EXTREME"

    def test_climax_signal(self):
        """Very high percentile + price up = V4ATR_NEUT_CLIMAX."""
        logic = ATRSignalLogic()
        f = ATRFeatures(
            symbol="TEST", date="2025-06-01", data_cutoff_date="2025-05-30",
            atr_value=5.0, atr_pct=5.0, atr_percentile=97.0,
            atr_change_5d=0.05, atr_ratio=2.0, atr_expanding=False,
            atr_contracting=False, atr_score=4, atr_norm=1.0,
            vol_regime="CLIMAX", price_return=0.01, close=100.0,
            has_sufficient_data=True,
        )
        o = logic.compute(f)
        assert o.signal_code == "V4ATR_NEUT_CLIMAX"

    def test_normal_signal(self):
        """Mid-range percentile, stable = V4ATR_NEUT_NORMAL."""
        logic = ATRSignalLogic()
        f = ATRFeatures(
            symbol="TEST", date="2025-06-01", data_cutoff_date="2025-05-30",
            atr_value=1.0, atr_pct=1.0, atr_percentile=50.0,
            atr_change_5d=0.02, atr_ratio=1.0, atr_expanding=False,
            atr_contracting=False, atr_score=2, atr_norm=0.5,
            vol_regime="NORMAL", price_return=0.001, close=100.0,
            has_sufficient_data=True,
        )
        o = logic.compute(f)
        assert o.signal_code == "V4ATR_NEUT_NORMAL"

    def test_insufficient_data_zero(self):
        """Insufficient data should return zero scores."""
        logic = ATRSignalLogic()
        f = ATRFeatures(
            symbol="TEST", date="2025-06-01", data_cutoff_date="",
            has_sufficient_data=False,
        )
        o = logic.compute(f)
        assert o.atr_score == 0
        assert not o.has_sufficient_data


# --- Expert Writer ---

class TestATRExpertWriter:

    def test_run_symbol(self, test_dbs):
        mdb, sdb = test_dbs
        w = ATRExpertWriter(mdb, sdb)
        o = w.run_symbol("FPT", "2025-06-01")
        assert isinstance(o, ATROutput)

        conn = sqlite3.connect(sdb)
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT * FROM expert_signals WHERE symbol='FPT' AND expert_id='V4ATR'"
        ).fetchone()
        conn.close()
        assert row is not None
        assert 0 <= row["primary_score"] <= 4

    def test_metadata_fields(self, test_dbs):
        """Metadata must include all required fields."""
        mdb, sdb = test_dbs
        w = ATRExpertWriter(mdb, sdb)
        w.run_symbol("FPT", "2025-06-01")

        conn = sqlite3.connect(sdb)
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT metadata_json FROM expert_signals WHERE symbol='FPT' AND expert_id='V4ATR'"
        ).fetchone()
        conn.close()

        meta = json.loads(row["metadata_json"])
        required = [
            "atr_value", "atr_pct", "atr_percentile", "atr_ratio",
            "atr_change_5d", "atr_expanding", "atr_contracting",
            "vol_regime", "atr_score", "atr_norm",
        ]
        for key in required:
            assert key in meta, f"Missing metadata key: {key}"

    def test_metadata_types(self, test_dbs):
        """Ensure numpy bools are cast to Python bool/int for JSON."""
        mdb, sdb = test_dbs
        w = ATRExpertWriter(mdb, sdb)
        w.run_symbol("FPT", "2025-06-01")

        conn = sqlite3.connect(sdb)
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT metadata_json FROM expert_signals WHERE symbol='FPT' AND expert_id='V4ATR'"
        ).fetchone()
        conn.close()

        meta = json.loads(row["metadata_json"])
        assert isinstance(meta["atr_expanding"], bool)
        assert isinstance(meta["atr_contracting"], bool)
        assert isinstance(meta["atr_score"], int)
        assert isinstance(meta["vol_regime"], str)
        assert meta["vol_regime"] in ("SQUEEZE", "NORMAL", "EXPANSION", "CLIMAX")

    def test_run_all(self, test_dbs):
        mdb, sdb = test_dbs
        w = ATRExpertWriter(mdb, sdb)
        results = w.run_all("2025-06-01", symbols=["FPT", "VNM"])
        assert len(results) == 2

    def test_idempotent(self, test_dbs):
        mdb, sdb = test_dbs
        w = ATRExpertWriter(mdb, sdb)
        w.run_symbol("FPT", "2025-06-01")
        w.run_symbol("FPT", "2025-06-01")
        conn = sqlite3.connect(sdb)
        cnt = conn.execute(
            "SELECT COUNT(*) FROM expert_signals WHERE symbol='FPT' AND date='2025-06-01' AND expert_id='V4ATR'"
        ).fetchone()[0]
        conn.close()
        assert cnt == 1

    def test_secondary_score_is_norm(self, test_dbs):
        """secondary_score in DB must equal atr_norm = atr_score / 4."""
        mdb, sdb = test_dbs
        w = ATRExpertWriter(mdb, sdb)
        w.run_symbol("FPT", "2025-06-01")

        conn = sqlite3.connect(sdb)
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT primary_score, secondary_score FROM expert_signals WHERE symbol='FPT' AND expert_id='V4ATR'"
        ).fetchone()
        conn.close()
        assert abs(row["secondary_score"] - row["primary_score"] / 4.0) < 1e-9

    def test_primary_score_is_integer_0_to_4(self, test_dbs):
        """primary_score must be integer in [0, 4]."""
        mdb, sdb = test_dbs
        w = ATRExpertWriter(mdb, sdb)
        w.run_symbol("FPT", "2025-06-01")

        conn = sqlite3.connect(sdb)
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT primary_score FROM expert_signals WHERE symbol='FPT' AND expert_id='V4ATR'"
        ).fetchone()
        conn.close()
        score = row["primary_score"]
        assert score == int(score)
        assert 0 <= score <= 4

    def test_signal_code_in_db(self, test_dbs):
        """Signal code must be a valid V4ATR code."""
        mdb, sdb = test_dbs
        w = ATRExpertWriter(mdb, sdb)
        w.run_symbol("FPT", "2025-06-01")

        conn = sqlite3.connect(sdb)
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT signal_code FROM expert_signals WHERE symbol='FPT' AND expert_id='V4ATR'"
        ).fetchone()
        conn.close()
        valid_codes = {
            "V4ATR_NEUT_SQUEEZE", "V4ATR_BULL_EXPAND", "V4ATR_BEAR_EXPAND",
            "V4ATR_BEAR_EXTREME", "V4ATR_NEUT_CLIMAX", "V4ATR_NEUT_NORMAL",
        }
        assert row["signal_code"] in valid_codes


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
