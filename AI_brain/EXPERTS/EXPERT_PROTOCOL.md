# EXPERT PROTOCOL — AI_STOCK v2

Generated: 2026-03-15
Status: ACTIVE

---

## 1. NGUYÊN TẮC CỐT LÕI

1. **Experts là deterministic engines** — cùng input → cùng output, mọi lúc
2. **Experts KHÔNG học, KHÔNG predict** — chỉ tính toán theo rulebook
3. **Experts KHÔNG biết nhau** — mỗi expert hoạt động độc lập
4. **Experts KHÔNG ra quyết định** — chỉ output score, không output BUY/SELL

---

## 2. INTERFACE CHUẨN

Mỗi expert PHẢI implement interface sau:

```python
class BaseExpert:
    expert_id: str          # V4I, V4RSI, etc.
    expert_name: str        # Human-readable name
    group: str              # TREND, MOMENTUM, VOLUME, etc.
    version: str            # Semantic versioning
    scale_min: float        # Min score (e.g., -4 or 0)
    scale_max: float        # Max score (e.g., +4 or 100)

    def compute(self, symbol: str, date: str, market_data: dict) -> ExpertSignal:
        """
        Tính score cho 1 symbol, 1 ngày.
        Returns ExpertSignal object.
        """
        pass

    def compute_batch(self, symbols: list, date: str, market_data: dict) -> list[ExpertSignal]:
        """
        Tính score cho nhiều symbols cùng lúc.
        Default: loop qua compute(). Expert có thể override để optimize.
        """
        pass

    def validate_output(self, signal: ExpertSignal) -> bool:
        """
        Validate output nằm trong range hợp lệ.
        """
        pass
```

---

## 3. OUTPUT FORMAT (ExpertSignal)

```python
@dataclass
class ExpertSignal:
    symbol: str
    date: str
    snapshot_time: str      # 'EOD' hoặc 'HH:MM'
    expert_id: str
    primary_score: float    # Score chính theo rulebook scale
    secondary_score: float  # Score phụ (optional, default None)
    signal_code: str        # Mã tín hiệu (xem SIGNAL_CODEBOOK)
    signal_quality: int     # 0..4
    metadata: dict          # Extra data (optional)
```

---

## 4. SIGNAL QUALITY SCALE

| Quality | Nghĩa | Mô tả |
|---|---|---|
| 0 | NO_SIGNAL | Không có tín hiệu rõ ràng |
| 1 | WEAK | Tín hiệu yếu, ít tin cậy |
| 2 | MODERATE | Tín hiệu trung bình |
| 3 | STRONG | Tín hiệu mạnh, tin cậy |
| 4 | VERY_STRONG | Tín hiệu rất mạnh, hiếm gặp |

---

## 5. DATA ACCESS RULES

- Experts đọc từ `market.db` ONLY
- Experts ghi vào `signals.db` ONLY
- Experts KHÔNG đọc `signals.db` (không biết output của expert khác)
- Experts KHÔNG đọc `models.db` hay `audit.db`

Exceptions:
- V4RS (Relative Strength) cần VNINDEX data → đọc từ market.db
- V4REG (Regime) output cũng ghi vào market.db → market_regime table

---

## 6. ERROR HANDLING

- Nếu thiếu data → return signal_quality = 0, primary_score = 0
- Nếu data invalid → log warning, return signal_quality = 0
- Expert KHÔNG ĐƯỢC crash pipeline — luôn return valid output hoặc graceful skip

---

## 7. TESTING PROTOCOL

Mỗi expert PHẢI có:
1. **Unit tests**: test từng rule trong rulebook
2. **Known-input tests**: bộ test data cố định → expected output cố định
3. **Boundary tests**: test edge cases (giá = 0, volume = 0, etc.)
4. **Consistency tests**: chạy 2 lần cùng input → cùng output (deterministic)

---

## 8. FILE STRUCTURE (mỗi expert)

```
AI_engine/experts/
├── base_expert.py          ← BaseExpert class
├── expert_signal.py        ← ExpertSignal dataclass
├── v4i_ichimoku.py
├── v4ma_moving_average.py
├── v4adx_trend_strength.py
├── v4macd_macd.py
├── v4rsi_rsi.py
├── v4sto_stochastic.py
├── v4v_volume.py
├── v4obv_obv.py
├── v4atr_atr.py
├── v4bb_bollinger.py
├── v4p_price_action.py
├── v4candle_candlestick.py
├── v4br_breadth.py
├── v4rs_relative_strength.py
├── v4reg_regime.py
├── v4s_sector.py
├── v4liq_liquidity.py
└── __init__.py
```

---

*Document này quy định cách build và vận hành expert.*
*Mọi expert PHẢI tuân thủ protocol này.*
