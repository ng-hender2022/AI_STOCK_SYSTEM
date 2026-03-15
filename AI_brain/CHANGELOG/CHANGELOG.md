# CHANGELOG — AI_STOCK v2

---

## [2026-03-15] Phase 1 — Foundation Started

### Added
- Folder structure: AI_brain, AI_data, AI_engine
- SYSTEM documents:
  - AI_STOCK_GLOBAL_ARCHITECTURE.md
  - AI_STOCK_BRAIN_PROTOCOL.md
  - AI_STOCK_DB_SCHEMA_MASTER.md
  - AI_STOCK_DATA_PIPELINE_SPEC.md
- EXPERTS documents:
  - EXPERT_LIST.md
  - EXPERT_PROTOCOL.md
  - SIGNAL_CODEBOOK.md
- CLAUDE documents:
  - CLAUDE_OPERATING_PROTOCOL.md
  - SAFE_EDIT_RULES.md
- REPORTS:
  - CURRENT_SYSTEM_STATE.md
  - MODEL_PERFORMANCE.md
  - SYSTEM_HEALTH.md
- SNAPSHOTS:
  - SYSTEM_SNAPSHOT.md
- KNOWLEDGE (17 expert rulebooks):
  - ICHIMOKU_RULEBOOK.md
  - MA_RULEBOOK.md
  - ADX_RULEBOOK.md
  - MACD_RULEBOOK.md
  - RSI_RULEBOOK.md
  - STOCHASTIC_RULEBOOK.md
  - VOLUME_RULEBOOK.md
  - OBV_RULEBOOK.md
  - ATR_RULEBOOK.md
  - BOLLINGER_RULEBOOK.md
  - PRICE_ACTION_RULEBOOK.md
  - CANDLE_RULEBOOK.md
  - BREADTH_RULEBOOK.md
  - RS_RULEBOOK.md
  - REGIME_RULEBOOK.md
  - SECTOR_RULEBOOK.md
  - LIQUIDITY_RULEBOOK.md

### Decisions
- Locked architecture: 92 symbols, SQLite, 17 experts, 5 R models
- Brain = source of truth, code follows Brain

---

*Ghi mỗi thay đổi quan trọng vào đây.*
