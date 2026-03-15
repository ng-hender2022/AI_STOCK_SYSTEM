# AI_STOCK DATA PIPELINE SPECIFICATION v1

Generated: 2026-03-15
Status: ACTIVE

---

## 1. DATA SOURCE

| Source | API | Data |
|---|---|---|
| vnstock | vnstock Python package | OHLCV daily, intraday, company info |

---

## 2. PIPELINE FLOW

```
[vnstock API]
    ↓ fetch
[Raw Data]
    ↓ validate + clean
[market.db]
    ↓ trigger experts
[17 Experts] → [signals.db]
    ↓ trigger R layer
[R1..R5] → [models.db]
    ↓ trigger X1
[X1 Decision]
    ↓ async (T+1, T+5, T+10)
[Feedback Engine] → [audit.db]
```

---

## 3. DATA FETCH SCHEDULE

### 3.1 Daily Pipeline
- **Khi nào**: Sau market close (15:00 VN time)
- **Làm gì**:
  1. Fetch prices_daily cho 92 symbols
  2. Validate: no missing, no duplicates
  3. Insert vào market.db → prices_daily
  4. Run 17 experts → signals.db
  5. Run R1..R5 → models.db
  6. Run X1 → decision output

### 3.2 Intraday Pipeline (tương lai)
- **Khi nào**: Mỗi 15 phút trong giờ giao dịch
- **Làm gì**: Fetch snapshot, chạy experts, chạy R layer

---

## 4. DATA VALIDATION RULES

### 4.1 prices_daily
- `close > 0`
- `high >= low`
- `high >= open, high >= close`
- `low <= open, low <= close`
- `volume >= 0`
- Không có ngày bị thiếu (trừ ngày nghỉ lễ)
- Không có duplicate (symbol, date)

### 4.2 expert_signals
- `primary_score` nằm trong range của rulebook
- `signal_quality` trong [0, 4]
- Mỗi expert phải output cho TẤT CẢ 92 symbols (trừ khi có lý do)

### 4.3 r_predictions
- Tất cả r*_score nằm trong [-4, +4]
- ensemble_confidence nằm trong [0, 1]
- ensemble_direction trong [-1, 0, +1]

---

## 5. ERROR HANDLING

| Lỗi | Xử lý |
|---|---|
| API timeout | Retry 3 lần, interval 30s |
| Missing data | Log warning, skip symbol, continue |
| Invalid data | Log error, reject row, continue |
| DB write fail | Log critical, halt pipeline |
| Expert crash | Log error, skip expert, continue pipeline |
| R model crash | Log error, use remaining models for ensemble |

---

## 6. LOGGING

Mọi pipeline run phải log:
- Start time, end time
- Số records fetched / processed / inserted
- Errors / warnings
- Expert run status (success/fail per expert)
- R model run status

Log format: `[TIMESTAMP] [LEVEL] [COMPONENT] message`

---

*Document này quy định data pipeline từ fetch đến output.*
*Thay đổi pipeline phải cập nhật spec này.*
