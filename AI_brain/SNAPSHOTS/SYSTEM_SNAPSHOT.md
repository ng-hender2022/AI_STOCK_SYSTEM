# SYSTEM SNAPSHOT

Snapshot date: 2026-03-15
Phase: 1 — Foundation

---

## Summary

- Hệ thống AI_STOCK v2 đang được build từ đầu
- Folder structure đã tạo
- Brain documents đang được viết
- Chưa có code, chưa có data

---

## Key Decisions Made

1. Universe: 92 symbols (91 stocks + VNINDEX)
2. DB engine: SQLite (4 files)
3. 17 experts, mỗi expert có rulebook riêng
4. R Layer: 5 models (R1-R5) output -4 → +4
5. Expert output: score theo scale riêng của rulebook
6. Pipeline: vnstock → market.db → experts → signals.db → R layer → models.db → X1

---

## Next Steps

1. Hoàn thành Brain documents (rulebooks cho 17 experts)
2. Initialize 4 SQLite databases
3. Build engine skeleton (base classes)
4. Build V4REG (Market Regime) — expert đầu tiên

---

*Snapshot này capture trạng thái hệ thống tại thời điểm cụ thể.*
