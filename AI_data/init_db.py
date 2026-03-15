"""
AI_STOCK Database Initialization Script
Tạo 4 SQLite databases với đầy đủ tables theo DB_SCHEMA_MASTER v1.

Usage:
    python init_db.py              # Tạo mới (skip nếu đã tồn tại)
    python init_db.py --force      # Xóa và tạo lại từ đầu
    python init_db.py --verify     # Chỉ verify, không tạo
"""

import sqlite3
import sys
from pathlib import Path
from datetime import datetime

DATA_ROOT = Path(__file__).parent

# ---------------------------------------------------------------------------
# SCHEMA DEFINITIONS (mirror of DB_SCHEMA_MASTER.md)
# ---------------------------------------------------------------------------

MARKET_DB_SCHEMA = """
-- ============================================================
-- market.db — Raw market data
-- Writer: Data Pipeline | Reader: All
-- ============================================================

CREATE TABLE IF NOT EXISTS symbols_master (
    symbol          TEXT PRIMARY KEY,
    name            TEXT NOT NULL,
    exchange        TEXT DEFAULT 'HOSE',
    sector          TEXT,
    industry        TEXT,
    is_tradable     INTEGER DEFAULT 1,
    added_date      DATE NOT NULL,
    notes           TEXT
);

CREATE TABLE IF NOT EXISTS prices_daily (
    symbol          TEXT NOT NULL,
    date            DATE NOT NULL,
    open            REAL,
    high            REAL,
    low             REAL,
    close           REAL,
    volume          INTEGER,
    value           REAL,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (symbol, date),
    FOREIGN KEY (symbol) REFERENCES symbols_master(symbol)
);

CREATE INDEX IF NOT EXISTS idx_prices_daily_date ON prices_daily(date);
CREATE INDEX IF NOT EXISTS idx_prices_daily_symbol ON prices_daily(symbol);

CREATE TABLE IF NOT EXISTS prices_intraday (
    symbol          TEXT NOT NULL,
    date            DATE NOT NULL,
    snapshot_time   TEXT NOT NULL,
    open            REAL,
    high            REAL,
    low             REAL,
    close           REAL,
    volume          INTEGER,
    value           REAL,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (symbol, date, snapshot_time),
    FOREIGN KEY (symbol) REFERENCES symbols_master(symbol)
);

CREATE TABLE IF NOT EXISTS market_regime (
    date            DATE NOT NULL,
    snapshot_time   TEXT DEFAULT 'EOD',
    regime_score    REAL NOT NULL,
    regime_label    TEXT NOT NULL,
    breadth_score   REAL,
    volatility_score REAL,
    trend_score     REAL,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (date, snapshot_time)
);
"""

SIGNALS_DB_SCHEMA = """
-- ============================================================
-- signals.db — Expert outputs
-- Writer: Expert Layer | Reader: R Layer, X1
-- ============================================================

CREATE TABLE IF NOT EXISTS expert_signals (
    symbol          TEXT NOT NULL,
    date            DATE NOT NULL,
    snapshot_time   TEXT DEFAULT 'EOD',
    expert_id       TEXT NOT NULL,
    primary_score   REAL NOT NULL,
    secondary_score REAL,
    signal_code     TEXT,
    signal_quality  INTEGER DEFAULT 0,
    metadata_json   TEXT,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (symbol, date, snapshot_time, expert_id)
);

CREATE INDEX IF NOT EXISTS idx_expert_signals_date ON expert_signals(date);
CREATE INDEX IF NOT EXISTS idx_expert_signals_expert ON expert_signals(expert_id);

CREATE TABLE IF NOT EXISTS meta_features (
    symbol              TEXT NOT NULL,
    date                DATE NOT NULL,
    snapshot_time       TEXT DEFAULT 'EOD',
    bullish_expert_count    INTEGER,
    bearish_expert_count    INTEGER,
    neutral_expert_count    INTEGER,
    avg_score               REAL,
    trend_group_score       REAL,
    momentum_group_score    REAL,
    volume_group_score      REAL,
    volatility_group_score  REAL,
    structure_group_score   REAL,
    context_group_score     REAL,
    expert_conflict_score   REAL,
    expert_alignment_score  REAL,
    regime_score            REAL,
    created_at              TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (symbol, date, snapshot_time)
);

CREATE TABLE IF NOT EXISTS expert_conflicts (
    symbol          TEXT NOT NULL,
    date            DATE NOT NULL,
    snapshot_time   TEXT DEFAULT 'EOD',
    expert_a        TEXT NOT NULL,
    expert_b        TEXT NOT NULL,
    conflict_type   TEXT NOT NULL,
    severity        INTEGER,
    description     TEXT,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (symbol, date, snapshot_time, expert_a, expert_b)
);
"""

MODELS_DB_SCHEMA = """
-- ============================================================
-- models.db — R Layer outputs
-- Writer: R Layer | Reader: X1, Brain
-- ============================================================

CREATE TABLE IF NOT EXISTS r_predictions (
    symbol              TEXT NOT NULL,
    date                DATE NOT NULL,
    snapshot_time       TEXT DEFAULT 'EOD',
    r1_score            REAL,
    r2_score            REAL,
    r3_score            REAL,
    r4_score            REAL,
    r5_score            REAL,
    ensemble_score      REAL,
    ensemble_confidence REAL,
    ensemble_direction  INTEGER,
    model_version       TEXT,
    created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (symbol, date, snapshot_time)
);

CREATE INDEX IF NOT EXISTS idx_r_predictions_date ON r_predictions(date);

CREATE TABLE IF NOT EXISTS training_history (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    model_id        TEXT NOT NULL,
    train_date      DATE NOT NULL,
    train_start     TIMESTAMP,
    train_end       TIMESTAMP,
    data_start_date DATE,
    data_end_date   DATE,
    sample_count    INTEGER,
    hyperparams_json TEXT,
    metrics_json    TEXT,
    model_version   TEXT,
    status          TEXT DEFAULT 'COMPLETED',
    notes           TEXT
);

CREATE TABLE IF NOT EXISTS model_metrics (
    model_id        TEXT NOT NULL,
    eval_date       DATE NOT NULL,
    metric_name     TEXT NOT NULL,
    metric_value    REAL,
    eval_period     TEXT,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (model_id, eval_date, metric_name, eval_period)
);

CREATE TABLE IF NOT EXISTS feature_importance (
    model_id        TEXT NOT NULL,
    train_date      DATE NOT NULL,
    feature_name    TEXT NOT NULL,
    importance      REAL,
    rank            INTEGER,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (model_id, train_date, feature_name)
);
"""

AUDIT_DB_SCHEMA = """
-- ============================================================
-- audit.db — Feedback & performance tracking
-- Writer: Feedback Engine | Reader: Brain, Dashboard
-- ============================================================

CREATE TABLE IF NOT EXISTS signal_outcomes (
    symbol          TEXT NOT NULL,
    signal_date     DATE NOT NULL,
    snapshot_time   TEXT DEFAULT 'EOD',
    ensemble_score  REAL,
    ensemble_direction INTEGER,
    return_t1       REAL,
    return_t5       REAL,
    return_t10      REAL,
    price_at_signal REAL,
    price_t1        REAL,
    price_t5        REAL,
    price_t10       REAL,
    correct_t1      INTEGER,
    correct_t5      INTEGER,
    correct_t10     INTEGER,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (symbol, signal_date, snapshot_time)
);

CREATE TABLE IF NOT EXISTS expert_reliability (
    expert_id       TEXT NOT NULL,
    eval_date       DATE NOT NULL,
    regime          TEXT,
    eval_period     TEXT NOT NULL,
    total_signals   INTEGER,
    correct_signals INTEGER,
    win_rate        REAL,
    avg_return      REAL,
    avg_score_when_correct  REAL,
    avg_score_when_wrong    REAL,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (expert_id, eval_date, regime, eval_period)
);

CREATE TABLE IF NOT EXISTS r_model_reliability (
    model_id        TEXT NOT NULL,
    eval_date       DATE NOT NULL,
    eval_period     TEXT NOT NULL,
    total_predictions INTEGER,
    correct_predictions INTEGER,
    accuracy        REAL,
    avg_score_error REAL,
    directional_accuracy REAL,
    sharpe_ratio    REAL,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (model_id, eval_date, eval_period)
);
"""

# ---------------------------------------------------------------------------
# DB definitions: (filename, schema, expected_tables)
# ---------------------------------------------------------------------------

DATABASES = [
    (
        "market.db",
        MARKET_DB_SCHEMA,
        ["symbols_master", "prices_daily", "prices_intraday", "market_regime"],
    ),
    (
        "signals.db",
        SIGNALS_DB_SCHEMA,
        ["expert_signals", "meta_features", "expert_conflicts"],
    ),
    (
        "models.db",
        MODELS_DB_SCHEMA,
        ["r_predictions", "training_history", "model_metrics", "feature_importance"],
    ),
    (
        "audit.db",
        AUDIT_DB_SCHEMA,
        ["signal_outcomes", "expert_reliability", "r_model_reliability"],
    ),
]


def init_database(db_path: Path, schema: str, expected_tables: list[str]) -> bool:
    """Khởi tạo 1 database. Returns True nếu thành công."""
    try:
        conn = sqlite3.connect(str(db_path))
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.executescript(schema)

        # Verify tables
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        )
        actual_tables = [row[0] for row in cursor.fetchall()]
        conn.close()

        missing = set(expected_tables) - set(actual_tables)
        if missing:
            print(f"  [ERROR] Missing tables: {missing}")
            return False

        print(f"  [OK] {db_path.name}: {len(actual_tables)} tables created")
        for t in actual_tables:
            print(f"       - {t}")
        return True

    except Exception as e:
        print(f"  [ERROR] {db_path.name}: {e}")
        return False


def verify_database(db_path: Path, expected_tables: list[str]) -> bool:
    """Verify database tồn tại và có đủ tables."""
    if not db_path.exists():
        print(f"  [MISSING] {db_path.name}")
        return False

    try:
        conn = sqlite3.connect(str(db_path))
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        )
        actual_tables = [row[0] for row in cursor.fetchall()]

        # Count rows per table
        for t in actual_tables:
            count = conn.execute(f"SELECT COUNT(*) FROM [{t}]").fetchone()[0]
            print(f"       - {t}: {count} rows")

        conn.close()

        missing = set(expected_tables) - set(actual_tables)
        if missing:
            print(f"  [WARN] {db_path.name}: missing tables {missing}")
            return False

        print(f"  [OK] {db_path.name}: {len(actual_tables)} tables verified")
        return True

    except Exception as e:
        print(f"  [ERROR] {db_path.name}: {e}")
        return False


def main():
    force = "--force" in sys.argv
    verify_only = "--verify" in sys.argv

    print("=" * 60)
    print("AI_STOCK Database Initialization")
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Data root: {DATA_ROOT}")
    print(f"Mode: {'VERIFY' if verify_only else 'FORCE RECREATE' if force else 'CREATE'}")
    print("=" * 60)

    success_count = 0

    for db_name, schema, expected_tables in DATABASES:
        db_path = DATA_ROOT / db_name
        print(f"\n--- {db_name} ---")

        if verify_only:
            if verify_database(db_path, expected_tables):
                success_count += 1
            continue

        if db_path.exists():
            if force:
                db_path.unlink()
                print(f"  Deleted existing {db_name}")
            else:
                print(f"  Already exists, verifying...")
                if verify_database(db_path, expected_tables):
                    success_count += 1
                    continue
                print(f"  Verification failed, recreating...")
                db_path.unlink()

        if init_database(db_path, schema, expected_tables):
            success_count += 1

    print("\n" + "=" * 60)
    print(f"Result: {success_count}/{len(DATABASES)} databases OK")
    if success_count == len(DATABASES):
        print("All databases initialized successfully.")
    else:
        print("Some databases failed. Check errors above.")
        sys.exit(1)


if __name__ == "__main__":
    main()
