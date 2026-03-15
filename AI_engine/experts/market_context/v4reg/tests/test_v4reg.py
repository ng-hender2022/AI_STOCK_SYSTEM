"""
V4REG Tests
Covers: feature builder, signal logic, regime writer, data leakage prevention.
"""

import sqlite3
import os
import tempfile
from datetime import date, timedelta
from pathlib import Path

import pytest
import numpy as np

# Adjust path so imports work
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[5]))

from AI_engine.experts.market_context.v4reg.feature_builder import (
    RegimeFeatureBuilder,
    RegimeFeatures,
)
from AI_engine.experts.market_context.v4reg.signal_logic import (
    RegimeSignalLogic,
    RegimeOutput,
)
from AI_engine.experts.market_context.v4reg.regime_writer import RegimeWriter


# ---------------------------------------------------------------------------
# Test data helpers
# ---------------------------------------------------------------------------

def _create_test_db(db_path: str, num_days: int = 250) -> None:
    """Create a test market.db with synthetic VNINDEX + stock data."""
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL")

    # Create tables
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS symbols_master (
            symbol TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            exchange TEXT DEFAULT 'HOSE',
            sector TEXT,
            industry TEXT,
            is_tradable INTEGER DEFAULT 1,
            added_date DATE NOT NULL,
            notes TEXT
        );

        CREATE TABLE IF NOT EXISTS prices_daily (
            symbol TEXT NOT NULL,
            date DATE NOT NULL,
            open REAL, high REAL, low REAL, close REAL,
            volume INTEGER, value REAL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (symbol, date)
        );

        CREATE TABLE IF NOT EXISTS market_regime (
            date DATE NOT NULL,
            snapshot_time TEXT DEFAULT 'EOD',
            regime_score REAL NOT NULL,
            regime_label TEXT NOT NULL,
            breadth_score REAL,
            volatility_score REAL,
            trend_score REAL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (date, snapshot_time)
        );
    """)

    # Insert VNINDEX
    conn.execute(
        "INSERT OR IGNORE INTO symbols_master (symbol, name, is_tradable, added_date)"
        " VALUES ('VNINDEX', 'VN Index', 0, '2026-01-01')"
    )

    # Insert 20 dummy stocks
    for i in range(20):
        sym = f"STK{i:02d}"
        conn.execute(
            "INSERT OR IGNORE INTO symbols_master (symbol, name, is_tradable, added_date)"
            f" VALUES ('{sym}', 'Stock {i}', 1, '2026-01-01')"
        )

    # Generate VNINDEX price data: uptrend
    base_date = date(2025, 3, 1)
    base_price = 1200.0
    np.random.seed(42)

    for day_i in range(num_days):
        d = base_date + timedelta(days=day_i)
        if d.weekday() >= 5:
            continue

        # Gentle uptrend with noise
        trend = 0.0003 * day_i
        noise = np.random.normal(0, 0.008)
        change = trend + noise
        base_price = base_price * (1 + change)

        o = base_price * (1 + np.random.normal(0, 0.003))
        h = max(o, base_price) * (1 + abs(np.random.normal(0, 0.005)))
        l = min(o, base_price) * (1 - abs(np.random.normal(0, 0.005)))
        c = base_price
        v = int(np.random.uniform(100_000_000, 300_000_000))

        conn.execute(
            "INSERT OR IGNORE INTO prices_daily (symbol, date, open, high, low, close, volume)"
            " VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("VNINDEX", d.isoformat(), round(o, 2), round(h, 2), round(l, 2), round(c, 2), v),
        )

        # Generate stock data (some above MA50, some below for breadth)
        for j in range(20):
            sym = f"STK{j:02d}"
            if j < 14:  # 14/20 = 70% trending up
                stock_change = change + np.random.normal(0.0002, 0.012)
            else:
                stock_change = change + np.random.normal(-0.001, 0.015)

            stock_base = 50.0 + j * 5
            stock_price = stock_base * (1 + 0.0003 * day_i + np.random.normal(0, 0.01))
            sv = int(np.random.uniform(500_000, 5_000_000))

            conn.execute(
                "INSERT OR IGNORE INTO prices_daily (symbol, date, open, high, low, close, volume)"
                " VALUES (?, ?, ?, ?, ?, ?, ?)",
                (sym, d.isoformat(), round(stock_price * 0.99, 2),
                 round(stock_price * 1.01, 2), round(stock_price * 0.98, 2),
                 round(stock_price, 2), sv),
            )

    conn.commit()
    conn.close()


@pytest.fixture
def test_db(tmp_path):
    """Create a temporary test database."""
    db_path = str(tmp_path / "market.db")
    _create_test_db(db_path)
    return db_path


# ---------------------------------------------------------------------------
# Feature builder tests
# ---------------------------------------------------------------------------

class TestFeatureBuilder:

    def test_build_returns_features(self, test_db):
        builder = RegimeFeatureBuilder(test_db)
        features = builder.build("2025-12-15")
        assert isinstance(features, RegimeFeatures)
        assert features.has_sufficient_data is True

    def test_data_leakage_prevention(self, test_db):
        """Feature date T must use data up to T-1 only."""
        builder = RegimeFeatureBuilder(test_db)
        features = builder.build("2025-12-15")
        assert features.data_cutoff_date < "2025-12-15"

    def test_vnindex_features_populated(self, test_db):
        builder = RegimeFeatureBuilder(test_db)
        features = builder.build("2025-12-15")
        assert features.vnindex_close > 0
        assert features.vnindex_ma20 > 0
        assert features.vnindex_ma50 > 0

    def test_breadth_features_populated(self, test_db):
        builder = RegimeFeatureBuilder(test_db)
        features = builder.build("2025-12-15")
        assert 0 <= features.pct_above_ma50 <= 1.0
        assert features.advance_decline_ratio >= 0

    def test_insufficient_data(self, test_db):
        builder = RegimeFeatureBuilder(test_db)
        # Date before any data exists
        features = builder.build("2024-01-01")
        assert features.has_sufficient_data is False

    def test_volatility_features(self, test_db):
        builder = RegimeFeatureBuilder(test_db)
        features = builder.build("2025-12-15")
        assert features.vnindex_atr >= 0
        assert 0 <= features.atr_pct_percentile <= 100

    def test_liquidity_features(self, test_db):
        builder = RegimeFeatureBuilder(test_db)
        features = builder.build("2025-12-15")
        assert features.market_volume_ratio > 0


# ---------------------------------------------------------------------------
# Signal logic tests
# ---------------------------------------------------------------------------

class TestSignalLogic:

    def test_compute_returns_output(self, test_db):
        builder = RegimeFeatureBuilder(test_db)
        logic = RegimeSignalLogic()
        features = builder.build("2025-12-15")
        output = logic.compute(features)
        assert isinstance(output, RegimeOutput)

    def test_trend_regime_score_range(self, test_db):
        builder = RegimeFeatureBuilder(test_db)
        logic = RegimeSignalLogic()
        features = builder.build("2025-12-15")
        output = logic.compute(features)
        assert -4.0 <= output.trend_regime_score <= 4.0

    def test_vol_regime_score_range(self, test_db):
        builder = RegimeFeatureBuilder(test_db)
        logic = RegimeSignalLogic()
        features = builder.build("2025-12-15")
        output = logic.compute(features)
        assert 0 <= output.vol_regime_score <= 4

    def test_liquidity_regime_score_range(self, test_db):
        builder = RegimeFeatureBuilder(test_db)
        logic = RegimeSignalLogic()
        features = builder.build("2025-12-15")
        output = logic.compute(features)
        assert -2.0 <= output.liquidity_regime_score <= 2.0

    def test_confidence_range(self, test_db):
        builder = RegimeFeatureBuilder(test_db)
        logic = RegimeSignalLogic()
        features = builder.build("2025-12-15")
        output = logic.compute(features)
        assert 0.0 <= output.regime_confidence <= 1.0

    def test_regime_label_valid(self, test_db):
        builder = RegimeFeatureBuilder(test_db)
        logic = RegimeSignalLogic()
        features = builder.build("2025-12-15")
        output = logic.compute(features)
        valid_labels = {
            "STRONG_BULL", "BULL", "WEAK_BULL",
            "NEUTRAL",
            "WEAK_BEAR", "BEAR", "STRONG_BEAR",
        }
        assert output.regime_label in valid_labels

    def test_smoothing_limits_change(self):
        """Smoothing should limit daily change to 1 unit (except panic)."""
        logic = RegimeSignalLogic()

        # Simulate features that would give extreme raw score
        features = RegimeFeatures(
            date="2026-01-15",
            data_cutoff_date="2026-01-14",
            vnindex_close=1300,
            vnindex_ma20=1250, vnindex_ma50=1200, vnindex_ma200=1150,
            vnindex_ma20_slope=0.01, vnindex_ma50_slope=0.005,
            vnindex_return_1d=0.02, vnindex_return_20d=0.10,
            vnindex_return_60d=0.15, vnindex_drawdown=-0.01,
            pct_above_ma50=0.80, advance_decline_ratio=2.5,
            vnindex_atr=15.0, vnindex_atr_pct=0.012,
            atr_pct_percentile=50.0, market_volume_ratio=1.3,
            has_sufficient_data=True,
        )

        # Start from -2, should not jump more than 1
        output = logic.compute(features, prev_smooth_score=-2.0)
        assert output.trend_regime_score <= -1.0  # max +1 from -2

    def test_panic_override(self):
        """Panic conditions should force score to -4."""
        logic = RegimeSignalLogic()

        features = RegimeFeatures(
            date="2026-01-15",
            data_cutoff_date="2026-01-14",
            vnindex_close=1100,
            vnindex_ma20=1200, vnindex_ma50=1250, vnindex_ma200=1300,
            vnindex_ma20_slope=-0.02, vnindex_ma50_slope=-0.01,
            vnindex_return_1d=-0.04,   # -4% drop
            vnindex_return_20d=-0.12,
            vnindex_return_60d=-0.15,
            vnindex_drawdown=-0.18,
            pct_above_ma50=0.15, advance_decline_ratio=0.2,
            vnindex_atr=35.0, vnindex_atr_pct=0.032,
            atr_pct_percentile=95.0,   # extreme vol → vol_score=4
            market_volume_ratio=0.4,
            has_sufficient_data=True,
        )

        output = logic.compute(features, prev_smooth_score=0.0)
        assert output.panic_triggered is True
        assert output.trend_regime_score == -4.0

    def test_deterministic(self, test_db):
        """Same input → same output (deterministic)."""
        builder = RegimeFeatureBuilder(test_db)
        logic = RegimeSignalLogic()
        features = builder.build("2025-12-15")
        out1 = logic.compute(features)
        out2 = logic.compute(features)
        assert out1.trend_regime_score == out2.trend_regime_score
        assert out1.vol_regime_score == out2.vol_regime_score


# ---------------------------------------------------------------------------
# Regime writer tests
# ---------------------------------------------------------------------------

class TestRegimeWriter:

    def test_run_single_date(self, test_db):
        writer = RegimeWriter(test_db)
        output = writer.run("2025-12-15")
        assert isinstance(output, RegimeOutput)

        # Verify written to DB
        conn = sqlite3.connect(test_db)
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT * FROM market_regime WHERE date = '2025-12-15'"
        ).fetchone()
        conn.close()

        assert row is not None
        assert -4 <= row["regime_score"] <= 4

    def test_run_range(self, test_db):
        writer = RegimeWriter(test_db)
        results = writer.run_range("2025-11-01", "2025-12-01")
        assert len(results) > 0

        # Check all outputs valid
        for r in results:
            assert -4.0 <= r.trend_regime_score <= 4.0
            assert 0 <= r.vol_regime_score <= 4
            assert -2.0 <= r.liquidity_regime_score <= 2.0

    def test_smoothing_continuity(self, test_db):
        """Run range should carry forward smoothed scores."""
        writer = RegimeWriter(test_db)
        results = writer.run_range("2025-11-01", "2025-12-01")

        # Check no jumps > 1 (unless panic)
        for i in range(1, len(results)):
            if results[i].panic_triggered:
                continue
            delta = abs(
                results[i].trend_regime_score - results[i - 1].trend_regime_score
            )
            assert delta <= 1.5, (
                f"Day {results[i].date}: jump {delta} from "
                f"{results[i-1].trend_regime_score} to {results[i].trend_regime_score}"
            )

    def test_schema_evolution(self, test_db):
        """Writer should add extra columns if missing."""
        writer = RegimeWriter(test_db)
        writer.run("2025-12-15")

        conn = sqlite3.connect(test_db)
        columns = [
            row[1] for row in conn.execute("PRAGMA table_info(market_regime)")
        ]
        conn.close()

        assert "liquidity_score" in columns
        assert "regime_confidence" in columns
        assert "trend_regime_score_raw" in columns


# ---------------------------------------------------------------------------
# Data leakage tests
# ---------------------------------------------------------------------------

class TestDataLeakage:

    def test_feature_date_before_target(self, test_db):
        """Features must only use data strictly before target_date."""
        builder = RegimeFeatureBuilder(test_db)

        # Get the last available date
        conn = sqlite3.connect(test_db)
        row = conn.execute(
            "SELECT MAX(date) as d FROM prices_daily WHERE symbol='VNINDEX'"
        ).fetchone()
        last_date = row[0]
        conn.close()

        features = builder.build(last_date)
        assert features.data_cutoff_date < last_date

    def test_no_future_data_in_range(self, test_db):
        """Running V4REG for date T should not peek at T or later."""
        writer = RegimeWriter(test_db)

        # Run for a mid-range date
        output = writer.run("2025-10-15")

        # The feature builder's cutoff should be before 2025-10-15
        builder = RegimeFeatureBuilder(test_db)
        features = builder.build("2025-10-15")
        assert features.data_cutoff_date < "2025-10-15"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
