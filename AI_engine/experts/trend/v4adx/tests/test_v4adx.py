"""
V4ADX Trend Strength Expert Tests
"""

import sqlite3
import json
from datetime import date, timedelta
from pathlib import Path

import pytest
import numpy as np

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[5]))

from AI_engine.experts.trend.v4adx.feature_builder import ADXFeatureBuilder, ADXFeatures
from AI_engine.experts.trend.v4adx.signal_logic import ADXSignalLogic, ADXOutput
from AI_engine.experts.trend.v4adx.expert_writer import ADXExpertWriter


def _create_test_db(db_path: str, num_days=400, trend="up", volatility=0.015):
    """Create synthetic OHLC data with enough history for ADX computation."""
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
        for i in range(num_days):
            d = base + timedelta(days=i)
            if d.weekday() >= 5:
                continue
            drift = 0.001 if trend == "up" else (-0.001 if trend == "down" else 0)
            daily_return = drift + np.random.normal(0, volatility)
            price *= 1 + daily_return
            # Generate realistic OHLC with spread
            h = price * (1 + abs(np.random.normal(0, 0.005)))
            l = price * (1 - abs(np.random.normal(0, 0.005)))
            o = price * (1 + np.random.normal(0, 0.003))
            conn.execute(
                "INSERT OR IGNORE INTO prices_daily VALUES (?,?,?,?,?,?,?,NULL,CURRENT_TIMESTAMP)",
                (s, d.isoformat(), round(o, 2), round(h, 2), round(l, 2),
                 round(price, 2), int(np.random.uniform(1e6, 5e6))),
            )
    conn.commit()
    conn.close()


def _create_strong_trend_db(db_path: str, direction="up"):
    """Create data with a very strong directional trend for testing high ADX."""
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
    conn.execute("INSERT OR IGNORE INTO symbols_master VALUES (?,?,?,?,?,?,?,?)",
                  ("TREND", "TREND", "HOSE", None, None, 1, "2025-01-01", None))

    base = date(2024, 1, 1)
    price = 100.0
    drift = 0.005 if direction == "up" else -0.005
    for i in range(200):
        d = base + timedelta(days=i)
        if d.weekday() >= 5:
            continue
        price *= 1 + drift
        h = price * 1.002
        l = price * 0.998
        conn.execute(
            "INSERT OR IGNORE INTO prices_daily VALUES (?,?,?,?,?,?,?,NULL,CURRENT_TIMESTAMP)",
            ("TREND", d.isoformat(), round(price, 2), round(h, 2), round(l, 2),
             round(price, 2), 1000000),
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


def _create_di_cross_db(db_path: str):
    """Create data with a DI crossover event for testing."""
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
    conn.execute("INSERT OR IGNORE INTO symbols_master VALUES (?,?,?,?,?,?,?,?)",
                  ("CROSS", "CROSS", "HOSE", None, None, 1, "2025-01-01", None))

    base = date(2024, 1, 1)
    price = 100.0
    for i in range(200):
        d = base + timedelta(days=i)
        if d.weekday() >= 5:
            continue
        # First half: downtrend, second half: sharp reversal up
        if i < 140:
            price *= 0.997
        else:
            price *= 1.008
        h = price * 1.003
        l = price * 0.997
        conn.execute(
            "INSERT OR IGNORE INTO prices_daily VALUES (?,?,?,?,?,?,?,NULL,CURRENT_TIMESTAMP)",
            ("CROSS", d.isoformat(), round(price, 2), round(h, 2), round(l, 2),
             round(price, 2), 1000000),
        )
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


@pytest.fixture
def strong_trend_dbs(tmp_path):
    mdb = str(tmp_path / "market_strong.db")
    sdb = str(tmp_path / "signals.db")
    _create_strong_trend_db(mdb, direction="up")
    _create_signals_db(sdb)
    return mdb, sdb


@pytest.fixture
def di_cross_dbs(tmp_path):
    mdb = str(tmp_path / "market_cross.db")
    sdb = str(tmp_path / "signals.db")
    _create_di_cross_db(mdb)
    _create_signals_db(sdb)
    return mdb, sdb


# --- Feature Builder ---

class TestADXFeatureBuilder:

    def test_build_basic(self, test_dbs):
        mdb, _ = test_dbs
        f = ADXFeatureBuilder(mdb).build("FPT", "2024-09-01")
        assert f.has_sufficient_data
        assert f.adx_value > 0
        assert f.plus_di > 0
        assert f.minus_di > 0

    def test_adx_value_range(self, test_dbs):
        mdb, _ = test_dbs
        f = ADXFeatureBuilder(mdb).build("FPT", "2024-09-01")
        assert 0 <= f.adx_value <= 100

    def test_di_values_positive(self, test_dbs):
        mdb, _ = test_dbs
        f = ADXFeatureBuilder(mdb).build("FPT", "2024-09-01")
        assert f.plus_di >= 0
        assert f.minus_di >= 0

    def test_di_diff_equals_calculation(self, test_dbs):
        mdb, _ = test_dbs
        f = ADXFeatureBuilder(mdb).build("FPT", "2024-09-01")
        assert abs(f.di_diff - (f.plus_di - f.minus_di)) < 1e-9

    def test_di_score_equals_di_diff(self, test_dbs):
        mdb, _ = test_dbs
        f = ADXFeatureBuilder(mdb).build("FPT", "2024-09-01")
        assert abs(f.di_score - f.di_diff) < 1e-9

    def test_adx_score_range(self, test_dbs):
        mdb, _ = test_dbs
        f = ADXFeatureBuilder(mdb).build("FPT", "2024-09-01")
        assert 0 <= f.adx_score <= 4

    def test_adx_slope_computed(self, test_dbs):
        mdb, _ = test_dbs
        f = ADXFeatureBuilder(mdb).build("FPT", "2024-09-01")
        assert isinstance(f.adx_slope, float)
        assert isinstance(f.adx_rising, bool)

    def test_data_leakage(self, test_dbs):
        """Data cutoff must be strictly before target_date."""
        mdb, _ = test_dbs
        f = ADXFeatureBuilder(mdb).build("FPT", "2024-09-01")
        assert f.data_cutoff_date < "2024-09-01"

    def test_insufficient_data(self, test_dbs):
        """Too few days should return has_sufficient_data=False."""
        mdb, _ = test_dbs
        f = ADXFeatureBuilder(mdb).build("FPT", "2024-02-01")
        assert not f.has_sufficient_data

    def test_missing_symbol(self, test_dbs):
        mdb, _ = test_dbs
        f = ADXFeatureBuilder(mdb).build("NONEXISTENT", "2024-09-01")
        assert not f.has_sufficient_data
        assert f.data_cutoff_date == ""

    def test_batch(self, test_dbs):
        mdb, _ = test_dbs
        results = ADXFeatureBuilder(mdb).build_batch(["FPT", "VNM", "HPG"], "2024-09-01")
        assert len(results) == 3
        for r in results:
            assert r.has_sufficient_data

    def test_strong_trend_high_adx(self, strong_trend_dbs):
        """A very strong monotonic trend should produce high ADX."""
        mdb, _ = strong_trend_dbs
        f = ADXFeatureBuilder(mdb).build("TREND", "2024-09-01")
        assert f.has_sufficient_data
        # Strong persistent trend should have elevated ADX
        assert f.adx_value > 20


# --- Signal Logic: Score Ranges ---

class TestADXSignalLogicScoring:

    def test_score_0(self):
        """ADX < 15 -> score 0."""
        logic = ADXSignalLogic()
        f = ADXFeatures(
            symbol="T", date="2026-01-15", data_cutoff_date="2026-01-14",
            adx_value=12.0, plus_di=15.0, minus_di=14.0, di_diff=1.0,
            adx_score=0, di_score=1.0, has_sufficient_data=True,
        )
        o = logic.compute(f)
        assert o.primary_score == 0

    def test_score_1(self):
        """15 <= ADX < 20 -> score 1."""
        logic = ADXSignalLogic()
        f = ADXFeatures(
            symbol="T", date="2026-01-15", data_cutoff_date="2026-01-14",
            adx_value=17.5, plus_di=18.0, minus_di=12.0, di_diff=6.0,
            adx_score=1, di_score=6.0, has_sufficient_data=True,
        )
        o = logic.compute(f)
        assert o.primary_score == 1

    def test_score_2(self):
        """20 <= ADX < 25 -> score 2."""
        logic = ADXSignalLogic()
        f = ADXFeatures(
            symbol="T", date="2026-01-15", data_cutoff_date="2026-01-14",
            adx_value=22.0, plus_di=20.0, minus_di=10.0, di_diff=10.0,
            adx_score=2, di_score=10.0, has_sufficient_data=True,
        )
        o = logic.compute(f)
        assert o.primary_score == 2

    def test_score_3(self):
        """25 <= ADX < 40 -> score 3."""
        logic = ADXSignalLogic()
        f = ADXFeatures(
            symbol="T", date="2026-01-15", data_cutoff_date="2026-01-14",
            adx_value=32.0, plus_di=25.0, minus_di=10.0, di_diff=15.0,
            adx_score=3, di_score=15.0, has_sufficient_data=True,
        )
        o = logic.compute(f)
        assert o.primary_score == 3

    def test_score_4(self):
        """ADX >= 40 -> score 4."""
        logic = ADXSignalLogic()
        f = ADXFeatures(
            symbol="T", date="2026-01-15", data_cutoff_date="2026-01-14",
            adx_value=45.0, plus_di=30.0, minus_di=8.0, di_diff=22.0,
            adx_score=4, di_score=22.0, adx_rising=True,
            has_sufficient_data=True,
        )
        o = logic.compute(f)
        assert o.primary_score == 4


# --- Signal Logic: Signal Codes ---

class TestADXSignalCodes:

    def test_bull_trend_strong(self):
        logic = ADXSignalLogic()
        f = ADXFeatures(
            symbol="T", date="2026-01-15", data_cutoff_date="2026-01-14",
            adx_value=30.0, plus_di=25.0, minus_di=10.0, di_diff=15.0,
            adx_score=3, di_score=15.0, adx_rising=True,
            has_sufficient_data=True,
        )
        o = logic.compute(f)
        assert o.signal_code == "V4ADX_BULL_TREND_STRONG"

    def test_bear_trend_strong(self):
        logic = ADXSignalLogic()
        f = ADXFeatures(
            symbol="T", date="2026-01-15", data_cutoff_date="2026-01-14",
            adx_value=30.0, plus_di=10.0, minus_di=25.0, di_diff=-15.0,
            adx_score=3, di_score=-15.0, adx_rising=True,
            has_sufficient_data=True,
        )
        o = logic.compute(f)
        assert o.signal_code == "V4ADX_BEAR_TREND_STRONG"

    def test_bull_di_cross(self):
        logic = ADXSignalLogic()
        f = ADXFeatures(
            symbol="T", date="2026-01-15", data_cutoff_date="2026-01-14",
            adx_value=22.0, plus_di=18.0, minus_di=16.0, di_diff=2.0,
            adx_score=2, di_score=2.0, di_cross_bull=True,
            has_sufficient_data=True,
        )
        o = logic.compute(f)
        assert o.signal_code == "V4ADX_BULL_DI_CROSS"

    def test_bear_di_cross(self):
        logic = ADXSignalLogic()
        f = ADXFeatures(
            symbol="T", date="2026-01-15", data_cutoff_date="2026-01-14",
            adx_value=22.0, plus_di=16.0, minus_di=18.0, di_diff=-2.0,
            adx_score=2, di_score=-2.0, di_cross_bear=True,
            has_sufficient_data=True,
        )
        o = logic.compute(f)
        assert o.signal_code == "V4ADX_BEAR_DI_CROSS"

    def test_neut_trend_weak(self):
        logic = ADXSignalLogic()
        f = ADXFeatures(
            symbol="T", date="2026-01-15", data_cutoff_date="2026-01-14",
            adx_value=12.0, plus_di=14.0, minus_di=13.0, di_diff=1.0,
            adx_score=0, di_score=1.0,
            has_sufficient_data=True,
        )
        o = logic.compute(f)
        assert o.signal_code == "V4ADX_NEUT_TREND_WEAK"

    def test_neut_exhaustion(self):
        """ADX > 40 and falling = exhaustion."""
        logic = ADXSignalLogic()
        f = ADXFeatures(
            symbol="T", date="2026-01-15", data_cutoff_date="2026-01-14",
            adx_value=45.0, plus_di=30.0, minus_di=8.0, di_diff=22.0,
            adx_score=4, di_score=22.0,
            adx_slope=-2.0, adx_rising=False,
            has_sufficient_data=True,
        )
        o = logic.compute(f)
        assert o.signal_code == "V4ADX_NEUT_EXHAUSTION"

    def test_bull_trend_start(self):
        logic = ADXSignalLogic()
        f = ADXFeatures(
            symbol="T", date="2026-01-15", data_cutoff_date="2026-01-14",
            adx_value=18.0, plus_di=20.0, minus_di=12.0, di_diff=8.0,
            adx_score=1, di_score=8.0,
            adx_slope=2.0, adx_rising=True,
            has_sufficient_data=True,
        )
        o = logic.compute(f)
        assert o.signal_code == "V4ADX_BULL_TREND_START"

    def test_bear_trend_start(self):
        logic = ADXSignalLogic()
        f = ADXFeatures(
            symbol="T", date="2026-01-15", data_cutoff_date="2026-01-14",
            adx_value=18.0, plus_di=12.0, minus_di=20.0, di_diff=-8.0,
            adx_score=1, di_score=-8.0,
            adx_slope=2.0, adx_rising=True,
            has_sufficient_data=True,
        )
        o = logic.compute(f)
        assert o.signal_code == "V4ADX_BEAR_TREND_START"


# --- Signal Quality ---

class TestADXSignalQuality:

    def test_quality_range(self, test_dbs):
        mdb, _ = test_dbs
        f = ADXFeatureBuilder(mdb).build("FPT", "2024-09-01")
        o = ADXSignalLogic().compute(f)
        assert 0 <= o.signal_quality <= 4

    def test_quality_4(self):
        """ADX > 30, clear DI separation, ADX rising -> quality 4."""
        logic = ADXSignalLogic()
        f = ADXFeatures(
            symbol="T", date="2026-01-15", data_cutoff_date="2026-01-14",
            adx_value=35.0, plus_di=28.0, minus_di=10.0, di_diff=18.0,
            adx_score=3, di_score=18.0,
            adx_slope=3.0, adx_rising=True,
            has_sufficient_data=True,
        )
        o = logic.compute(f)
        assert o.signal_quality == 4

    def test_quality_0(self):
        """ADX < 15 -> quality 0."""
        logic = ADXSignalLogic()
        f = ADXFeatures(
            symbol="T", date="2026-01-15", data_cutoff_date="2026-01-14",
            adx_value=10.0, plus_di=12.0, minus_di=11.0, di_diff=1.0,
            adx_score=0, di_score=1.0,
            has_sufficient_data=True,
        )
        o = logic.compute(f)
        assert o.signal_quality == 0


# --- DI Crossover ---

class TestDICrossover:

    def test_di_cross_bull_flag(self):
        """When +DI crosses above -DI, di_cross_bull should be True."""
        f = ADXFeatures(
            symbol="T", date="2026-01-15", data_cutoff_date="2026-01-14",
            di_cross_bull=True, has_sufficient_data=True,
            adx_value=22.0, plus_di=18.0, minus_di=16.0, di_diff=2.0,
            adx_score=2, di_score=2.0,
        )
        o = ADXSignalLogic().compute(f)
        assert o.signal_code == "V4ADX_BULL_DI_CROSS"

    def test_di_cross_bear_flag(self):
        f = ADXFeatures(
            symbol="T", date="2026-01-15", data_cutoff_date="2026-01-14",
            di_cross_bear=True, has_sufficient_data=True,
            adx_value=22.0, plus_di=16.0, minus_di=18.0, di_diff=-2.0,
            adx_score=2, di_score=-2.0,
        )
        o = ADXSignalLogic().compute(f)
        assert o.signal_code == "V4ADX_BEAR_DI_CROSS"

    def test_di_cross_priority_over_strong_trend(self):
        """DI cross signals should take priority even when ADX is high."""
        f = ADXFeatures(
            symbol="T", date="2026-01-15", data_cutoff_date="2026-01-14",
            di_cross_bull=True, has_sufficient_data=True,
            adx_value=35.0, plus_di=22.0, minus_di=20.0, di_diff=2.0,
            adx_score=3, di_score=2.0, adx_rising=True,
        )
        o = ADXSignalLogic().compute(f)
        assert o.signal_code == "V4ADX_BULL_DI_CROSS"


# --- Exhaustion ---

class TestExhaustion:

    def test_exhaustion_adx_above_40_falling(self):
        """ADX > 40 and falling should trigger exhaustion."""
        f = ADXFeatures(
            symbol="T", date="2026-01-15", data_cutoff_date="2026-01-14",
            adx_value=42.0, plus_di=30.0, minus_di=8.0, di_diff=22.0,
            adx_score=4, di_score=22.0,
            adx_slope=-1.5, adx_rising=False,
            has_sufficient_data=True,
        )
        o = ADXSignalLogic().compute(f)
        assert o.signal_code == "V4ADX_NEUT_EXHAUSTION"

    def test_no_exhaustion_adx_above_40_rising(self):
        """ADX > 40 but rising should NOT be exhaustion."""
        f = ADXFeatures(
            symbol="T", date="2026-01-15", data_cutoff_date="2026-01-14",
            adx_value=42.0, plus_di=30.0, minus_di=8.0, di_diff=22.0,
            adx_score=4, di_score=22.0,
            adx_slope=1.0, adx_rising=True,
            has_sufficient_data=True,
        )
        o = ADXSignalLogic().compute(f)
        assert o.signal_code != "V4ADX_NEUT_EXHAUSTION"


# --- Determinism ---

class TestDeterminism:

    def test_deterministic_features(self, test_dbs):
        """Same input -> same features."""
        mdb, _ = test_dbs
        builder = ADXFeatureBuilder(mdb)
        f1 = builder.build("FPT", "2024-09-01")
        f2 = builder.build("FPT", "2024-09-01")
        assert f1.adx_value == f2.adx_value
        assert f1.plus_di == f2.plus_di
        assert f1.minus_di == f2.minus_di
        assert f1.adx_score == f2.adx_score

    def test_deterministic_scoring(self, test_dbs):
        mdb, _ = test_dbs
        f = ADXFeatureBuilder(mdb).build("FPT", "2024-09-01")
        o1 = ADXSignalLogic().compute(f)
        o2 = ADXSignalLogic().compute(f)
        assert o1.primary_score == o2.primary_score
        assert o1.secondary_score == o2.secondary_score
        assert o1.signal_code == o2.signal_code


# --- Expert Writer ---

class TestADXExpertWriter:

    def test_run_symbol(self, test_dbs):
        mdb, sdb = test_dbs
        w = ADXExpertWriter(mdb, sdb)
        o = w.run_symbol("FPT", "2024-09-01")
        assert isinstance(o, ADXOutput)

        conn = sqlite3.connect(sdb)
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT * FROM expert_signals WHERE symbol='FPT' AND expert_id='V4ADX'"
        ).fetchone()
        conn.close()
        assert row is not None
        assert 0 <= row["primary_score"] <= 4

    def test_metadata_fields(self, test_dbs):
        """Metadata must include all specified features."""
        mdb, sdb = test_dbs
        w = ADXExpertWriter(mdb, sdb)
        w.run_symbol("FPT", "2024-09-01")

        conn = sqlite3.connect(sdb)
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT metadata_json FROM expert_signals WHERE symbol='FPT' AND expert_id='V4ADX'"
        ).fetchone()
        conn.close()

        meta = json.loads(row["metadata_json"])
        expected_keys = [
            "adx_value", "plus_di", "minus_di", "di_diff",
            "adx_slope", "adx_rising", "di_cross_bull", "di_cross_bear",
            "adx_score", "di_score",
        ]
        for key in expected_keys:
            assert key in meta, f"Missing metadata key: {key}"

    def test_run_all(self, test_dbs):
        mdb, sdb = test_dbs
        w = ADXExpertWriter(mdb, sdb)
        results = w.run_all("2024-09-01", symbols=["FPT", "VNM"])
        assert len(results) == 2

    def test_idempotent(self, test_dbs):
        mdb, sdb = test_dbs
        w = ADXExpertWriter(mdb, sdb)
        w.run_symbol("FPT", "2024-09-01")
        w.run_symbol("FPT", "2024-09-01")
        conn = sqlite3.connect(sdb)
        cnt = conn.execute(
            "SELECT COUNT(*) FROM expert_signals WHERE symbol='FPT' AND date='2024-09-01' AND expert_id='V4ADX'"
        ).fetchone()[0]
        conn.close()
        assert cnt == 1

    def test_insufficient_data_not_written(self, test_dbs):
        """Symbols with insufficient data should not be written to DB."""
        mdb, sdb = test_dbs
        w = ADXExpertWriter(mdb, sdb)
        w.run_symbol("FPT", "2024-02-01")  # too early, not enough history
        conn = sqlite3.connect(sdb)
        cnt = conn.execute(
            "SELECT COUNT(*) FROM expert_signals WHERE symbol='FPT' AND date='2024-02-01' AND expert_id='V4ADX'"
        ).fetchone()[0]
        conn.close()
        assert cnt == 0

    def test_secondary_score_is_di_diff(self, test_dbs):
        """secondary_score in DB should equal di_score (= +DI - -DI)."""
        mdb, sdb = test_dbs
        w = ADXExpertWriter(mdb, sdb)
        o = w.run_symbol("FPT", "2024-09-01")

        conn = sqlite3.connect(sdb)
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT secondary_score FROM expert_signals WHERE symbol='FPT' AND expert_id='V4ADX'"
        ).fetchone()
        conn.close()
        assert abs(row["secondary_score"] - o.secondary_score) < 1e-9


# --- Data Leakage Prevention ---

class TestDataLeakage:

    def test_no_future_data(self, test_dbs):
        """Features for date T must not use any data from T or after."""
        mdb, _ = test_dbs
        target = "2024-09-01"
        f = ADXFeatureBuilder(mdb).build("FPT", target)
        assert f.data_cutoff_date < target

    def test_different_dates_different_results(self, test_dbs):
        """Different target dates should produce different feature values."""
        mdb, _ = test_dbs
        f1 = ADXFeatureBuilder(mdb).build("FPT", "2024-08-15")
        f2 = ADXFeatureBuilder(mdb).build("FPT", "2024-09-01")
        # Should have different cutoff dates and likely different ADX values
        assert f1.data_cutoff_date != f2.data_cutoff_date


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
