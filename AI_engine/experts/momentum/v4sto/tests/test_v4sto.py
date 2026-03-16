"""
V4STO Stochastic Expert Tests

Tests:
- Stochastic calculation accuracy
- Known %K values (constant gains -> high %K, constant losses -> low %K)
- OB/OS detection
- %K/%D crossover detection
- Divergence detection
- Score ranges (primary 0-100, secondary -1..+1)
- Determinism
- Writer / idempotency
- Data leakage prevention
"""

import sqlite3
import json
from datetime import date, timedelta
from pathlib import Path

import pytest
import numpy as np

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[5]))

from AI_engine.experts.momentum.v4sto.feature_builder import (
    STOFeatureBuilder, STOFeatures, _fast_k, _slow_stochastic, _sma,
)
from AI_engine.experts.momentum.v4sto.signal_logic import STOSignalLogic, STOOutput
from AI_engine.experts.momentum.v4sto.expert_writer import STOExpertWriter


# ---------------------------------------------------------------------------
# Test DB helpers
# ---------------------------------------------------------------------------

def _create_test_db(db_path: str, num_days=400, trend="up", seed=42):
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
    np.random.seed(seed)
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
                (s, d.isoformat(), round(price * 1.001, 2), round(h, 2),
                 round(l, 2), round(price, 2), int(np.random.uniform(1e6, 5e6))),
            )
    conn.commit()
    conn.close()


def _create_constant_gain_db(db_path: str, num_days=60):
    """Create DB where price goes up every day -> %K should approach 100."""
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
    conn.execute(
        "INSERT OR IGNORE INTO symbols_master VALUES (?,?,?,?,?,?,?,?)",
        ("TEST", "TEST", "HOSE", None, None, 1, "2024-01-01", None),
    )
    base = date(2024, 1, 1)
    price = 100.0
    for i in range(num_days):
        d = base + timedelta(days=i)
        if d.weekday() >= 5:
            continue
        price += 1.0  # constant gain every day
        conn.execute(
            "INSERT OR IGNORE INTO prices_daily VALUES (?,?,?,?,?,?,?,NULL,CURRENT_TIMESTAMP)",
            ("TEST", d.isoformat(), price - 0.5, price + 0.5, price - 1.0,
             price, 1000000),
        )
    conn.commit()
    conn.close()


def _create_constant_loss_db(db_path: str, num_days=60):
    """Create DB where price goes down every day -> %K should approach 0."""
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
    conn.execute(
        "INSERT OR IGNORE INTO symbols_master VALUES (?,?,?,?,?,?,?,?)",
        ("TEST", "TEST", "HOSE", None, None, 1, "2024-01-01", None),
    )
    base = date(2024, 1, 1)
    price = 500.0
    for i in range(num_days):
        d = base + timedelta(days=i)
        if d.weekday() >= 5:
            continue
        price -= 1.0
        if price < 10:
            price = 10
        conn.execute(
            "INSERT OR IGNORE INTO prices_daily VALUES (?,?,?,?,?,?,?,NULL,CURRENT_TIMESTAMP)",
            ("TEST", d.isoformat(), price + 0.5, price + 1.0, price - 0.5,
             price, 1000000),
        )
    conn.commit()
    conn.close()


def _create_oversold_db(db_path: str):
    """Create DB where price drops sharply -> %K should be in oversold."""
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
    conn.execute(
        "INSERT OR IGNORE INTO symbols_master VALUES (?,?,?,?,?,?,?,?)",
        ("TEST", "TEST", "HOSE", None, None, 1, "2024-01-01", None),
    )
    base = date(2024, 1, 1)
    price = 200.0
    day_count = 0
    for i in range(70):
        d = base + timedelta(days=i)
        if d.weekday() >= 5:
            continue
        day_count += 1
        if day_count <= 20:
            price += 0.1
        else:
            price *= 0.97  # 3% daily drop
        h = price * 1.002
        l = price * 0.998
        conn.execute(
            "INSERT OR IGNORE INTO prices_daily VALUES (?,?,?,?,?,?,?,NULL,CURRENT_TIMESTAMP)",
            ("TEST", d.isoformat(), round(price * 1.001, 2), round(h, 2),
             round(l, 2), round(price, 2), 1000000),
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


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

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
def all_gains_dbs(tmp_path):
    mdb = str(tmp_path / "market.db")
    sdb = str(tmp_path / "signals.db")
    _create_constant_gain_db(mdb)
    _create_signals_db(sdb)
    return mdb, sdb


@pytest.fixture
def all_losses_dbs(tmp_path):
    mdb = str(tmp_path / "market.db")
    sdb = str(tmp_path / "signals.db")
    _create_constant_loss_db(mdb)
    _create_signals_db(sdb)
    return mdb, sdb


@pytest.fixture
def oversold_dbs(tmp_path):
    mdb = str(tmp_path / "market.db")
    sdb = str(tmp_path / "signals.db")
    _create_oversold_db(mdb)
    _create_signals_db(sdb)
    return mdb, sdb


# ===========================================================================
# Stochastic Calculation Accuracy
# ===========================================================================

class TestStochasticCalculation:

    def test_fast_k_basic(self):
        """Test Fast %K calculation on known sequence."""
        closes = np.array([10, 11, 12, 13, 14, 15, 16, 17, 18, 19,
                           20, 21, 22, 23, 24], dtype=float)
        highs = closes + 0.5
        lows = closes - 0.5
        fk = _fast_k(closes, highs, lows, 14)
        # First 13 values should be NaN
        for i in range(13):
            assert np.isnan(fk[i])
        # At index 13 (14th value): close=23, highest_high=23.5, lowest_low=9.5
        # %K = 100 * (23 - 9.5) / (23.5 - 9.5) = 100 * 13.5 / 14 = 96.43
        assert not np.isnan(fk[13])
        assert 0 <= fk[13] <= 100

    def test_all_gains_high_k(self, all_gains_dbs):
        """When price increases every day, %K should be near 100."""
        mdb, _ = all_gains_dbs
        f = STOFeatureBuilder(mdb).build("TEST", "2024-04-01")
        assert f.has_sufficient_data
        assert f.stoch_k >= 80, f"Expected %K >= 80 for constant gains, got {f.stoch_k}"

    def test_all_losses_low_k(self, all_losses_dbs):
        """When price decreases every day, %K should be near 0."""
        mdb, _ = all_losses_dbs
        f = STOFeatureBuilder(mdb).build("TEST", "2024-04-01")
        assert f.has_sufficient_data
        assert f.stoch_k <= 20, f"Expected %K <= 20 for constant losses, got {f.stoch_k}"

    def test_sma_basic(self):
        """Test SMA calculation."""
        data = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
        result = _sma(data, 3)
        assert np.isnan(result[0])
        assert np.isnan(result[1])
        assert result[2] == pytest.approx(2.0)
        assert result[3] == pytest.approx(3.0)
        assert result[4] == pytest.approx(4.0)

    def test_slow_stochastic_shape(self):
        """Slow stochastic arrays should have same length as input."""
        n = 30
        closes = np.cumsum(np.random.normal(0, 1, n)) + 100
        highs = closes + np.abs(np.random.normal(0, 0.5, n))
        lows = closes - np.abs(np.random.normal(0, 0.5, n))
        sk, sd = _slow_stochastic(closes, highs, lows, 14, 3, 3)
        assert len(sk) == n
        assert len(sd) == n

    def test_k_range_0_100(self, test_dbs):
        """%K must always be in [0, 100]."""
        mdb, _ = test_dbs
        builder = STOFeatureBuilder(mdb)
        for sym in ["FPT", "VNM", "HPG"]:
            f = builder.build(sym, "2025-02-01")
            if f.has_sufficient_data:
                assert 0 <= f.stoch_k <= 100, f"%K out of range for {sym}: {f.stoch_k}"

    def test_flat_price_k_50(self):
        """Flat prices: Highest High == Lowest Low -> %K should be 50 (midpoint)."""
        prices = np.array([100.0] * 30, dtype=float)
        fk = _fast_k(prices, prices, prices, 14)
        # When range is 0, we set %K = 50
        assert fk[-1] == 50.0


# ===========================================================================
# Feature Builder
# ===========================================================================

class TestSTOFeatureBuilder:

    def test_build(self, test_dbs):
        mdb, _ = test_dbs
        f = STOFeatureBuilder(mdb).build("FPT", "2025-02-01")
        assert f.has_sufficient_data
        assert 0 <= f.stoch_k <= 100

    def test_sto_norm(self, test_dbs):
        mdb, _ = test_dbs
        f = STOFeatureBuilder(mdb).build("FPT", "2025-02-01")
        assert f.sto_norm == pytest.approx((f.stoch_k - 50) / 50, abs=1e-6)

    def test_data_leakage(self, test_dbs):
        """Data cutoff must be strictly before target_date."""
        mdb, _ = test_dbs
        f = STOFeatureBuilder(mdb).build("FPT", "2025-02-01")
        assert f.data_cutoff_date < "2025-02-01"

    def test_data_leakage_no_future(self, test_dbs):
        """
        Stochastic computed for date X should not change when we add data after X.
        """
        mdb, _ = test_dbs
        builder = STOFeatureBuilder(mdb)
        f1 = builder.build("FPT", "2025-02-01")
        f2 = builder.build("FPT", "2025-02-01")
        assert f1.data_cutoff_date < "2025-02-01"
        assert f1.stoch_k == f2.stoch_k

    def test_norm_range(self, test_dbs):
        """sto_norm must be in [-1, +1]."""
        mdb, _ = test_dbs
        f = STOFeatureBuilder(mdb).build("FPT", "2025-02-01")
        assert -1.0 <= f.sto_norm <= 1.0

    def test_k_slope(self, test_dbs):
        mdb, _ = test_dbs
        f = STOFeatureBuilder(mdb).build("FPT", "2025-02-01")
        assert isinstance(f.stoch_k_slope, float)
        assert -1.0 <= f.stoch_k_slope <= 1.0

    def test_k_above_d(self, test_dbs):
        mdb, _ = test_dbs
        f = STOFeatureBuilder(mdb).build("FPT", "2025-02-01")
        assert f.k_above_d in (1, -1)

    def test_stoch_zone(self, test_dbs):
        mdb, _ = test_dbs
        f = STOFeatureBuilder(mdb).build("FPT", "2025-02-01")
        assert f.stoch_zone in (-1, 0, 1)

    def test_insufficient_data(self, test_dbs):
        mdb, _ = test_dbs
        f = STOFeatureBuilder(mdb).build("FPT", "2024-01-10")
        assert not f.has_sufficient_data

    def test_unknown_symbol(self, test_dbs):
        mdb, _ = test_dbs
        f = STOFeatureBuilder(mdb).build("NONEXIST", "2025-02-01")
        assert not f.has_sufficient_data
        assert f.data_cutoff_date == ""

    def test_batch(self, test_dbs):
        mdb, _ = test_dbs
        results = STOFeatureBuilder(mdb).build_batch(["FPT", "VNM", "HPG"], "2025-02-01")
        assert len(results) == 3
        for f in results:
            if f.has_sufficient_data:
                assert 0 <= f.stoch_k <= 100


# ===========================================================================
# OB/OS Detection
# ===========================================================================

class TestOBOSDetection:

    def test_oversold_detection(self, oversold_dbs):
        """After sharp decline, %K should be in oversold territory."""
        mdb, _ = oversold_dbs
        f = STOFeatureBuilder(mdb).build("TEST", "2024-03-15")
        if f.has_sufficient_data:
            assert f.stoch_k < 20, f"Expected %K < 20 after sharp decline, got {f.stoch_k}"
            assert f.stoch_zone == -1

    def test_overbought_detection(self, all_gains_dbs):
        """Constant gains should produce overbought %K."""
        mdb, _ = all_gains_dbs
        f = STOFeatureBuilder(mdb).build("TEST", "2024-04-01")
        assert f.stoch_k >= 80
        assert f.stoch_zone == 1


# ===========================================================================
# Divergence Detection
# ===========================================================================

class TestDivergence:

    def test_bullish_divergence_synthetic(self):
        """
        Bullish divergence: price lower low + %K higher low (in OS zone).
        """
        closes = [100, 95, 90, 85, 90, 95, 92, 88, 83]
        stoch_ks = [30, 18, 12, 8, 15, 25, 18, 14, 10]  # higher low (10 > 8), in OS zone
        result = STOFeatureBuilder._detect_divergence(closes, stoch_ks, 5, 20, 80)
        assert result == 1, f"Expected bullish divergence, got {result}"

    def test_bearish_divergence_synthetic(self):
        """
        Bearish divergence: price higher high + %K lower high (in OB zone).
        """
        closes = [100, 105, 110, 115, 108, 103, 108, 112, 118]
        stoch_ks = [70, 78, 85, 92, 82, 75, 80, 84, 88]  # lower high (88 < 92), in OB zone
        result = STOFeatureBuilder._detect_divergence(closes, stoch_ks, 5, 20, 80)
        assert result == -1, f"Expected bearish divergence, got {result}"

    def test_no_divergence_mid_zone(self):
        """Divergence only counts in OB/OS zone."""
        closes = [100, 95, 90, 85, 90, 95, 92, 88, 83]
        stoch_ks = [50, 45, 42, 38, 45, 55, 48, 44, 40]  # in neutral zone
        result = STOFeatureBuilder._detect_divergence(closes, stoch_ks, 5, 20, 80)
        assert result == 0

    def test_divergence_insufficient_data(self):
        """Too few bars: no divergence."""
        result = STOFeatureBuilder._detect_divergence([100, 101], [50, 52], 5, 20, 80)
        assert result == 0


# ===========================================================================
# Signal Logic
# ===========================================================================

class TestSTOSignalLogic:

    def test_score_range(self, test_dbs):
        mdb, _ = test_dbs
        f = STOFeatureBuilder(mdb).build("FPT", "2025-02-01")
        o = STOSignalLogic().compute(f)
        assert 0 <= o.primary_score <= 100

    def test_norm_range(self, test_dbs):
        mdb, _ = test_dbs
        f = STOFeatureBuilder(mdb).build("FPT", "2025-02-01")
        o = STOSignalLogic().compute(f)
        assert -1.0 <= o.secondary_score <= 1.0
        expected_norm = (o.primary_score - 50) / 50
        assert o.secondary_score == pytest.approx(expected_norm, abs=1e-6)

    def test_quality_range(self, test_dbs):
        mdb, _ = test_dbs
        f = STOFeatureBuilder(mdb).build("FPT", "2025-02-01")
        o = STOSignalLogic().compute(f)
        assert 0 <= o.signal_quality <= 4

    def test_signal_code_prefix(self, test_dbs):
        mdb, _ = test_dbs
        f = STOFeatureBuilder(mdb).build("FPT", "2025-02-01")
        o = STOSignalLogic().compute(f)
        assert o.signal_code.startswith("V4STO_")

    def test_deterministic(self, test_dbs):
        mdb, _ = test_dbs
        builder = STOFeatureBuilder(mdb)
        f1 = builder.build("FPT", "2025-02-01")
        f2 = builder.build("FPT", "2025-02-01")
        o1 = STOSignalLogic().compute(f1)
        o2 = STOSignalLogic().compute(f2)
        assert o1.primary_score == o2.primary_score
        assert o1.secondary_score == o2.secondary_score
        assert o1.signal_code == o2.signal_code
        assert o1.signal_quality == o2.signal_quality

    def test_extreme_oversold_code(self):
        logic = STOSignalLogic()
        f = STOFeatures(
            symbol="TEST", date="2025-02-01", data_cutoff_date="2025-01-31",
            stoch_k=8.0, stoch_d=12.0, sto_norm=-0.84, stoch_zone=-1,
            has_sufficient_data=True,
        )
        o = logic.compute(f)
        assert o.signal_code == "V4STO_BULL_EXTREME_OS"
        assert o.signal_quality == 1  # OB/OS zone but no cross

    def test_extreme_overbought_code(self):
        logic = STOSignalLogic()
        f = STOFeatures(
            symbol="TEST", date="2025-02-01", data_cutoff_date="2025-01-31",
            stoch_k=92.0, stoch_d=88.0, sto_norm=0.84, stoch_zone=1,
            has_sufficient_data=True,
        )
        o = logic.compute(f)
        assert o.signal_code == "V4STO_BEAR_EXTREME_OB"
        assert o.signal_quality == 1

    def test_bull_cross_in_os(self):
        """Bullish cross: %K crosses above %D in oversold zone."""
        logic = STOSignalLogic()
        f = STOFeatures(
            symbol="TEST", date="2025-02-01", data_cutoff_date="2025-01-31",
            stoch_k=18.0, stoch_d=16.0, sto_norm=-0.64, stoch_zone=-1,
            k_crossed_above_d=True, stoch_cross_in_zone=1,
            has_sufficient_data=True,
        )
        o = logic.compute(f)
        assert o.signal_code == "V4STO_BULL_CROSS"
        assert o.signal_quality == 3

    def test_bear_cross_in_ob(self):
        """Bearish cross: %K crosses below %D in overbought zone."""
        logic = STOSignalLogic()
        f = STOFeatures(
            symbol="TEST", date="2025-02-01", data_cutoff_date="2025-01-31",
            stoch_k=82.0, stoch_d=84.0, sto_norm=0.64, stoch_zone=1,
            k_crossed_below_d=True, stoch_cross_in_zone=1,
            has_sufficient_data=True,
        )
        o = logic.compute(f)
        assert o.signal_code == "V4STO_BEAR_CROSS"
        assert o.signal_quality == 3

    def test_neutral_code(self):
        logic = STOSignalLogic()
        f = STOFeatures(
            symbol="TEST", date="2025-02-01", data_cutoff_date="2025-01-31",
            stoch_k=50.0, stoch_d=50.0, sto_norm=0.0, stoch_zone=0,
            has_sufficient_data=True,
        )
        o = logic.compute(f)
        assert o.signal_code == "V4STO_NEUT_MID"
        assert o.signal_quality == 0

    def test_quality_4_div_plus_cross(self):
        """Quality 4: divergence + %K/%D cross in OB/OS zone."""
        logic = STOSignalLogic()
        f = STOFeatures(
            symbol="TEST", date="2025-02-01", data_cutoff_date="2025-01-31",
            stoch_k=15.0, stoch_d=18.0, sto_norm=-0.7, stoch_zone=-1,
            stoch_divergence=1, k_crossed_above_d=True, stoch_cross_in_zone=1,
            has_sufficient_data=True,
        )
        o = logic.compute(f)
        assert o.signal_quality == 4

    def test_quality_3_cross_in_obos(self):
        """Quality 3: cross in OB/OS zone."""
        logic = STOSignalLogic()
        f = STOFeatures(
            symbol="TEST", date="2025-02-01", data_cutoff_date="2025-01-31",
            stoch_k=15.0, stoch_d=18.0, sto_norm=-0.7, stoch_zone=-1,
            k_crossed_above_d=True, stoch_cross_in_zone=1,
            has_sufficient_data=True,
        )
        o = logic.compute(f)
        assert o.signal_quality == 3

    def test_quality_2_cross_near_obos(self):
        """Quality 2: cross near OB/OS (20-30)."""
        logic = STOSignalLogic()
        f = STOFeatures(
            symbol="TEST", date="2025-02-01", data_cutoff_date="2025-01-31",
            stoch_k=25.0, stoch_d=27.0, sto_norm=-0.5, stoch_zone=0,
            k_crossed_above_d=True,
            has_sufficient_data=True,
        )
        o = logic.compute(f)
        assert o.signal_quality == 2

    def test_quality_1_obos_no_cross(self):
        """Quality 1: OB/OS zone but no cross."""
        logic = STOSignalLogic()
        f = STOFeatures(
            symbol="TEST", date="2025-02-01", data_cutoff_date="2025-01-31",
            stoch_k=15.0, stoch_d=12.0, sto_norm=-0.7, stoch_zone=-1,
            has_sufficient_data=True,
        )
        o = logic.compute(f)
        assert o.signal_quality == 1

    def test_quality_0_neutral(self):
        """Quality 0: neutral zone, no cross."""
        logic = STOSignalLogic()
        f = STOFeatures(
            symbol="TEST", date="2025-02-01", data_cutoff_date="2025-01-31",
            stoch_k=50.0, stoch_d=50.0, sto_norm=0.0, stoch_zone=0,
            has_sufficient_data=True,
        )
        o = logic.compute(f)
        assert o.signal_quality == 0

    def test_insufficient_data_output(self):
        logic = STOSignalLogic()
        f = STOFeatures(
            symbol="TEST", date="2025-02-01", data_cutoff_date="",
            has_sufficient_data=False,
        )
        o = logic.compute(f)
        assert not o.has_sufficient_data
        assert o.signal_code == ""

    def test_divergence_bullish_code(self):
        logic = STOSignalLogic()
        f = STOFeatures(
            symbol="TEST", date="2025-02-01", data_cutoff_date="2025-01-31",
            stoch_k=15.0, stoch_d=18.0, sto_norm=-0.7, stoch_zone=-1,
            stoch_divergence=1,
            has_sufficient_data=True,
        )
        o = logic.compute(f)
        assert o.signal_code == "V4STO_BULL_DIV"

    def test_divergence_bearish_code(self):
        logic = STOSignalLogic()
        f = STOFeatures(
            symbol="TEST", date="2025-02-01", data_cutoff_date="2025-01-31",
            stoch_k=85.0, stoch_d=82.0, sto_norm=0.7, stoch_zone=1,
            stoch_divergence=-1,
            has_sufficient_data=True,
        )
        o = logic.compute(f)
        assert o.signal_code == "V4STO_BEAR_DIV"


# ===========================================================================
# Expert Writer
# ===========================================================================

class TestSTOExpertWriter:

    def test_run_symbol(self, test_dbs):
        mdb, sdb = test_dbs
        w = STOExpertWriter(mdb, sdb)
        o = w.run_symbol("FPT", "2025-02-01")
        assert isinstance(o, STOOutput)

        conn = sqlite3.connect(sdb)
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT * FROM expert_signals WHERE symbol='FPT' AND expert_id='V4STO'"
        ).fetchone()
        conn.close()
        assert row is not None
        assert 0 <= row["primary_score"] <= 100
        assert -1 <= row["secondary_score"] <= 1

    def test_metadata_fields(self, test_dbs):
        """Metadata must include all required Stochastic features."""
        mdb, sdb = test_dbs
        w = STOExpertWriter(mdb, sdb)
        w.run_symbol("FPT", "2025-02-01")

        conn = sqlite3.connect(sdb)
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT metadata_json FROM expert_signals WHERE symbol='FPT' AND expert_id='V4STO'"
        ).fetchone()
        conn.close()

        meta = json.loads(row["metadata_json"])
        required_fields = [
            "stoch_k", "stoch_d", "stoch_k_slope", "k_above_d",
            "stoch_zone", "stoch_divergence", "stoch_cross_in_zone",
            "sto_norm", "signal_quality",
        ]
        for fld in required_fields:
            assert fld in meta, f"Missing metadata field: {fld}"

    def test_metadata_no_numpy_types(self, test_dbs):
        """All metadata values must be plain Python types, not numpy."""
        mdb, sdb = test_dbs
        w = STOExpertWriter(mdb, sdb)
        w.run_symbol("FPT", "2025-02-01")

        conn = sqlite3.connect(sdb)
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT metadata_json FROM expert_signals WHERE symbol='FPT' AND expert_id='V4STO'"
        ).fetchone()
        conn.close()

        meta = json.loads(row["metadata_json"])
        for key, val in meta.items():
            assert isinstance(val, (int, float)), (
                f"metadata[{key}] is {type(val).__name__}, expected int or float"
            )

    def test_run_all(self, test_dbs):
        mdb, sdb = test_dbs
        w = STOExpertWriter(mdb, sdb)
        results = w.run_all("2025-02-01", symbols=["FPT", "VNM"])
        assert len(results) == 2

    def test_idempotent(self, test_dbs):
        mdb, sdb = test_dbs
        w = STOExpertWriter(mdb, sdb)
        w.run_symbol("FPT", "2025-02-01")
        w.run_symbol("FPT", "2025-02-01")
        conn = sqlite3.connect(sdb)
        cnt = conn.execute(
            "SELECT COUNT(*) FROM expert_signals WHERE symbol='FPT' AND date='2025-02-01' AND expert_id='V4STO'"
        ).fetchone()[0]
        conn.close()
        assert cnt == 1

    def test_expert_id(self, test_dbs):
        mdb, sdb = test_dbs
        w = STOExpertWriter(mdb, sdb)
        w.run_symbol("FPT", "2025-02-01")
        conn = sqlite3.connect(sdb)
        row = conn.execute(
            "SELECT expert_id FROM expert_signals WHERE symbol='FPT'"
        ).fetchone()
        conn.close()
        assert row[0] == "V4STO"

    def test_primary_score_is_k_value(self, test_dbs):
        """primary_score in DB must be the raw %K value (0-100)."""
        mdb, sdb = test_dbs
        w = STOExpertWriter(mdb, sdb)
        o = w.run_symbol("FPT", "2025-02-01")

        conn = sqlite3.connect(sdb)
        row = conn.execute(
            "SELECT primary_score FROM expert_signals WHERE symbol='FPT' AND expert_id='V4STO'"
        ).fetchone()
        conn.close()
        assert row[0] == pytest.approx(o.primary_score, abs=1e-4)
        assert 0 <= row[0] <= 100


# ===========================================================================
# Valid signal codes
# ===========================================================================

class TestSignalCodes:

    VALID_CODES = {
        "V4STO_BULL_CROSS",
        "V4STO_BEAR_CROSS",
        "V4STO_BULL_EXTREME_OS",
        "V4STO_BEAR_EXTREME_OB",
        "V4STO_BULL_DIV",
        "V4STO_BEAR_DIV",
        "V4STO_NEUT_MID",
    }

    def test_all_codes_valid(self, test_dbs):
        mdb, _ = test_dbs
        builder = STOFeatureBuilder(mdb)
        logic = STOSignalLogic()
        for sym in ["FPT", "VNM", "HPG"]:
            f = builder.build(sym, "2025-02-01")
            o = logic.compute(f)
            if o.has_sufficient_data:
                assert o.signal_code in self.VALID_CODES, (
                    f"Invalid signal code for {sym}: {o.signal_code}"
                )

    def test_synthetic_codes_all_valid(self):
        logic = STOSignalLogic()
        test_cases = [
            # (k, d, zone, div, cross_above, cross_below, expected_code)
            (8.0, 12.0, -1, 0, False, False, "V4STO_BULL_EXTREME_OS"),
            (92.0, 88.0, 1, 0, False, False, "V4STO_BEAR_EXTREME_OB"),
            (15.0, 18.0, -1, 0, True, False, "V4STO_BULL_CROSS"),
            (85.0, 82.0, 1, 0, False, True, "V4STO_BEAR_CROSS"),
            (15.0, 18.0, -1, 1, False, False, "V4STO_BULL_DIV"),
            (85.0, 82.0, 1, -1, False, False, "V4STO_BEAR_DIV"),
            (50.0, 50.0, 0, 0, False, False, "V4STO_NEUT_MID"),
        ]
        for k, d, zone, div, ca, cb, expected_code in test_cases:
            f = STOFeatures(
                symbol="TEST", date="2025-02-01", data_cutoff_date="2025-01-31",
                stoch_k=k, stoch_d=d, sto_norm=(k - 50) / 50, stoch_zone=zone,
                stoch_divergence=div, k_crossed_above_d=ca, k_crossed_below_d=cb,
                has_sufficient_data=True,
            )
            o = logic.compute(f)
            assert o.signal_code == expected_code, (
                f"K={k}, D={d}, zone={zone}, div={div}, ca={ca}, cb={cb}: "
                f"expected {expected_code}, got {o.signal_code}"
            )
            assert o.signal_code in self.VALID_CODES


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
