"""
X1 Decision Engine Tests
Tests: decision logic, position sizing, risk management, portfolio, output writer.
"""

import sqlite3
from pathlib import Path

import pytest

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from AI_engine.x1.decision_engine import DecisionEngine, Decision
from AI_engine.x1.position_sizer import PositionSizer, PositionSize
from AI_engine.x1.risk_manager import RiskManager, RiskCheck
from AI_engine.x1.portfolio_engine import PortfolioEngine, Portfolio
from AI_engine.x1.output_writer import OutputWriter


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _create_test_dbs(tmp_path):
    """Create models.db + market.db with test data."""
    models_db = str(tmp_path / "models.db")
    market_db = str(tmp_path / "market.db")

    # Market DB
    mconn = sqlite3.connect(market_db)
    mconn.executescript("""
        CREATE TABLE symbols_master (
            symbol TEXT PRIMARY KEY, name TEXT, exchange TEXT,
            sector TEXT, industry TEXT, is_tradable INTEGER DEFAULT 1,
            added_date DATE, notes TEXT, is_index INTEGER DEFAULT 0
        );
        CREATE TABLE market_regime (
            date DATE NOT NULL, snapshot_time TEXT DEFAULT 'EOD',
            regime_score REAL, regime_label TEXT, breadth_score REAL,
            volatility_score REAL, trend_score REAL, liquidity_score REAL,
            PRIMARY KEY (date, snapshot_time)
        );
    """)
    # Add symbols
    for sym in ["FPT", "VNM", "HPG", "TCB", "VCB", "ACB", "MBB", "SSI", "MWG",
                 "REE", "DPM", "GAS", "PNJ", "VIC", "VHM", "HDB"]:
        mconn.execute("INSERT INTO symbols_master (symbol, name, is_tradable, added_date, is_index) VALUES (?,?,1,'2020-01-01',0)", (sym, sym))
    mconn.execute("INSERT INTO symbols_master (symbol, name, is_tradable, added_date, is_index) VALUES ('VNINDEX','VN Index',0,'2020-01-01',1)")

    # Normal regime
    mconn.execute("INSERT INTO market_regime VALUES ('2025-01-15','EOD',1.5,'BULL',1.0,1.5,1.0,0.5)")
    # Bear regime
    mconn.execute("INSERT INTO market_regime VALUES ('2025-02-15','EOD',-3.5,'STRONG_BEAR',-2.0,3.5,-2.0,-1.5)")
    # Bull regime low vol
    mconn.execute("INSERT INTO market_regime VALUES ('2025-03-15','EOD',2.5,'STRONG_BULL',2.0,1.0,2.0,1.5)")
    mconn.commit()
    mconn.close()

    # Models DB
    conn = sqlite3.connect(models_db)
    conn.executescript("""
        CREATE TABLE master_summary (
            symbol TEXT, date DATE, snapshot_time TEXT DEFAULT 'EOD',
            r0_score REAL, r1_score REAL, r2_score REAL,
            r3_score REAL, r4_score REAL, r5_score REAL,
            ensemble_score REAL, ensemble_confidence REAL, ensemble_direction INTEGER,
            agg_avg_score REAL, agg_median_score REAL, agg_dispersion REAL,
            agg_agreement_score REAL,
            agg_bullish_model_count INTEGER, agg_bearish_model_count INTEGER,
            agg_neutral_model_count INTEGER, agg_available_models INTEGER,
            summary_direction INTEGER, summary_strength REAL,
            PRIMARY KEY (symbol, date, snapshot_time)
        );
    """)

    # Strong buy signal (normal regime 2025-01-15, regime=1.5)
    conn.execute("INSERT INTO master_summary (symbol,date,snapshot_time,r0_score,r1_score,r2_score,r3_score,r4_score,r5_score,ensemble_score,ensemble_confidence,ensemble_direction,agg_avg_score,summary_direction,summary_strength) VALUES ('FPT','2025-01-15','EOD',2.0,2.5,2.0,3.0,2.0,2.5,2.5,0.85,1,2.3,1,2.3)")
    # Moderate buy
    conn.execute("INSERT INTO master_summary (symbol,date,snapshot_time,r0_score,r1_score,r2_score,r3_score,r4_score,r5_score,ensemble_score,ensemble_confidence,ensemble_direction,agg_avg_score,summary_direction,summary_strength) VALUES ('VNM','2025-01-15','EOD',1.0,1.5,1.0,1.5,1.0,1.0,1.2,0.6,1,1.1,1,1.1)")
    # Sell signal in neutral regime (regime=1.5, need thresh -2.5, agreement 4)
    # All 6 R models bearish -> should SELL
    conn.execute("INSERT INTO master_summary (symbol,date,snapshot_time,r0_score,r1_score,r2_score,r3_score,r4_score,r5_score,ensemble_score,ensemble_confidence,ensemble_direction,agg_avg_score,summary_direction,summary_strength) VALUES ('HPG','2025-01-15','EOD',-2.0,-3.0,-2.5,-3.0,-2.0,-2.5,-2.5,0.8,-1,-2.3,-1,2.3)")
    # Hold
    conn.execute("INSERT INTO master_summary (symbol,date,snapshot_time,r0_score,r1_score,r2_score,r3_score,r4_score,r5_score,ensemble_score,ensemble_confidence,ensemble_direction,agg_avg_score,summary_direction,summary_strength) VALUES ('TCB','2025-01-15','EOD',0.1,0.5,-0.2,0.3,0.1,0.2,0.3,0.5,0,0.2,0,0.2)")
    # VNINDEX
    conn.execute("INSERT INTO master_summary (symbol,date,snapshot_time,r0_score,r1_score,r2_score,r3_score,r4_score,r5_score,ensemble_score,ensemble_confidence,ensemble_direction,agg_avg_score,summary_direction,summary_strength) VALUES ('VNINDEX','2025-01-15','EOD',2.0,2.0,2.0,2.0,2.0,2.0,2.0,0.9,1,1.8,1,1.8)")

    # Bear regime date (2025-02-15, regime=-3.5): buy blocked
    conn.execute("INSERT INTO master_summary (symbol,date,snapshot_time,r0_score,r1_score,r2_score,r3_score,r4_score,r5_score,ensemble_score,ensemble_confidence,ensemble_direction,agg_avg_score,summary_direction,summary_strength) VALUES ('FPT','2025-02-15','EOD',2.0,2.5,2.0,3.0,2.0,2.5,2.5,0.85,1,2.3,1,2.3)")

    # Bull regime (2025-03-15, regime=2.5): sell in bull should be blocked unless very strong
    conn.execute("INSERT INTO master_summary (symbol,date,snapshot_time,r0_score,r1_score,r2_score,r3_score,r4_score,r5_score,ensemble_score,ensemble_confidence,ensemble_direction,agg_avg_score,summary_direction,summary_strength) VALUES ('FPT','2025-03-15','EOD',2.0,2.5,2.0,3.0,2.0,2.5,2.5,0.85,1,2.3,1,2.3)")
    # Weak sell in bull regime (score=-2.5, but regime=2.5 requires -3.5) -> should HOLD
    conn.execute("INSERT INTO master_summary (symbol,date,snapshot_time,r0_score,r1_score,r2_score,r3_score,r4_score,r5_score,ensemble_score,ensemble_confidence,ensemble_direction,agg_avg_score,summary_direction,summary_strength) VALUES ('HPG','2025-03-15','EOD',-2.0,-3.0,-2.0,-2.5,-1.0,-2.0,-2.5,0.7,-1,-2.0,-1,2.0)")
    # Strong sell in bull regime (score=-3.5, 5 models bearish) -> should SELL
    conn.execute("INSERT INTO master_summary (symbol,date,snapshot_time,r0_score,r1_score,r2_score,r3_score,r4_score,r5_score,ensemble_score,ensemble_confidence,ensemble_direction,agg_avg_score,summary_direction,summary_strength) VALUES ('VNM','2025-03-15','EOD',-3.5,-4.0,-3.0,-3.5,-3.0,-3.5,-3.5,0.9,-1,-3.4,-1,3.4)")

    conn.commit()
    conn.close()
    return models_db, market_db


@pytest.fixture
def test_dbs(tmp_path):
    return _create_test_dbs(tmp_path)


# ---------------------------------------------------------------------------
# Decision Engine Tests
# ---------------------------------------------------------------------------

class TestDecisionEngine:

    def test_strong_buy(self, test_dbs):
        mdb, mkdb = test_dbs
        engine = DecisionEngine(mdb, mkdb)
        d = engine.decide_symbol("FPT", "2025-01-15")
        assert d.action == "BUY"
        assert d.strength == "STRONG"

    def test_moderate_buy(self, test_dbs):
        mdb, mkdb = test_dbs
        engine = DecisionEngine(mdb, mkdb)
        d = engine.decide_symbol("VNM", "2025-01-15")
        assert d.action == "BUY"
        assert d.strength == "MODERATE"

    def test_sell_in_neutral_regime(self, test_dbs):
        """Neutral regime (1.5): score=-2.5 with 6 bearish models -> SELL."""
        mdb, mkdb = test_dbs
        engine = DecisionEngine(mdb, mkdb)
        d = engine.decide_symbol("HPG", "2025-01-15")
        assert d.action == "SELL"

    def test_hold(self, test_dbs):
        mdb, mkdb = test_dbs
        engine = DecisionEngine(mdb, mkdb)
        d = engine.decide_symbol("TCB", "2025-01-15")
        assert d.action == "HOLD"

    def test_vnindex_not_tradable(self, test_dbs):
        mdb, mkdb = test_dbs
        engine = DecisionEngine(mdb, mkdb)
        d = engine.decide_symbol("VNINDEX", "2025-01-15")
        assert d.action == "HOLD"
        assert "not tradable" in d.reason

    def test_regime_blocks_buy(self, test_dbs):
        """Bear regime (trend <= -3) should block buy signals."""
        mdb, mkdb = test_dbs
        engine = DecisionEngine(mdb, mkdb)
        d = engine.decide_symbol("FPT", "2025-02-15")
        assert d.action == "HOLD"
        assert d.regime_blocked is True

    def test_sell_blocked_in_bull_regime(self, test_dbs):
        """Bull regime (2.5): score=-2.5 but threshold is -3.5 -> HOLD (doesn't reach threshold)."""
        mdb, mkdb = test_dbs
        engine = DecisionEngine(mdb, mkdb)
        d = engine.decide_symbol("HPG", "2025-03-15")
        assert d.action == "HOLD"  # -2.5 > -3.5 threshold, so no sell triggered

    def test_strong_sell_passes_in_bull_regime(self, test_dbs):
        """Bull regime: score=-3.5 with 5+ bearish models -> SELL passes."""
        mdb, mkdb = test_dbs
        engine = DecisionEngine(mdb, mkdb)
        d = engine.decide_symbol("VNM", "2025-03-15")
        assert d.action == "SELL"

    def test_decide_all(self, test_dbs):
        mdb, mkdb = test_dbs
        engine = DecisionEngine(mdb, mkdb)
        decisions = engine.decide("2025-01-15")
        assert len(decisions) == 5
        actions = {d.symbol: d.action for d in decisions}
        assert actions["FPT"] == "BUY"
        assert actions["VNINDEX"] == "HOLD"


# ---------------------------------------------------------------------------
# Position Sizer Tests
# ---------------------------------------------------------------------------

class TestPositionSizer:

    def test_strong_buy_size(self):
        ps = PositionSizer()
        size = ps.size("FPT", "2025-01-15", "BUY", "STRONG", 0.85, 1.5, 2.0)
        assert size.weight > 0
        assert size.weight <= 0.10

    def test_hold_zero_weight(self):
        ps = PositionSizer()
        size = ps.size("TCB", "2025-01-15", "HOLD", "WEAK", 0.5, 0.0, 2.0)
        assert size.weight == 0.0

    def test_bull_regime_larger(self):
        ps = PositionSizer()
        normal = ps.size("FPT", "2025-01-15", "BUY", "STRONG", 0.8, 0.5, 2.0)
        bull = ps.size("FPT", "2025-01-15", "BUY", "STRONG", 0.8, 2.5, 1.0)
        assert bull.weight >= normal.weight

    def test_bear_regime_smaller(self):
        ps = PositionSizer()
        normal = ps.size("FPT", "2025-01-15", "BUY", "STRONG", 0.8, 0.5, 2.0)
        bear = ps.size("FPT", "2025-01-15", "BUY", "STRONG", 0.8, -2.5, 3.0)
        assert bear.weight <= normal.weight


# ---------------------------------------------------------------------------
# Risk Manager Tests
# ---------------------------------------------------------------------------

class TestRiskManager:

    def test_pass_normal(self):
        rm = RiskManager()
        check = rm.check({}, "FPT", 0.05)
        assert check.passed is True

    def test_max_positions(self):
        rm = RiskManager()
        positions = {f"SYM{i}": 0.05 for i in range(15)}
        check = rm.check(positions, "NEW", 0.05)
        assert check.passed is False
        assert "Max positions" in check.reason

    def test_max_exposure(self):
        rm = RiskManager()
        positions = {f"SYM{i}": 0.07 for i in range(11)}  # 77%
        check = rm.check(positions, "NEW", 0.05)  # 82% > 80%
        assert check.passed is False

    def test_max_single_position(self):
        rm = RiskManager()
        check = rm.check({}, "FPT", 0.15)  # 15% > 10%
        assert check.passed is False

    def test_drawdown_halves(self):
        rm = RiskManager()
        rm.set_drawdown(0.16)
        assert rm.drawdown_active is True

    def test_sector_limit(self):
        rm = RiskManager()
        check = rm.check({}, "FPT", 0.05, sector_weights={"Tech": 0.28}, new_sector="Tech")
        assert check.passed is False
        assert "Sector" in check.reason


# ---------------------------------------------------------------------------
# Portfolio Engine Tests
# ---------------------------------------------------------------------------

class TestPortfolioEngine:

    def test_build_portfolio(self, test_dbs):
        mdb, mkdb = test_dbs
        pe = PortfolioEngine(mdb, mkdb)
        portfolio = pe.build("2025-01-15")
        assert isinstance(portfolio, Portfolio)
        assert len(portfolio.entries) > 0
        assert portfolio.cash_weight >= 0
        assert portfolio.cash_weight <= 1.0

    def test_portfolio_has_buys_sells_holds(self, test_dbs):
        mdb, mkdb = test_dbs
        pe = PortfolioEngine(mdb, mkdb)
        portfolio = pe.build("2025-01-15")
        actions = [e.action for e in portfolio.entries]
        assert "BUY" in actions
        assert "SELL" in actions
        assert "HOLD" in actions


# ---------------------------------------------------------------------------
# Output Writer Tests
# ---------------------------------------------------------------------------

class TestOutputWriter:

    def test_write_decisions(self, test_dbs):
        mdb, mkdb = test_dbs
        pe = PortfolioEngine(mdb, mkdb)
        portfolio = pe.build("2025-01-15")

        writer = OutputWriter(mdb)
        stats = writer.write(portfolio)
        assert stats["written"] > 0
        assert stats["buys"] >= 1
        assert stats["sells"] >= 1

        # Verify DB
        conn = sqlite3.connect(mdb)
        count = conn.execute("SELECT COUNT(*) FROM x1_decisions WHERE date='2025-01-15'").fetchone()[0]
        conn.close()
        assert count == stats["written"]

    def test_idempotent(self, test_dbs):
        mdb, mkdb = test_dbs
        pe = PortfolioEngine(mdb, mkdb)
        portfolio = pe.build("2025-01-15")
        writer = OutputWriter(mdb)
        writer.write(portfolio)
        writer.write(portfolio)
        conn = sqlite3.connect(mdb)
        count = conn.execute("SELECT COUNT(*) FROM x1_decisions WHERE date='2025-01-15'").fetchone()[0]
        conn.close()
        assert count == len(portfolio.entries)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
