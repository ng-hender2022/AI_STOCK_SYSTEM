# AI_STOCK DATABASE SCHEMA MASTER v1

Generated: 2026-03-15
Status: ACTIVE
Engine: SQLite
Location: D:\AI\AI_data\

---

## 1. DATABASE FILES

| File | Mục đích | Writer | Reader |
|---|---|---|---|
| market.db | Raw market data | Data Pipeline | All |
| signals.db | Expert outputs | Expert Layer | R Layer, X1 |
| models.db | Model outputs | R Layer | X1, Brain |
| audit.db | Feedback & tracking | Feedback Engine | Brain, Dashboard |

---

## 2. market.db

### 2.1 symbols_master
```sql
CREATE TABLE symbols_master (
    symbol          TEXT PRIMARY KEY,
    name            TEXT NOT NULL,
    exchange        TEXT DEFAULT 'HOSE',
    sector          TEXT,
    industry        TEXT,
    is_tradable     INTEGER DEFAULT 1,    -- 0=VNINDEX, 1=tradable stock
    added_date      DATE NOT NULL,
    notes           TEXT
);
-- 92 rows: 91 stocks + VNINDEX
```

### 2.2 prices_daily
```sql
CREATE TABLE prices_daily (
    symbol          TEXT NOT NULL,
    date            DATE NOT NULL,
    open            REAL,
    high            REAL,
    low             REAL,
    close           REAL,
    volume          INTEGER,
    value           REAL,           -- giá trị giao dịch (VND)
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (symbol, date),
    FOREIGN KEY (symbol) REFERENCES symbols_master(symbol)
);

CREATE INDEX idx_prices_daily_date ON prices_daily(date);
CREATE INDEX idx_prices_daily_symbol ON prices_daily(symbol);
```

### 2.3 prices_intraday
```sql
CREATE TABLE prices_intraday (
    symbol          TEXT NOT NULL,
    date            DATE NOT NULL,
    snapshot_time   TEXT NOT NULL,       -- 'HH:MM' format
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
```

### 2.4 market_regime
```sql
CREATE TABLE market_regime (
    date            DATE NOT NULL,
    snapshot_time   TEXT,
    regime_score    REAL NOT NULL,       -- -4 → +4
    regime_label    TEXT NOT NULL,        -- 'STRONG_BEAR','BEAR','WEAK_BEAR','NEUTRAL','WEAK_BULL','BULL','STRONG_BULL'
    breadth_score   REAL,
    volatility_score REAL,
    trend_score     REAL,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (date, snapshot_time)
);
```

---

## 3. signals.db

### 3.1 expert_signals
```sql
CREATE TABLE expert_signals (
    symbol          TEXT NOT NULL,
    date            DATE NOT NULL,
    snapshot_time   TEXT DEFAULT 'EOD',
    expert_id       TEXT NOT NULL,       -- V4I, V4RSI, V4REG...
    primary_score   REAL NOT NULL,       -- score chính theo scale rulebook
    secondary_score REAL,                -- score phụ (optional)
    signal_code     TEXT,                -- mã tín hiệu chuẩn (xem SIGNAL_CODEBOOK)
    signal_quality  INTEGER DEFAULT 0,   -- 0..4
    metadata_json   TEXT,                -- JSON cho extra data
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (symbol, date, snapshot_time, expert_id)
);

CREATE INDEX idx_expert_signals_date ON expert_signals(date);
CREATE INDEX idx_expert_signals_expert ON expert_signals(expert_id);
```

### 3.2 meta_features
```sql
CREATE TABLE meta_features (
    symbol              TEXT NOT NULL,
    date                DATE NOT NULL,
    snapshot_time       TEXT DEFAULT 'EOD',

    -- Expert counts
    bullish_expert_count    INTEGER,
    bearish_expert_count    INTEGER,
    neutral_expert_count    INTEGER,

    -- Group scores (normalized -4 → +4)
    avg_score               REAL,
    trend_group_score       REAL,
    momentum_group_score    REAL,
    volume_group_score      REAL,
    volatility_group_score  REAL,
    structure_group_score   REAL,
    context_group_score     REAL,

    -- Derived
    expert_conflict_score   REAL,       -- 0=aligned, 1=max conflict
    expert_alignment_score  REAL,       -- 0=no alignment, 1=perfect
    regime_score            REAL,       -- from V4REG

    created_at              TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (symbol, date, snapshot_time)
);
```

### 3.3 expert_conflicts
```sql
CREATE TABLE expert_conflicts (
    symbol          TEXT NOT NULL,
    date            DATE NOT NULL,
    snapshot_time   TEXT DEFAULT 'EOD',
    expert_a        TEXT NOT NULL,
    expert_b        TEXT NOT NULL,
    conflict_type   TEXT NOT NULL,       -- 'DIRECTION','MAGNITUDE','TIMING'
    severity        INTEGER,             -- 1..4
    description     TEXT,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (symbol, date, snapshot_time, expert_a, expert_b)
);
```

---

## 4. models.db

### 4.1 r_predictions
```sql
CREATE TABLE r_predictions (
    symbol              TEXT NOT NULL,
    date                DATE NOT NULL,
    snapshot_time       TEXT DEFAULT 'EOD',

    r1_score            REAL,           -- -4 → +4
    r2_score            REAL,           -- -4 → +4
    r3_score            REAL,           -- -4 → +4
    r4_score            REAL,           -- -4 → +4
    r5_score            REAL,           -- -4 → +4

    ensemble_score      REAL,           -- -4 → +4 (weighted average)
    ensemble_confidence REAL,           -- 0 → 1
    ensemble_direction  INTEGER,        -- -1 / 0 / +1

    model_version       TEXT,
    created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (symbol, date, snapshot_time)
);

CREATE INDEX idx_r_predictions_date ON r_predictions(date);
```

### 4.2 training_history
```sql
CREATE TABLE training_history (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    model_id        TEXT NOT NULL,       -- R1, R2, R3, R4, R5
    train_date      DATE NOT NULL,
    train_start     TIMESTAMP,
    train_end       TIMESTAMP,
    data_start_date DATE,
    data_end_date   DATE,
    sample_count    INTEGER,
    hyperparams_json TEXT,
    metrics_json    TEXT,               -- accuracy, loss, etc.
    model_version   TEXT,
    status          TEXT DEFAULT 'COMPLETED',
    notes           TEXT
);
```

### 4.3 model_metrics
```sql
CREATE TABLE model_metrics (
    model_id        TEXT NOT NULL,
    eval_date       DATE NOT NULL,
    metric_name     TEXT NOT NULL,       -- 'accuracy','precision','recall','f1','mse','sharpe'
    metric_value    REAL,
    eval_period     TEXT,                -- '1W','1M','3M','6M','1Y'
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (model_id, eval_date, metric_name, eval_period)
);
```

### 4.4 feature_importance
```sql
CREATE TABLE feature_importance (
    model_id        TEXT NOT NULL,
    train_date      DATE NOT NULL,
    feature_name    TEXT NOT NULL,
    importance      REAL,
    rank            INTEGER,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (model_id, train_date, feature_name)
);
```

---

## 5. audit.db

### 5.1 signal_outcomes
```sql
CREATE TABLE signal_outcomes (
    symbol          TEXT NOT NULL,
    signal_date     DATE NOT NULL,
    snapshot_time   TEXT DEFAULT 'EOD',
    ensemble_score  REAL,
    ensemble_direction INTEGER,

    -- Actual returns
    return_t1       REAL,               -- return after 1 day
    return_t5       REAL,               -- return after 5 days
    return_t10      REAL,               -- return after 10 days
    price_at_signal REAL,
    price_t1        REAL,
    price_t5        REAL,
    price_t10       REAL,

    -- Classification outcome
    correct_t1      INTEGER,            -- 1=direction matched, 0=not
    correct_t5      INTEGER,
    correct_t10     INTEGER,

    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (symbol, signal_date, snapshot_time)
);
```

### 5.2 expert_reliability
```sql
CREATE TABLE expert_reliability (
    expert_id       TEXT NOT NULL,
    eval_date       DATE NOT NULL,
    regime          TEXT,                -- regime label at time of signal
    eval_period     TEXT NOT NULL,       -- '1W','1M','3M'

    total_signals   INTEGER,
    correct_signals INTEGER,
    win_rate        REAL,
    avg_return      REAL,
    avg_score_when_correct  REAL,
    avg_score_when_wrong    REAL,

    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (expert_id, eval_date, regime, eval_period)
);
```

### 5.3 r_model_reliability
```sql
CREATE TABLE r_model_reliability (
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
```

---

## 6. QUY TẮC CHUNG

1. **Primary Keys**: Luôn composite (symbol, date, snapshot_time, ...)
2. **snapshot_time**: 'EOD' cho daily, 'HH:MM' cho intraday
3. **Timestamps**: UTC+7 (Vietnam timezone)
4. **NULL handling**: score fields có thể NULL nếu expert/model chưa chạy
5. **Naming**: snake_case cho tất cả column names
6. **Foreign Keys**: Enforce qua SQLite PRAGMA foreign_keys = ON

---

*Document này là schema master cho toàn bộ databases.*
*Mọi thay đổi schema phải cập nhật file này TRƯỚC khi sửa code.*
