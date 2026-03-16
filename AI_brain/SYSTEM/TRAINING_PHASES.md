# TRAINING PHASES — AI_STOCK

Version: 3.0
Date: 2026-03-16
Source: TRADING_CALENDAR_MASTER.csv
Status: ACTIVE

---

## PHASE DEFINITIONS

| Phase | Name | Start | End | Trading Days | Role |
|---|---|---|---|---|---|
| Phase TEST | First Validation | 2014-03-06 | 2014-07-29 | 100 | TEST |
| Phase 1 | NEN (Foundation) | 2014-07-30 | 2016-12-30 | 608 | TRAIN |
| Phase 2 | TANG TRUONG (Growth) | 2017-01-03 | 2019-12-31 | 748 | FINE-TUNE |
| Phase 3 | HIEN DAI (Modern) | 2020-01-02 | 2026-03-13 | 1544 | FINE-TUNE → PRODUCTION |
| **Total** | | **2014-03-06** | **2026-03-13** | **3000** | |

---

## PHASE DETAILS

### Phase TEST — First Validation (100 days) — TEST
- Start: 2014-03-06 (first trading day in calendar)
- End: 2014-07-29 (100th trading day)
- Duration: 100 trading days (~5 months)
- Role: **Held-out test set** — verify expert signals and data pipeline before training
- Market context: VNINDEX sideways ~560-590
- NEVER used for training or fine-tuning

### Phase 1 — NEN / Foundation (608 days) — TRAIN
- Start: 2014-07-30 (day after Phase TEST ends)
- End: 2016-12-30 (last trading day of 2016)
- Duration: 608 trading days (~2.4 years)
- Role: **Initial training** — R Layer learns baseline patterns
- Market context: 2014 recovery, 2015 sideways, 2016 gradual bull
- VNINDEX range: ~590 → ~680

### Phase 2 — TANG TRUONG / Growth (748 days) — FINE-TUNE
- Start: 2017-01-03 (first trading day of 2017)
- End: 2019-12-31 (last trading day of 2019)
- Duration: 748 trading days (~3.0 years)
- Role: **Fine-tune** — R Layer adapts to growth/correction cycles
- Market context: 2017 bull acceleration, 2018 peak + correction, 2019 recovery
- VNINDEX range: ~680 → ~960 (peak ~1200 in Apr 2018)

### Phase 3 — HIEN DAI / Modern (1544 days) — FINE-TUNE → PRODUCTION
- Start: 2020-01-02 (first trading day of 2020)
- End: 2026-03-13 (last trading day in calendar)
- Duration: 1544 trading days (~6.2 years)
- Role: **Fine-tune then production** — includes modern market regimes
- Market context: COVID crash 2020, 2020-2021 super bull, 2022 crash, 2023-2026 recovery
- VNINDEX range: ~960 → ~1280 (peak ~1528 in Jan 2022, trough ~874 in Nov 2022)

---

## TRAINING PIPELINE

```
Phase TEST (TEST)
    ↓ verify experts + data pipeline on 100 days
    ↓ sanity check passed:
Phase 1 (TRAIN)
    ↓ train R0-R5 on 608 days
    ↓ validate with TimeSeriesSplit within Phase 1
Phase 2 (FINE-TUNE)
    ↓ fine-tune R0-R5 on Phase 1 + Phase 2 data
    ↓ validate on last 100 days of Phase 2
Phase 3 (FINE-TUNE → PRODUCTION)
    ↓ fine-tune on Phase 1 + 2 + early Phase 3
    ↓ walk-forward: retrain periodically, test on next window
    ↓ production: live predictions
```

---

## DATA LEAKAGE RULES

- Phase TEST data NEVER used for training
- Phase 1 training NEVER sees Phase 2 or Phase 3 data
- Phase 2 fine-tuning NEVER sees Phase 3 data
- Within each phase: use TimeSeriesSplit (chronological only)
- Walk-forward in Phase 3: expanding train window, fixed test window
- See: DATA_LEAKAGE_PREVENTION.md

---

## KEY DATES

| Event | Date | Phase |
|---|---|---|
| Calendar start | 2014-03-06 | Phase TEST start |
| Phase TEST end | 2014-07-29 | 100th trading day |
| Phase 1 start | 2014-07-30 | Day after TEST |
| Phase 1 end | 2016-12-30 | Last trading day 2016 |
| Phase 2 start | 2017-01-03 | First trading day 2017 |
| Phase 2 end | 2019-12-31 | Last trading day 2019 |
| Phase 3 start | 2020-01-02 | First trading day 2020 |
| Calendar end | 2026-03-13 | Phase 3 end |

---

*All dates verified from TRADING_CALENDAR_MASTER.csv.*
*Total: 3000 trading days across 4 phases (100 + 608 + 748 + 1544).*
