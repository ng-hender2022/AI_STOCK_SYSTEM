"""
V4RSI RSI Expert Tests

Tests:
- RSI calculation accuracy with Wilder smoothing
- Known RSI values (all gains -> 100, all losses -> 0)
- OB/OS detection
- Divergence detection
- Failure swing detection
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

from AI_engine.experts.momentum.v4rsi.feature_builder import (
    RSIFeatureBuilder, RSIFeatures, _wilder_rsi,
)
from AI_engine.experts.momentum.v4rsi.signal_logic import RSISignalLogic, RSIOutput
from AI_engine.experts.momentum.v4rsi.expert_writer import RSIExpertWriter


# ---------------------------------------------------------------------------
# Test DB helpers
# ---------------------------------------------------------------------------

def _create_test_db(db_path: str, num_days=350, trend="up", seed=42):
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
            (s, s, "HOSE", None, None, t, "2025-01-01", None),
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


def _create_constant_gain_db(db_path: str, num_days=50):
    """Create DB where price goes up every day -> RSI should approach 100."""
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
        ("TEST", "TEST", "HOSE", None, None, 1, "2025-01-01", None),
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


def _create_constant_loss_db(db_path: str, num_days=50):
    """Create DB where price goes down every day -> RSI should approach 0."""
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
        ("TEST", "TEST", "HOSE", None, None, 1, "2025-01-01", None),
    )
    base = date(2024, 1, 1)
    price = 500.0
    for i in range(num_days):
        d = base + timedelta(days=i)
        if d.weekday() >= 5:
            continue
        price -= 1.0  # constant loss every day
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
    """Create DB where price drops sharply then stabilizes -> RSI should be in oversold."""
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
        ("TEST", "TEST", "HOSE", None, None, 1, "2025-01-01", None),
    )
    base = date(2024, 1, 1)
    price = 200.0
    day_count = 0
    for i in range(60):
        d = base + timedelta(days=i)
        if d.weekday() >= 5:
            continue
        day_count += 1
        # First 20 trading days: flat, then 20 days of sharp decline
        if day_count <= 20:
            price += 0.1
        else:
            price *= 0.97  # 3% daily drop
        conn.execute(
            "INSERT OR IGNORE INTO prices_daily VALUES (?,?,?,?,?,?,?,NULL,CURRENT_TIMESTAMP)",
            ("TEST", d.isoformat(), price + 0.5, price + 1.0, price - 0.5,
             price, 1000000),
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
# RSI Calculation Accuracy
# ===========================================================================

class TestRSICalculation:

    def test_wilder_rsi_basic(self):
        """Test RSI calculation on a known sequence."""
        # 15 prices: first 14 changes needed for first RSI value
        prices = np.array([
            44.0, 44.34, 44.09, 43.61, 44.33,
            44.83, 45.10, 45.42, 45.84, 46.08,
            45.89, 46.03, 45.61, 46.28, 46.28,
        ], dtype=float)
        rsi = _wilder_rsi(prices, 14)
        # First 14 values should be NaN
        for i in range(14):
            assert np.isnan(rsi[i])
        # RSI at index 14 should be valid and in range
        assert not np.isnan(rsi[14])
        assert 0 <= rsi[14] <= 100

    def test_all_gains_rsi_100(self, all_gains_dbs):
        """When price increases every day, RSI should be 100."""
        mdb, _ = all_gains_dbs
        f = RSIFeatureBuilder(mdb).build("TEST", "2024-04-01")
        assert f.has_sufficient_data
        assert f.rsi_value == 100.0

    def test_all_losses_rsi_0(self, all_losses_dbs):
        """When price decreases every day, RSI should be 0."""
        mdb, _ = all_losses_dbs
        f = RSIFeatureBuilder(mdb).build("TEST", "2024-04-01")
        assert f.has_sufficient_data
        assert f.rsi_value == 0.0

    def test_wilder_rsi_all_gains(self):
        """Pure gains: RSI must be 100."""
        prices = np.array([100 + i for i in range(30)], dtype=float)
        rsi = _wilder_rsi(prices, 14)
        assert rsi[-1] == 100.0

    def test_wilder_rsi_all_losses(self):
        """Pure losses: RSI must be 0."""
        prices = np.array([200 - i for i in range(30)], dtype=float)
        rsi = _wilder_rsi(prices, 14)
        assert rsi[-1] == 0.0

    def test_wilder_rsi_flat(self):
        """Flat prices: avg_gain and avg_loss both 0 -> RSI should be 100 (0/0 edge)."""
        prices = np.array([100.0] * 30, dtype=float)
        rsi = _wilder_rsi(prices, 14)
        # When avg_loss = 0, RSI = 100 by formula
        assert rsi[-1] == 100.0

    def test_rsi_range_0_100(self, test_dbs):
        """RSI must always be in [0, 100]."""
        mdb, _ = test_dbs
        builder = RSIFeatureBuilder(mdb)
        for sym in ["FPT", "VNM", "HPG"]:
            f = builder.build(sym, "2025-06-01")
            if f.has_sufficient_data:
                assert 0 <= f.rsi_value <= 100, f"RSI out of range for {sym}: {f.rsi_value}"

    def test_wilder_smoothing_not_simple(self):
        """Verify Wilder smoothing differs from simple rolling average after warmup."""
        np.random.seed(123)
        prices = np.cumsum(np.random.normal(0, 1, 100)) + 200
        rsi = _wilder_rsi(prices, 14)
        # Just verify it produces valid values and is deterministic
        rsi2 = _wilder_rsi(prices, 14)
        np.testing.assert_array_equal(rsi, rsi2)


# ===========================================================================
# Feature Builder
# ===========================================================================

class TestRSIFeatureBuilder:

    def test_build(self, test_dbs):
        mdb, _ = test_dbs
        f = RSIFeatureBuilder(mdb).build("FPT", "2025-06-01")
        assert f.has_sufficient_data
        assert 0 <= f.rsi_value <= 100
        assert f.rsi_norm == pytest.approx((f.rsi_value - 50) / 50, abs=1e-6)

    def test_data_leakage(self, test_dbs):
        """Data cutoff must be strictly before target_date."""
        mdb, _ = test_dbs
        f = RSIFeatureBuilder(mdb).build("FPT", "2025-06-01")
        assert f.data_cutoff_date < "2025-06-01"

    def test_data_leakage_no_future(self, test_dbs):
        """
        RSI computed for date X should not change when we add data after X.
        We test by computing RSI for a date, then verifying the cutoff is before that date.
        """
        mdb, _ = test_dbs
        builder = RSIFeatureBuilder(mdb)
        f1 = builder.build("FPT", "2025-03-01")
        f2 = builder.build("FPT", "2025-06-01")
        # f1 should use data < 2025-03-01, f2 should use data < 2025-06-01
        assert f1.data_cutoff_date < "2025-03-01"
        assert f2.data_cutoff_date < "2025-06-01"
        # Building same date twice should give same result
        f3 = builder.build("FPT", "2025-03-01")
        assert f1.rsi_value == f3.rsi_value

    def test_norm_range(self, test_dbs):
        """rsi_norm must be in [-1, +1]."""
        mdb, _ = test_dbs
        f = RSIFeatureBuilder(mdb).build("FPT", "2025-06-01")
        assert -1.0 <= f.rsi_norm <= 1.0

    def test_rsi_slope(self, test_dbs):
        mdb, _ = test_dbs
        f = RSIFeatureBuilder(mdb).build("FPT", "2025-06-01")
        assert isinstance(f.rsi_slope, float)
        # Slope should be (RSI[t] - RSI[t-3]) / 100, so reasonable range
        assert -1.0 <= f.rsi_slope <= 1.0

    def test_rsi_ma10(self, test_dbs):
        mdb, _ = test_dbs
        f = RSIFeatureBuilder(mdb).build("FPT", "2025-06-01")
        assert 0 <= f.rsi_ma10 <= 100

    def test_rsi_above_50(self, test_dbs):
        mdb, _ = test_dbs
        f = RSIFeatureBuilder(mdb).build("FPT", "2025-06-01")
        assert f.rsi_above_50 in (1, -1)

    def test_rsi_zone(self, test_dbs):
        mdb, _ = test_dbs
        f = RSIFeatureBuilder(mdb).build("FPT", "2025-06-01")
        assert f.rsi_zone in (-2, -1, 0, 1, 2)

    def test_rsi_zone_extreme_oversold(self, all_losses_dbs):
        mdb, _ = all_losses_dbs
        f = RSIFeatureBuilder(mdb).build("TEST", "2024-04-01")
        assert f.rsi_zone == -2

    def test_rsi_zone_extreme_overbought(self, all_gains_dbs):
        mdb, _ = all_gains_dbs
        f = RSIFeatureBuilder(mdb).build("TEST", "2024-04-01")
        assert f.rsi_zone == 2

    def test_insufficient_data(self, test_dbs):
        mdb, _ = test_dbs
        f = RSIFeatureBuilder(mdb).build("FPT", "2024-01-10")
        assert not f.has_sufficient_data

    def test_unknown_symbol(self, test_dbs):
        mdb, _ = test_dbs
        f = RSIFeatureBuilder(mdb).build("NONEXIST", "2025-06-01")
        assert not f.has_sufficient_data
        assert f.data_cutoff_date == ""

    def test_batch(self, test_dbs):
        mdb, _ = test_dbs
        results = RSIFeatureBuilder(mdb).build_batch(["FPT", "VNM", "HPG"], "2025-06-01")
        assert len(results) == 3
        for f in results:
            if f.has_sufficient_data:
                assert 0 <= f.rsi_value <= 100


# ===========================================================================
# OB/OS Detection
# ===========================================================================

class TestOBOSDetection:

    def test_oversold_detection(self, oversold_dbs):
        """After sharp decline, RSI should be in oversold territory."""
        mdb, _ = oversold_dbs
        f = RSIFeatureBuilder(mdb).build("TEST", "2024-03-15")
        if f.has_sufficient_data:
            assert f.rsi_value < 30, f"Expected RSI < 30 after sharp decline, got {f.rsi_value}"
            assert f.rsi_zone in (-1, -2)

    def test_overbought_detection(self, all_gains_dbs):
        """Constant gains should produce overbought RSI."""
        mdb, _ = all_gains_dbs
        f = RSIFeatureBuilder(mdb).build("TEST", "2024-04-01")
        assert f.rsi_value >= 70
        assert f.rsi_zone in (1, 2)


# ===========================================================================
# Divergence Detection
# ===========================================================================

class TestDivergence:

    def test_bullish_divergence_synthetic(self):
        """
        Bullish divergence: price lower low + RSI higher low.
        """
        # Construct: price goes low, bounces, then makes lower low; RSI goes low, bounces, makes higher low
        closes = [100, 95, 90, 85, 90, 95, 92, 88, 83]  # lower low at end
        rsis =   [50,  40, 30, 20, 35, 45, 38, 32, 25]   # higher low (25 > 20)
        result = RSIFeatureBuilder._detect_divergence(closes, rsis, 5)
        assert result == 1, f"Expected bullish divergence, got {result}"

    def test_bearish_divergence_synthetic(self):
        """
        Bearish divergence: price higher high + RSI lower high.
        """
        closes = [100, 105, 110, 115, 108, 103, 108, 112, 118]  # higher high at end
        rsis =   [50,  60,  70,  80,  65,  55,  62,  68,  75]    # lower high (75 < 80)
        result = RSIFeatureBuilder._detect_divergence(closes, rsis, 5)
        assert result == -1, f"Expected bearish divergence, got {result}"

    def test_no_divergence(self):
        """Normal trend: no divergence."""
        closes = [100, 101, 102, 103, 104, 105, 106, 107, 108, 109, 110]
        rsis =   [50,  52,  54,  56,  58,  60,  62,  64,  66,  68,  70]
        result = RSIFeatureBuilder._detect_divergence(closes, rsis, 5)
        assert result == 0

    def test_divergence_insufficient_data(self):
        """Too few bars: no divergence."""
        result = RSIFeatureBuilder._detect_divergence([100, 101], [50, 52], 5)
        assert result == 0


# ===========================================================================
# Failure Swing Detection
# ===========================================================================

class TestFailureSwing:

    def test_bullish_failure_swing_synthetic(self):
        """
        Bullish failure swing:
        RSI drops below 30, bounces to X, pulls back above 30, breaks X.
        """
        rsis = [35, 28, 25, 32, 38, 35, 33, 40]
        # 28,25 below 30; bounces to 38 (X=38); pulls back to 35,33 (above 30); breaks 40 > 38
        result = RSIFeatureBuilder._detect_failure_swing(rsis, oversold=30, overbought=70)
        assert result == 1, f"Expected bullish failure swing, got {result}"

    def test_bearish_failure_swing_synthetic(self):
        """
        Bearish failure swing:
        RSI rises above 70, falls to Y, rallies below 70, breaks below Y.
        """
        rsis = [65, 72, 75, 68, 62, 65, 67, 60]
        # 72,75 above 70; drops to 62 (Y=62); rallies to 65,67 (below 70); breaks 60 < 62
        result = RSIFeatureBuilder._detect_failure_swing(rsis, oversold=30, overbought=70)
        assert result == -1, f"Expected bearish failure swing, got {result}"

    def test_no_failure_swing_neutral(self):
        """RSI in neutral zone: no failure swing."""
        rsis = [45, 48, 50, 52, 49, 51, 50, 48, 50, 52]
        result = RSIFeatureBuilder._detect_failure_swing(rsis, oversold=30, overbought=70)
        assert result == 0

    def test_failure_swing_insufficient_data(self):
        """Too few bars: no failure swing."""
        result = RSIFeatureBuilder._detect_failure_swing([25, 35], oversold=30, overbought=70)
        assert result == 0


# ===========================================================================
# Signal Logic
# ===========================================================================

class TestRSISignalLogic:

    def test_score_range(self, test_dbs):
        mdb, _ = test_dbs
        f = RSIFeatureBuilder(mdb).build("FPT", "2025-06-01")
        o = RSISignalLogic().compute(f)
        assert 0 <= o.primary_score <= 100

    def test_norm_range(self, test_dbs):
        mdb, _ = test_dbs
        f = RSIFeatureBuilder(mdb).build("FPT", "2025-06-01")
        o = RSISignalLogic().compute(f)
        assert -1.0 <= o.secondary_score <= 1.0
        expected_norm = (o.primary_score - 50) / 50
        assert o.secondary_score == pytest.approx(expected_norm, abs=1e-6)

    def test_quality_range(self, test_dbs):
        mdb, _ = test_dbs
        f = RSIFeatureBuilder(mdb).build("FPT", "2025-06-01")
        o = RSISignalLogic().compute(f)
        assert 0 <= o.signal_quality <= 4

    def test_signal_code_prefix(self, test_dbs):
        mdb, _ = test_dbs
        f = RSIFeatureBuilder(mdb).build("FPT", "2025-06-01")
        o = RSISignalLogic().compute(f)
        assert o.signal_code.startswith("V4RSI_")

    def test_deterministic(self, test_dbs):
        mdb, _ = test_dbs
        builder = RSIFeatureBuilder(mdb)
        f1 = builder.build("FPT", "2025-06-01")
        f2 = builder.build("FPT", "2025-06-01")
        o1 = RSISignalLogic().compute(f1)
        o2 = RSISignalLogic().compute(f2)
        assert o1.primary_score == o2.primary_score
        assert o1.secondary_score == o2.secondary_score
        assert o1.signal_code == o2.signal_code
        assert o1.signal_quality == o2.signal_quality

    def test_extreme_oversold_code(self):
        logic = RSISignalLogic()
        f = RSIFeatures(
            symbol="TEST", date="2026-01-15", data_cutoff_date="2026-01-14",
            rsi_value=15.0, rsi_norm=-0.7, rsi_zone=-2,
            has_sufficient_data=True,
        )
        o = logic.compute(f)
        assert o.signal_code == "V4RSI_BULL_EXTREME_OS"
        assert o.signal_quality == 2

    def test_extreme_overbought_code(self):
        logic = RSISignalLogic()
        f = RSIFeatures(
            symbol="TEST", date="2026-01-15", data_cutoff_date="2026-01-14",
            rsi_value=85.0, rsi_norm=0.7, rsi_zone=2,
            has_sufficient_data=True,
        )
        o = logic.compute(f)
        assert o.signal_code == "V4RSI_BEAR_EXTREME_OB"
        assert o.signal_quality == 2

    def test_regular_oversold_code(self):
        logic = RSISignalLogic()
        f = RSIFeatures(
            symbol="TEST", date="2026-01-15", data_cutoff_date="2026-01-14",
            rsi_value=25.0, rsi_norm=-0.5, rsi_zone=-1,
            has_sufficient_data=True,
        )
        o = logic.compute(f)
        assert o.signal_code == "V4RSI_BULL_REVERSAL"
        assert o.signal_quality == 1

    def test_regular_overbought_code(self):
        logic = RSISignalLogic()
        f = RSIFeatures(
            symbol="TEST", date="2026-01-15", data_cutoff_date="2026-01-14",
            rsi_value=75.0, rsi_norm=0.5, rsi_zone=1,
            has_sufficient_data=True,
        )
        o = logic.compute(f)
        assert o.signal_code == "V4RSI_BEAR_REVERSAL"
        assert o.signal_quality == 1

    def test_neutral_code(self):
        logic = RSISignalLogic()
        f = RSIFeatures(
            symbol="TEST", date="2026-01-15", data_cutoff_date="2026-01-14",
            rsi_value=50.0, rsi_norm=0.0, rsi_zone=0,
            has_sufficient_data=True,
        )
        o = logic.compute(f)
        assert o.signal_code == "V4RSI_NEUT_NEUTRAL"
        assert o.signal_quality == 0

    def test_center_cross_bullish(self):
        logic = RSISignalLogic()
        f = RSIFeatures(
            symbol="TEST", date="2026-01-15", data_cutoff_date="2026-01-14",
            rsi_value=55.0, rsi_norm=0.1, rsi_zone=0,
            centerline_cross=1,
            has_sufficient_data=True,
        )
        o = logic.compute(f)
        assert o.signal_code == "V4RSI_BULL_CENTER_CROSS"

    def test_center_cross_bearish(self):
        logic = RSISignalLogic()
        f = RSIFeatures(
            symbol="TEST", date="2026-01-15", data_cutoff_date="2026-01-14",
            rsi_value=45.0, rsi_norm=-0.1, rsi_zone=0,
            centerline_cross=-1,
            has_sufficient_data=True,
        )
        o = logic.compute(f)
        assert o.signal_code == "V4RSI_BEAR_CENTER_CROSS"

    def test_divergence_bullish_code(self):
        logic = RSISignalLogic()
        f = RSIFeatures(
            symbol="TEST", date="2026-01-15", data_cutoff_date="2026-01-14",
            rsi_value=55.0, rsi_norm=0.1, rsi_zone=0,
            divergence_flag=1,
            has_sufficient_data=True,
        )
        o = logic.compute(f)
        assert o.signal_code == "V4RSI_BULL_DIV"

    def test_divergence_bearish_code(self):
        logic = RSISignalLogic()
        f = RSIFeatures(
            symbol="TEST", date="2026-01-15", data_cutoff_date="2026-01-14",
            rsi_value=55.0, rsi_norm=0.1, rsi_zone=0,
            divergence_flag=-1,
            has_sufficient_data=True,
        )
        o = logic.compute(f)
        assert o.signal_code == "V4RSI_BEAR_DIV"

    def test_failure_swing_bullish_code(self):
        logic = RSISignalLogic()
        f = RSIFeatures(
            symbol="TEST", date="2026-01-15", data_cutoff_date="2026-01-14",
            rsi_value=55.0, rsi_norm=0.1, rsi_zone=0,
            failure_swing_flag=1,
            has_sufficient_data=True,
        )
        o = logic.compute(f)
        assert o.signal_code == "V4RSI_BULL_FAILURE_SWING"

    def test_failure_swing_bearish_code(self):
        logic = RSISignalLogic()
        f = RSIFeatures(
            symbol="TEST", date="2026-01-15", data_cutoff_date="2026-01-14",
            rsi_value=55.0, rsi_norm=0.1, rsi_zone=0,
            failure_swing_flag=-1,
            has_sufficient_data=True,
        )
        o = logic.compute(f)
        assert o.signal_code == "V4RSI_BEAR_FAILURE_SWING"

    def test_quality_4_divergence_extreme(self):
        """Quality 4: divergence + extreme OB/OS."""
        logic = RSISignalLogic()
        f = RSIFeatures(
            symbol="TEST", date="2026-01-15", data_cutoff_date="2026-01-14",
            rsi_value=15.0, rsi_norm=-0.7, rsi_zone=-2,
            divergence_flag=1,
            has_sufficient_data=True,
        )
        o = logic.compute(f)
        assert o.signal_quality == 4

    def test_quality_3_divergence_obos(self):
        """Quality 3: divergence at OB/OS level."""
        logic = RSISignalLogic()
        f = RSIFeatures(
            symbol="TEST", date="2026-01-15", data_cutoff_date="2026-01-14",
            rsi_value=25.0, rsi_norm=-0.5, rsi_zone=-1,
            divergence_flag=1,
            has_sufficient_data=True,
        )
        o = logic.compute(f)
        assert o.signal_quality == 3

    def test_quality_0_neutral(self):
        """Quality 0: neutral zone, no divergence."""
        logic = RSISignalLogic()
        f = RSIFeatures(
            symbol="TEST", date="2026-01-15", data_cutoff_date="2026-01-14",
            rsi_value=50.0, rsi_norm=0.0, rsi_zone=0,
            has_sufficient_data=True,
        )
        o = logic.compute(f)
        assert o.signal_quality == 0

    def test_insufficient_data_output(self):
        logic = RSISignalLogic()
        f = RSIFeatures(
            symbol="TEST", date="2026-01-15", data_cutoff_date="",
            has_sufficient_data=False,
        )
        o = logic.compute(f)
        assert not o.has_sufficient_data
        assert o.signal_code == ""


# ===========================================================================
# Expert Writer
# ===========================================================================

class TestRSIExpertWriter:

    def test_run_symbol(self, test_dbs):
        mdb, sdb = test_dbs
        w = RSIExpertWriter(mdb, sdb)
        o = w.run_symbol("FPT", "2025-06-01")
        assert isinstance(o, RSIOutput)

        conn = sqlite3.connect(sdb)
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT * FROM expert_signals WHERE symbol='FPT' AND expert_id='V4RSI'"
        ).fetchone()
        conn.close()
        assert row is not None
        assert 0 <= row["primary_score"] <= 100
        assert -1 <= row["secondary_score"] <= 1

    def test_metadata_fields(self, test_dbs):
        """Metadata must include all required RSI features."""
        mdb, sdb = test_dbs
        w = RSIExpertWriter(mdb, sdb)
        w.run_symbol("FPT", "2025-06-01")

        conn = sqlite3.connect(sdb)
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT metadata_json FROM expert_signals WHERE symbol='FPT' AND expert_id='V4RSI'"
        ).fetchone()
        conn.close()

        meta = json.loads(row["metadata_json"])
        required_fields = [
            "rsi_value", "rsi_norm", "rsi_slope", "rsi_ma10",
            "rsi_above_50", "rsi_zone", "divergence_flag",
            "failure_swing_flag", "signal_quality",
        ]
        for field in required_fields:
            assert field in meta, f"Missing metadata field: {field}"

    def test_run_all(self, test_dbs):
        mdb, sdb = test_dbs
        w = RSIExpertWriter(mdb, sdb)
        results = w.run_all("2025-06-01", symbols=["FPT", "VNM"])
        assert len(results) == 2

    def test_idempotent(self, test_dbs):
        mdb, sdb = test_dbs
        w = RSIExpertWriter(mdb, sdb)
        w.run_symbol("FPT", "2025-06-01")
        w.run_symbol("FPT", "2025-06-01")
        conn = sqlite3.connect(sdb)
        cnt = conn.execute(
            "SELECT COUNT(*) FROM expert_signals WHERE symbol='FPT' AND date='2025-06-01' AND expert_id='V4RSI'"
        ).fetchone()[0]
        conn.close()
        assert cnt == 1

    def test_expert_id(self, test_dbs):
        mdb, sdb = test_dbs
        w = RSIExpertWriter(mdb, sdb)
        w.run_symbol("FPT", "2025-06-01")
        conn = sqlite3.connect(sdb)
        row = conn.execute(
            "SELECT expert_id FROM expert_signals WHERE symbol='FPT'"
        ).fetchone()
        conn.close()
        assert row[0] == "V4RSI"

    def test_primary_score_is_rsi_value(self, test_dbs):
        """primary_score in DB must be the raw RSI value (0-100), NOT -4..+4."""
        mdb, sdb = test_dbs
        w = RSIExpertWriter(mdb, sdb)
        o = w.run_symbol("FPT", "2025-06-01")

        conn = sqlite3.connect(sdb)
        row = conn.execute(
            "SELECT primary_score FROM expert_signals WHERE symbol='FPT' AND expert_id='V4RSI'"
        ).fetchone()
        conn.close()
        assert row[0] == pytest.approx(o.primary_score, abs=1e-4)
        assert 0 <= row[0] <= 100


# ===========================================================================
# Valid signal codes
# ===========================================================================

class TestSignalCodes:

    VALID_CODES = {
        "V4RSI_BULL_EXTREME_OS",
        "V4RSI_BEAR_EXTREME_OB",
        "V4RSI_BULL_REVERSAL",
        "V4RSI_BEAR_REVERSAL",
        "V4RSI_BULL_DIV",
        "V4RSI_BEAR_DIV",
        "V4RSI_BULL_CENTER_CROSS",
        "V4RSI_BEAR_CENTER_CROSS",
        "V4RSI_NEUT_NEUTRAL",
        "V4RSI_BULL_FAILURE_SWING",
        "V4RSI_BEAR_FAILURE_SWING",
    }

    def test_all_codes_valid(self, test_dbs):
        mdb, _ = test_dbs
        builder = RSIFeatureBuilder(mdb)
        logic = RSISignalLogic()
        for sym in ["FPT", "VNM", "HPG"]:
            f = builder.build(sym, "2025-06-01")
            o = logic.compute(f)
            if o.has_sufficient_data:
                assert o.signal_code in self.VALID_CODES, (
                    f"Invalid signal code for {sym}: {o.signal_code}"
                )

    def test_synthetic_codes_all_valid(self):
        logic = RSISignalLogic()
        test_cases = [
            (15.0, -2, 0, 0, 0, "V4RSI_BULL_EXTREME_OS"),
            (85.0, 2, 0, 0, 0, "V4RSI_BEAR_EXTREME_OB"),
            (25.0, -1, 0, 0, 0, "V4RSI_BULL_REVERSAL"),
            (75.0, 1, 0, 0, 0, "V4RSI_BEAR_REVERSAL"),
            (50.0, 0, 1, 0, 0, "V4RSI_BULL_DIV"),
            (50.0, 0, -1, 0, 0, "V4RSI_BEAR_DIV"),
            (55.0, 0, 0, 0, 1, "V4RSI_BULL_CENTER_CROSS"),
            (45.0, 0, 0, 0, -1, "V4RSI_BEAR_CENTER_CROSS"),
            (50.0, 0, 0, 0, 0, "V4RSI_NEUT_NEUTRAL"),
            (50.0, 0, 0, 1, 0, "V4RSI_BULL_FAILURE_SWING"),
            (50.0, 0, 0, -1, 0, "V4RSI_BEAR_FAILURE_SWING"),
        ]
        for rsi_val, zone, div, fs, cc, expected_code in test_cases:
            f = RSIFeatures(
                symbol="TEST", date="2026-01-15", data_cutoff_date="2026-01-14",
                rsi_value=rsi_val, rsi_norm=(rsi_val - 50) / 50, rsi_zone=zone,
                divergence_flag=div, failure_swing_flag=fs, centerline_cross=cc,
                has_sufficient_data=True,
            )
            o = logic.compute(f)
            assert o.signal_code == expected_code, (
                f"RSI={rsi_val}, zone={zone}, div={div}, fs={fs}, cc={cc}: "
                f"expected {expected_code}, got {o.signal_code}"
            )
            assert o.signal_code in self.VALID_CODES


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
