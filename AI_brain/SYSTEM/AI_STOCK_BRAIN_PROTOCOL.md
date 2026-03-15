# AI_STOCK BRAIN PROTOCOL v1

Generated: 2026-03-15
Status: ACTIVE

---

## 1. BRAIN LÀ GÌ

Brain là **source of truth** duy nhất của hệ thống AI_STOCK.
Mọi quyết định thiết kế, quy tắc, protocol đều được ghi lại tại đây.
Code PHẢI tuân theo Brain. Nếu code và Brain mâu thuẫn → Brain đúng.

---

## 2. CẤU TRÚC BRAIN

```
AI_brain/
├── SYSTEM/              ← Architecture, protocol, schema, specs
│   └── KNOWLEDGE/       ← Rulebooks cho 17 experts
├── EXPERTS/             ← Expert list, protocol, signal codes
├── REPORTS/             ← System state, performance, health
├── SNAPSHOTS/           ← Point-in-time system snapshots
├── CLAUDE/              ← Claude operating rules
├── SCRIPTS/             ← Brain maintenance scripts
└── CHANGELOG/           ← Change history
```

---

## 3. QUY TẮC ĐỌC/GHI BRAIN

### 3.1 AI PHẢI đọc Brain trước khi:
- Build/sửa bất kỳ expert nào → đọc rulebook tương ứng
- Thay đổi DB schema → đọc DB_SCHEMA_MASTER
- Thay đổi data flow → đọc DATA_PIPELINE_SPEC
- Viết code mới → đọc EXPERT_PROTOCOL + SIGNAL_CODEBOOK

### 3.2 AI PHẢI ghi Brain khi:
- Thêm/sửa expert → cập nhật EXPERT_LIST + rulebook
- Thay đổi architecture → cập nhật GLOBAL_ARCHITECTURE
- Phát hiện issue → ghi vào REPORTS
- Hoàn thành milestone → ghi CHANGELOG

### 3.3 AI KHÔNG ĐƯỢC:
- Sửa code mà không đọc Brain trước
- Thay đổi architecture mà không cập nhật Brain
- Bỏ qua rulebook khi implement expert
- Xóa hoặc ghi đè Brain document mà không hỏi user

---

## 4. DOCUMENT NAMING CONVENTION

| Prefix | Nghĩa |
|---|---|
| AI_STOCK_ | System-level document |
| *_RULEBOOK | Expert rulebook |
| *_PROTOCOL | Operating protocol |
| *_SPEC | Technical specification |
| *_CODEBOOK | Code/signal reference |

---

## 5. VERSION CONTROL

- Mỗi document có `Generated` date ở header
- Thay đổi quan trọng phải ghi CHANGELOG
- Brain documents thuộc git repo D:\AI\

---

## 6. BRAIN-CODE SYNC PROTOCOL

```
1. Đọc Brain document liên quan
2. Viết/sửa code theo Brain
3. Test code
4. Nếu phát hiện Brain sai/thiếu → báo user, chờ approval
5. Cập nhật Brain nếu cần
6. Ghi CHANGELOG
```

Không bao giờ sửa Brain để "fit" code. Luôn sửa code để "fit" Brain.

---

*Document này quy định cách vận hành Brain.*
*Mọi AI session phải tuân thủ protocol này.*
