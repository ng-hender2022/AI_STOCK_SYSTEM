# AI_STOCK GLOBAL ARCHITECTURE v2

Generated: 2026-03-15
Brain root: D:\AI\AI_brain

---

## 1. SYSTEM PHILOSOPHY

```
Market Data → Experts → R Layer → X1
```

- **Experts**: xử lý data thô, output score theo rulebook riêng
- **R Layer**: học từ expert outputs, ensemble thành score chuẩn
- **X1**: ra quyết định dựa trên ensemble score

Separation of concerns:
- Experts KHÔNG học, KHÔNG predict
- R Layer HỌC, KHÔNG quyết định
- X1 QUYẾT ĐỊNH, KHÔNG học trực tiếp từ data thô

---

## 2. FOLDER STRUCTURE

```
D:\AI\
├── AI_brain\               ← Source of truth (architecture, protocols, rulebooks)
├── AI_data\                ← SQLite databases
│   ├── market.db
│   ├── signals.db
│   ├── models.db
│   └── audit.db
├── AI_engine\              ← All AI components
│   ├── experts\            ← 17 Expert modules
│   ├── r_layer\            ← R1~R5 models
│   └── x1\                 ← Decision engine
└── README.md
```

---

## 3. UNIVERSE

```
91 tradable Vietnamese stocks
+ VNINDEX (market reference)
= 92 symbols (toàn hệ thống dùng thống nhất)
```

Data source: **vnstock API**

---

## 4. DATABASE ARCHITECTURE

### 4.1 market.db
Raw market data — viết bởi data pipeline, đọc bởi tất cả.

```
symbols_master          ← danh sách 92 symbols
prices_daily            ← OHLCV daily
prices_intraday         ← snapshot intraday
market_regime           ← output V4REG (regime_score -4..+4)
```

### 4.2 signals.db
Expert outputs — viết bởi Expert Layer, đọc bởi R Layer và X1.

```
expert_signals          ← raw score từng expert, từng symbol, từng ngày
meta_features           ← aggregated features từ toàn bộ experts
expert_conflicts        ← conflict detection giữa các experts
```

### 4.3 models.db
Model outputs — viết bởi R Layer, đọc bởi X1 và Brain.

```
r_predictions           ← score -4..+4 của từng model R1~R5
r_ensemble              ← ensemble score + confidence
training_history        ← log training runs
model_metrics           ← accuracy, performance metrics
feature_importance      ← feature importance từng model
```

### 4.4 audit.db
Feedback và performance tracking — viết bởi Feedback Engine.

```
signal_outcomes         ← kết quả thực tế sau T+1, T+5, T+10
expert_reliability      ← win rate, avg return theo expert × regime
r_model_reliability     ← performance tracking từng R model
```

---

## 5. EXPERT LAYER

### 5.1 Nguyên tắc

- Experts là **deterministic engines** — không học, không predict
- Mỗi expert đọc từ `market.db`, ghi vào `signals.db`
- Mỗi expert output score theo **scale riêng của rulebook**
- Experts KHÔNG output probability, KHÔNG output buy/sell advice

### 5.2 Danh sách 17 Experts

#### TREND GROUP
| ID | Tên | Rulebook | Scale output |
|---|---|---|---|
| V4I | Ichimoku Expert | ICHIMOKU_RULEBOOK | -4 → +4 |
| V4MA | Moving Average Expert | MA_RULEBOOK | -4 → +4 |
| V4ADX | Trend Strength Expert | ADX_RULEBOOK | 0 → 4 |

#### MOMENTUM GROUP
| ID | Tên | Rulebook | Scale output |
|---|---|---|---|
| V4MACD | MACD Expert | MACD_RULEBOOK | -4 → +4 |
| V4RSI | RSI Expert | RSI_RULEBOOK | 0 → 100 |
| V4STO | Stochastic Expert | STOCHASTIC_RULEBOOK | 0 → 100 |

#### VOLUME GROUP
| ID | Tên | Rulebook | Scale output |
|---|---|---|---|
| V4V | Volume Behavior Expert | VOLUME_RULEBOOK | -4 → +4 |
| V4OBV | OBV Expert | OBV_RULEBOOK | -4 → +4 |

#### VOLATILITY GROUP
| ID | Tên | Rulebook | Scale output |
|---|---|---|---|
| V4ATR | ATR Expert | ATR_RULEBOOK | 0 → 4 |
| V4BB | Bollinger Bands Expert | BOLLINGER_RULEBOOK | -4 → +4 |

#### PRICE STRUCTURE GROUP
| ID | Tên | Rulebook | Scale output |
|---|---|---|---|
| V4P | Price Action Expert | PRICE_ACTION_RULEBOOK | -4 → +4 |
| V4CANDLE | Candlestick Expert | CANDLE_RULEBOOK | -4 → +4 |

#### MARKET CONTEXT GROUP
| ID | Tên | Rulebook | Scale output |
|---|---|---|---|
| V4BR | Breadth Expert | BREADTH_RULEBOOK | -4 → +4 |
| V4RS | Relative Strength Expert | RS_RULEBOOK | -4 → +4 |
| V4REG | Market Regime Expert | REGIME_RULEBOOK | -4 → +4 |

#### STRUCTURE / ENVIRONMENT GROUP
| ID | Tên | Rulebook | Scale output |
|---|---|---|---|
| V4S | Sector Strength Expert | SECTOR_RULEBOOK | -4 → +4 |
| V4LIQ | Liquidity Expert | LIQUIDITY_RULEBOOK | -4 → +4 |

### 5.3 Expert Output Schema (signals.db → expert_signals)

```
symbol                  TEXT
date                    DATE
snapshot_time           TEXT        ← null nếu daily
expert_id               TEXT        ← V4I, V4RSI, V4REG...
primary_score           REAL        ← score chính theo scale rulebook
secondary_score         REAL        ← score phụ nếu có (optional)
signal_code             TEXT        ← mã tín hiệu chuẩn
signal_quality          INTEGER     ← 0..4 (chất lượng tín hiệu)
created_at              TIMESTAMP
PRIMARY KEY (symbol, date, snapshot_time, expert_id)
```

### 5.4 Meta Features Schema (signals.db → meta_features)

```
symbol                  TEXT
date                    DATE
snapshot_time           TEXT

-- Aggregated từ toàn bộ 17 experts
bullish_expert_count    INTEGER     ← số experts có score > 0
bearish_expert_count    INTEGER     ← số experts có score < 0
neutral_expert_count    INTEGER

avg_score               REAL        ← trung bình score (normalized)
trend_group_score       REAL        ← avg score nhóm Trend
momentum_group_score    REAL        ← avg score nhóm Momentum
volume_group_score      REAL        ← avg score nhóm Volume
volatility_group_score  REAL        ← avg score nhóm Volatility
structure_group_score   REAL        ← avg score nhóm Price Structure
context_group_score     REAL        ← avg score nhóm Market Context

expert_conflict_score   REAL        ← độ mâu thuẫn giữa các experts
expert_alignment_score  REAL        ← độ đồng thuận
regime_score            REAL        ← từ V4REG

PRIMARY KEY (symbol, date, snapshot_time)
```

---

## 6. R LAYER

### 6.1 Nguyên tắc

- 5 models chạy **độc lập**, không phụ thuộc nhau
- Input: expert_signals + meta_features từ `signals.db`
- Output: score **-4 → +4** cho từng symbol (scale thống nhất toàn R Layer)
- Kết quả 5 models được **ensemble** thành 1 score cuối cho X1

### 6.2 Các Models

| ID | Loại | Đặc điểm |
|---|---|---|
| R1 | Linear Model | Nhanh, interpretable, baseline |
| R2 | Random Forest | Robust, handle non-linear |
| R3 | Gradient Boosting | High accuracy, sequential learning |
| R4 | Neural Network | Complex patterns |
| R5 | Sector Models | Train riêng theo từng sector |

**R5 chi tiết:**
- Mỗi sector có 1 sub-model riêng
- Cùng architecture, khác training data
- Output vẫn là score -4 → +4

### 6.3 R Layer Output Schema (models.db → r_predictions)

```
symbol                  TEXT
date                    DATE
snapshot_time           TEXT

r1_score                REAL        ← -4 → +4
r2_score                REAL        ← -4 → +4
r3_score                REAL        ← -4 → +4
r4_score                REAL        ← -4 → +4
r5_score                REAL        ← -4 → +4

ensemble_score          REAL        ← -4 → +4 (weighted average)
ensemble_confidence     REAL        ← 0 → 1 (độ đồng thuận 5 models)
ensemble_direction      INTEGER     ← -1 / 0 / +1

model_version           TEXT
created_at              TIMESTAMP

PRIMARY KEY (symbol, date, snapshot_time)
```

### 6.4 Ensemble Logic

```
ensemble_score = weighted_average(r1..r5)
ensemble_confidence = 1 - std(r1..r5) / 4
ensemble_direction:
    score > threshold  → +1 (bullish)
    score < -threshold → -1 (bearish)
    otherwise          →  0 (neutral)
```

Weights ban đầu bằng nhau (0.2 mỗi model), sau này Feedback Engine có thể điều chỉnh.

---

## 7. X1 DECISION ENGINE

- Đọc `ensemble_score` + `ensemble_confidence` từ `models.db`
- Đọc `regime_score` từ `market.db`
- Ra quyết định: BUY / SELL / HOLD + position sizing
- Chi tiết thiết kế X1 sẽ được bàn sau

---

## 8. DATA FLOW CHI TIẾT

```
vnstock API
    ↓
market.db (prices_daily, prices_intraday)
    ↓
17 Experts (đọc market.db)
    ↓
signals.db (expert_signals, meta_features, expert_conflicts)
    ↓
R1, R2, R3, R4, R5 (đọc signals.db)
    ↓
models.db (r_predictions, r_ensemble)
    ↓
X1 (đọc models.db + market.db)
    ↓
Decision Output

Feedback Engine (async, T+1/T+5/T+10):
models.db + market.db → audit.db
```

---

## 9. BUILD ROADMAP

### Phase 1 — Foundation
- [ ] AI_brain folder structure
- [ ] AI_data folder + DB schema initialization
- [ ] AI_engine folder skeleton
- [ ] Rulebooks cho 17 experts

### Phase 2 — Expert Layer
- [ ] V4REG (Market Regime) — build trước, các expert khác cần
- [ ] Trend group: V4I, V4MA, V4ADX
- [ ] Momentum group: V4MACD, V4RSI, V4STO
- [ ] Volume group: V4V, V4OBV
- [ ] Volatility group: V4ATR, V4BB
- [ ] Price Structure group: V4P, V4CANDLE
- [ ] Market Context group: V4BR, V4RS, V4S, V4LIQ
- [ ] Meta Feature builder
- [ ] Conflict detector

### Phase 3 — R Layer
- [ ] R1 Linear Model
- [ ] R2 Random Forest
- [ ] R3 Gradient Boosting
- [ ] R4 Neural Network
- [ ] R5 Sector Models
- [ ] Ensemble engine

### Phase 4 — X1
- [ ] Decision engine (thiết kế sau)

### Phase 5 — Feedback & Audit
- [ ] Feedback engine (T+1, T+5, T+10)
- [ ] Expert reliability tracking
- [ ] R model reliability tracking

---

## 10. BRAIN STRUCTURE (AI_brain)

```
D:\AI\AI_brain\
├── SYSTEM\
│   ├── AI_STOCK_GLOBAL_ARCHITECTURE.md    ← file này
│   ├── AI_STOCK_BRAIN_PROTOCOL.md
│   ├── AI_STOCK_DB_SCHEMA_MASTER.md
│   ├── AI_STOCK_DATA_PIPELINE_SPEC.md
│   └── KNOWLEDGE\
│       ├── PRICE_ACTION_RULEBOOK.md
│       ├── VOLUME_BEHAVIOR_RULEBOOK.md
│       ├── CANDLESTICK_RULEBOOK.md
│       ├── ICHIMOKU_RULEBOOK.md
│       ├── MARKET_REGIME_RULEBOOK.md
│       └── ... (rulebook từng expert)
├── EXPERTS\
│   ├── EXPERT_LIST.md
│   ├── EXPERT_PROTOCOL.md
│   └── SIGNAL_CODEBOOK.md
├── REPORTS\
│   ├── CURRENT_SYSTEM_STATE.md
│   ├── MODEL_PERFORMANCE.md
│   └── SYSTEM_HEALTH.md
├── SNAPSHOTS\
│   └── SYSTEM_SNAPSHOT.md
├── CLAUDE\
│   ├── CLAUDE_OPERATING_PROTOCOL.md
│   └── SAFE_EDIT_RULES.md
├── SCRIPTS\
│   └── update_brain.py
└── CHANGELOG\
    └── CHANGELOG.md
```

---

## 11. LOCKED DECISIONS

| Quyết định | Giá trị |
|---|---|
| Brain root | D:\AI\AI_brain |
| Engine root | D:\AI\AI_engine |
| Data root | D:\AI\AI_data |
| Universe | 92 symbols (91 stocks + VNINDEX) |
| DB engine | SQLite |
| DB files | market.db, signals.db, models.db, audit.db |
| Expert output | Score theo scale rulebook riêng |
| R Layer output | Score -4 → +4 (thống nhất) |
| R models | R1 Linear, R2 RF, R3 GBM, R4 NN, R5 Sector |
| Ensemble | 5 models độc lập → weighted average |
| V4D/V4H | Build lại từ đầu |

---

*Document này là nền tảng cho toàn bộ AI_STOCK v2.*
*Mọi thay đổi kiến trúc phải cập nhật file này trước khi sửa code.*
