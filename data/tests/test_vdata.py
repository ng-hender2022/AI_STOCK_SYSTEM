"""
Vdata Tests
Covers: AmiBroker importer, calendar builder, label builder,
        normalizer, validator, leak checker.
"""

import csv
import sqlite3
import json
from datetime import date, timedelta
from pathlib import Path

import pytest
import numpy as np

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from importers.amibroker_importer import AmiBrokerImporter
from calendar_builder import CalendarBuilder
from label_builder import LabelBuilder, LeakageError
from normalizer import Normalizer
from validator import Validator, ValidationReport
from leak_checker import LeakChecker, LeakageError as CheckerLeakageError


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _create_market_db(db_path: str, num_days: int = 200) -> None:
    """Create market.db with synthetic data."""
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
        CREATE TABLE IF NOT EXISTS prices_intraday (
            symbol TEXT NOT NULL, date DATE NOT NULL,
            snapshot_time TEXT NOT NULL,
            open REAL, high REAL, low REAL, close REAL,
            volume INTEGER, value REAL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (symbol, date, snapshot_time)
        );
        CREATE TABLE IF NOT EXISTS market_regime (
            date DATE NOT NULL, snapshot_time TEXT DEFAULT 'EOD',
            regime_score REAL NOT NULL, regime_label TEXT NOT NULL,
            breadth_score REAL, volatility_score REAL, trend_score REAL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (date, snapshot_time)
        );
    """)

    symbols = ["VNINDEX", "FPT", "VNM", "HPG"]
    for s in symbols:
        t = 0 if s == "VNINDEX" else 1
        conn.execute(
            "INSERT OR IGNORE INTO symbols_master (symbol,name,is_tradable,added_date) VALUES (?,?,?,?)",
            (s, s, t, "2025-01-01"),
        )

    base = date(2025, 1, 1)
    np.random.seed(42)
    for s in symbols:
        price = 1200.0 if s == "VNINDEX" else 80.0
        for i in range(num_days):
            d = base + timedelta(days=i)
            if d.weekday() >= 5:
                continue
            price *= 1 + np.random.normal(0.0003, 0.01)
            h = price * 1.005
            l = price * 0.995
            o = price * (1 + np.random.normal(0, 0.002))
            v = int(np.random.uniform(1e6, 5e6))
            conn.execute(
                "INSERT OR IGNORE INTO prices_daily VALUES (?,?,?,?,?,?,?,NULL,CURRENT_TIMESTAMP)",
                (s, d.isoformat(), round(o, 2), round(h, 2), round(l, 2), round(price, 2), v),
            )

    conn.commit()
    conn.close()


def _create_signals_db(db_path: str) -> None:
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


def _create_ami_csv(csv_path: str) -> None:
    """Create synthetic AmiBroker CSV."""
    with open(csv_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Ticker", "Date", "Open", "High", "Low", "Close", "Volume", "RefPrice"])
        base = date(2025, 6, 1)
        for i in range(30):
            d = base + timedelta(days=i)
            if d.weekday() >= 5:
                continue
            for sym in ["FPT", "VNM", "UNKNOWN_SYM"]:
                p = 100 + i * 0.5
                writer.writerow([
                    sym,
                    d.strftime("%m/%d/%Y 00:00:00"),
                    round(p * 0.99, 2), round(p * 1.01, 2),
                    round(p * 0.98, 2), round(p, 2),
                    1000000 + i * 10000,
                    round(p, 2),
                ])


def _create_calendar_csv(csv_path: str) -> None:
    """Create synthetic VNINDEX trading calendar CSV."""
    with open(csv_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Ticker", "Date", "Close", "Volume"])
        base = date(2025, 1, 1)
        price = 1200.0
        for i in range(200):
            d = base + timedelta(days=i)
            if d.weekday() >= 5:
                continue
            price *= 1.001
            writer.writerow([
                "VNINDEX",
                d.strftime("%m/%d/%Y 00:00:00"),
                round(price, 2),
                10000000 + i * 100000,
            ])


@pytest.fixture
def test_env(tmp_path):
    market_db = str(tmp_path / "market.db")
    signals_db = str(tmp_path / "signals.db")
    _create_market_db(market_db)
    _create_signals_db(signals_db)
    return market_db, signals_db, tmp_path


# ---------------------------------------------------------------------------
# AmiBroker Importer Tests
# ---------------------------------------------------------------------------

class TestAmiBrokerImporter:

    def test_import_file(self, test_env):
        market_db, _, tmp_path = test_env
        csv_path = str(tmp_path / "test.csv")
        _create_ami_csv(csv_path)

        importer = AmiBrokerImporter(market_db)
        # Don't filter universe (test symbols may not be in master)
        stats = importer.import_file(csv_path, filter_universe=False)
        assert stats["imported"] > 0
        assert stats["errors"] == 0

    def test_filter_universe(self, test_env):
        market_db, _, tmp_path = test_env
        csv_path = str(tmp_path / "test.csv")
        _create_ami_csv(csv_path)

        importer = AmiBrokerImporter(market_db)
        stats = importer.import_file(csv_path, filter_universe=True)
        # UNKNOWN_SYM should be skipped
        assert stats["skipped"] > 0

    def test_date_parsing(self, test_env):
        market_db, _, tmp_path = test_env
        csv_path = str(tmp_path / "dates.csv")
        with open(csv_path, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["Ticker", "Date", "Open", "High", "Low", "Close", "Volume", "RefPrice"])
            w.writerow(["FPT", "3/15/2026 00:00:00", "100", "101", "99", "100.5", "1000000", "100"])
            w.writerow(["FPT", "2026-03-16", "101", "102", "100", "101.5", "1000000", "101"])

        importer = AmiBrokerImporter(market_db)
        stats = importer.import_file(csv_path, filter_universe=False)
        assert stats["imported"] == 2

        conn = sqlite3.connect(market_db)
        rows = conn.execute(
            "SELECT date FROM prices_daily WHERE symbol='FPT' AND date >= '2026-03-15' ORDER BY date"
        ).fetchall()
        conn.close()
        assert rows[0][0] == "2026-03-15"
        assert rows[1][0] == "2026-03-16"

    def test_ref_price_column(self, test_env):
        market_db, _, tmp_path = test_env
        csv_path = str(tmp_path / "test.csv")
        _create_ami_csv(csv_path)

        importer = AmiBrokerImporter(market_db)
        importer.import_file(csv_path, filter_universe=False)

        conn = sqlite3.connect(market_db)
        cols = {row[1] for row in conn.execute("PRAGMA table_info(prices_daily)")}
        conn.close()
        assert "ref_price" in cols


# ---------------------------------------------------------------------------
# Calendar Builder Tests
# ---------------------------------------------------------------------------

class TestCalendarBuilder:

    def test_build_from_csv(self, test_env):
        market_db, _, tmp_path = test_env
        csv_path = str(tmp_path / "calendar.csv")
        _create_calendar_csv(csv_path)

        builder = CalendarBuilder(market_db)
        stats = builder.build_from_csv(csv_path)
        assert stats["dates_parsed"] > 100

    def test_get_trading_dates(self, test_env):
        market_db, _, tmp_path = test_env
        csv_path = str(tmp_path / "calendar.csv")
        _create_calendar_csv(csv_path)

        builder = CalendarBuilder(market_db)
        builder.build_from_csv(csv_path)
        dates = builder.get_trading_dates("2025-03-01", "2025-03-31")
        assert len(dates) > 15  # ~22 trading days in a month
        # No weekends
        from datetime import date as dt
        for d in dates:
            parsed = dt.fromisoformat(d)
            assert parsed.weekday() < 5

    def test_offset_trading_day(self, test_env):
        market_db, _, tmp_path = test_env
        csv_path = str(tmp_path / "calendar.csv")
        _create_calendar_csv(csv_path)

        builder = CalendarBuilder(market_db)
        builder.build_from_csv(csv_path)

        # T+5 should be 5 trading days ahead
        d = builder.offset_trading_day("2025-03-03", 5)
        assert d is not None
        assert d > "2025-03-03"

    def test_build_from_db(self, test_env):
        market_db, _, _ = test_env
        builder = CalendarBuilder(market_db)
        stats = builder.build_from_db()
        assert stats["dates_from_db"] > 0

    def test_master_csv_created(self, test_env, monkeypatch):
        market_db, _, tmp_path = test_env
        csv_path = str(tmp_path / "calendar.csv")
        _create_calendar_csv(csv_path)

        # Patch the module-level constant before CalendarBuilder uses it
        master_path = tmp_path / "TRADING_CALENDAR_MASTER.csv"
        import data.calendar_builder as cb
        monkeypatch.setattr(cb, "CALENDAR_MASTER_PATH", master_path)
        # Also patch in calendar_builder used by test imports
        monkeypatch.setattr("calendar_builder.CALENDAR_MASTER_PATH", master_path)

        builder = CalendarBuilder(market_db)
        builder.build_from_csv(csv_path)

        assert master_path.exists()


# ---------------------------------------------------------------------------
# Label Builder Tests
# ---------------------------------------------------------------------------

class TestLabelBuilder:

    def test_compute_labels(self, test_env):
        market_db, _, tmp_path = test_env
        # Build calendar from DB first
        CalendarBuilder(market_db).build_from_db()

        lb = LabelBuilder(market_db)
        dates = CalendarBuilder(market_db).get_trading_dates()
        # Pick a date with enough forward room
        mid_date = dates[len(dates) // 2]
        result = lb.compute_labels("FPT", mid_date)

        assert result is not None
        assert result["feature_date"] == mid_date
        assert result["close_t"] > 0

    def test_label_values(self, test_env):
        market_db, _, _ = test_env
        CalendarBuilder(market_db).build_from_db()

        lb = LabelBuilder(market_db)
        dates = CalendarBuilder(market_db).get_trading_dates()
        mid_date = dates[len(dates) // 2]
        result = lb.compute_labels("FPT", mid_date)

        if result and result["t1_label"]:
            assert result["t1_label"] in ("UP", "DOWN", "NEUTRAL")
        if result and result["t5_label"]:
            assert result["t5_label"] in ("UP", "DOWN", "NEUTRAL")

    def test_leakage_check(self, test_env):
        """feature_date must be < label_date."""
        market_db, _, _ = test_env
        CalendarBuilder(market_db).build_from_db()

        lb = LabelBuilder(market_db)
        dates = CalendarBuilder(market_db).get_trading_dates()
        mid_date = dates[len(dates) // 2]

        # Normal call should not raise
        result = lb.compute_labels("FPT", mid_date, check_leak=True)
        # T+1 date must be after feature_date
        if result and result["t1_date"]:
            assert result["t1_date"] > mid_date

    def test_trading_day_offsets(self, test_env):
        """T+5 should be 5 trading days, not 5 calendar days."""
        market_db, _, _ = test_env
        CalendarBuilder(market_db).build_from_db()

        lb = LabelBuilder(market_db)
        dates = CalendarBuilder(market_db).get_trading_dates()
        mid_date = dates[50]
        result = lb.compute_labels("FPT", mid_date)

        if result and result["t5_date"]:
            # T+5 trading date should be exactly dates[55]
            assert result["t5_date"] == dates[55]


# ---------------------------------------------------------------------------
# Normalizer Tests
# ---------------------------------------------------------------------------

class TestNormalizer:

    def test_normalize_all(self, test_env):
        market_db, _, _ = test_env
        norm = Normalizer(market_db)
        stats = norm.normalize_all()
        assert "dates_fixed" in stats
        assert "numerics_fixed" in stats
        assert "symbols_fixed" in stats

    def test_date_normalization(self):
        assert Normalizer._normalize_date("3/15/2026 00:00:00") == "2026-03-15"
        assert Normalizer._normalize_date("2026-03-15") == "2026-03-15"
        assert Normalizer._normalize_date("12/31/2025") == "2025-12-31"


# ---------------------------------------------------------------------------
# Validator Tests
# ---------------------------------------------------------------------------

class TestValidator:

    def test_validate_clean_data(self, test_env):
        market_db, _, _ = test_env
        v = Validator(market_db)
        report = v.validate_all()
        assert isinstance(report, ValidationReport)
        assert report.total_rows > 0
        assert report.duplicates == 0
        assert report.missing_close == 0
        assert report.negative_volumes == 0

    def test_detect_ohlc_issues(self, test_env):
        market_db, _, _ = test_env
        # Insert bad row
        conn = sqlite3.connect(market_db)
        conn.execute(
            "INSERT INTO prices_daily (symbol,date,open,high,low,close,volume) "
            "VALUES ('FPT','2099-01-01',100,90,110,100,1000)"  # high < low
        )
        conn.commit()
        conn.close()

        v = Validator(market_db)
        report = v.validate_all()
        assert report.ohlc_inconsistencies > 0

    def test_detect_spike(self, test_env):
        market_db, _, _ = test_env
        conn = sqlite3.connect(market_db)
        # Add ref_price column
        try:
            conn.execute("ALTER TABLE prices_daily ADD COLUMN ref_price REAL")
        except Exception:
            pass
        # Insert row with big spike vs ref
        conn.execute(
            "INSERT OR REPLACE INTO prices_daily (symbol,date,open,high,low,close,volume,ref_price) "
            "VALUES ('FPT','2099-06-01',100,120,95,115,1000,80)"  # 115 vs 80 = 43%
        )
        conn.commit()
        conn.close()

        v = Validator(market_db)
        report = v.validate_all()
        assert report.spike_violations > 0


# ---------------------------------------------------------------------------
# Leak Checker Tests
# ---------------------------------------------------------------------------

class TestLeakChecker:

    def test_train_val_order_pass(self, test_env):
        market_db, signals_db, _ = test_env
        checker = LeakChecker(market_db, signals_db)
        result = checker.check_train_val_order("2025-06-30", "2025-07-01")
        assert result["passed"] is True

    def test_train_val_order_fail(self, test_env):
        market_db, signals_db, _ = test_env
        checker = LeakChecker(market_db, signals_db)
        result = checker.check_train_val_order("2025-07-01", "2025-06-30")
        assert result["passed"] is False

    def test_check_all_pass(self, test_env):
        market_db, signals_db, _ = test_env
        checker = LeakChecker(market_db, signals_db)
        results = checker.check_all("2025-06-30", "2025-07-01")
        for v in results.values():
            assert v["passed"] is True

    def test_check_all_fail_raises(self, test_env):
        market_db, signals_db, _ = test_env
        checker = LeakChecker(market_db, signals_db)
        with pytest.raises(CheckerLeakageError):
            checker.check_all("2025-07-01", "2025-06-30")


# ---------------------------------------------------------------------------
# First Trading Date / Listing Date Tests
# ---------------------------------------------------------------------------

class TestFirstTradingDate:

    def test_importer_sets_first_trading_date(self, test_env):
        """AmiBroker importer should set first_trading_date in symbols_master."""
        market_db, _, tmp_path = test_env
        csv_path = str(tmp_path / "test.csv")
        _create_ami_csv(csv_path)

        importer = AmiBrokerImporter(market_db)
        importer.import_file(csv_path, filter_universe=False)

        conn = sqlite3.connect(market_db)
        # Check column exists
        cols = {row[1] for row in conn.execute("PRAGMA table_info(symbols_master)")}
        assert "first_trading_date" in cols

        # Check FPT has a first_trading_date
        row = conn.execute(
            "SELECT first_trading_date FROM symbols_master WHERE symbol='FPT'"
        ).fetchone()
        conn.close()
        assert row is not None
        assert row[0] is not None

    def test_no_data_before_first_trading_date(self, test_env):
        """No price data should exist before first_trading_date."""
        market_db, _, tmp_path = test_env

        # Create a stock that lists late
        conn = sqlite3.connect(market_db)
        conn.execute(
            "INSERT OR IGNORE INTO symbols_master (symbol,name,is_tradable,added_date) VALUES (?,?,?,?)",
            ("LATE", "Late Stock", 1, "2025-01-01"),
        )
        # Add data starting from 2025-04-01 (late lister)
        for i in range(20):
            d = date(2025, 4, 1) + timedelta(days=i)
            if d.weekday() >= 5:
                continue
            conn.execute(
                "INSERT OR IGNORE INTO prices_daily (symbol,date,open,high,low,close,volume) VALUES (?,?,?,?,?,?,?)",
                ("LATE", d.isoformat(), 50, 51, 49, 50, 100000),
            )
        conn.commit()

        # Now run importer to set first_trading_date
        csv_path = str(tmp_path / "empty.csv")
        with open(csv_path, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["Ticker", "Date", "Open", "High", "Low", "Close", "Volume", "RefPrice"])

        importer = AmiBrokerImporter(market_db)
        importer.import_file(csv_path, filter_universe=False)

        # Verify first_trading_date is set correctly
        row = conn.execute(
            "SELECT first_trading_date FROM symbols_master WHERE symbol='LATE'"
        ).fetchone()
        assert row[0] == "2025-04-01"
        conn.close()

    def test_label_builder_skips_before_listing(self, test_env):
        """LabelBuilder should return None for dates before first_trading_date."""
        market_db, _, _ = test_env
        CalendarBuilder(market_db).build_from_db()

        # Set first_trading_date for FPT to a mid-range date
        conn = sqlite3.connect(market_db)
        cols = {row[1] for row in conn.execute("PRAGMA table_info(symbols_master)")}
        if "first_trading_date" not in cols:
            conn.execute("ALTER TABLE symbols_master ADD COLUMN first_trading_date DATE")
        conn.execute("UPDATE symbols_master SET first_trading_date='2025-03-01' WHERE symbol='FPT'")
        conn.commit()
        conn.close()

        lb = LabelBuilder(market_db)
        # Before listing date — should return None
        result = lb.compute_labels("FPT", "2025-02-15")
        assert result is None

        # After listing date — should work
        result = lb.compute_labels("FPT", "2025-04-01")
        assert result is not None

    def test_leak_checker_detects_pre_listing_prices(self, test_env):
        """LeakChecker should detect price data before first_trading_date."""
        market_db, signals_db, _ = test_env

        # Set first_trading_date AFTER some existing data
        conn = sqlite3.connect(market_db)
        cols = {row[1] for row in conn.execute("PRAGMA table_info(symbols_master)")}
        if "first_trading_date" not in cols:
            conn.execute("ALTER TABLE symbols_master ADD COLUMN first_trading_date DATE")
        # Set FPT first_trading_date to 2025-06-01, but data starts 2025-01-01
        conn.execute("UPDATE symbols_master SET first_trading_date='2025-06-01' WHERE symbol='FPT'")
        conn.commit()
        conn.close()

        checker = LeakChecker(market_db, signals_db)
        result = checker.check_no_pre_listing_data()
        assert result["passed"] is False  # FPT has data before 2025-06-01

    def test_leak_checker_passes_when_clean(self, test_env):
        """LeakChecker should pass when all data is after first_trading_date."""
        market_db, signals_db, _ = test_env

        conn = sqlite3.connect(market_db)
        cols = {row[1] for row in conn.execute("PRAGMA table_info(symbols_master)")}
        if "first_trading_date" not in cols:
            conn.execute("ALTER TABLE symbols_master ADD COLUMN first_trading_date DATE")
        # Set first_trading_date to before all data
        conn.execute("UPDATE symbols_master SET first_trading_date='2024-01-01'")
        conn.commit()
        conn.close()

        checker = LeakChecker(market_db, signals_db)
        result = checker.check_no_pre_listing_data()
        assert result["passed"] is True

    def test_get_first_trading_dates(self, test_env):
        """LeakChecker.get_first_trading_dates should return dict."""
        market_db, signals_db, _ = test_env

        conn = sqlite3.connect(market_db)
        cols = {row[1] for row in conn.execute("PRAGMA table_info(symbols_master)")}
        if "first_trading_date" not in cols:
            conn.execute("ALTER TABLE symbols_master ADD COLUMN first_trading_date DATE")
        conn.execute("UPDATE symbols_master SET first_trading_date='2025-01-02' WHERE symbol='FPT'")
        conn.commit()
        conn.close()

        checker = LeakChecker(market_db, signals_db)
        ftd = checker.get_first_trading_dates()
        assert isinstance(ftd, dict)
        assert ftd.get("FPT") == "2025-01-02"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
