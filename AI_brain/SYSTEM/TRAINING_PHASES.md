# TRAINING PHASES — AI_STOCK

Version: 5.0
Date: 2026-03-16
Source: TRADING_CALENDAR_MASTER.csv
Status: ACTIVE

---

## PHASE DEFINITIONS (by year)

| Phase | Start | End | Trading Days | Role |
|---|---|---|---|---|
| Phase TEST | 2014-03-06 | 2014-07-29 | 100 | TEST |
| Phase 2014 | 2014-07-30 | 2014-12-31 | 109 | TRAIN |
| Phase 2015 | 2015-01-05 | 2015-12-31 | 248 | TRAIN |
| Phase 2016 | 2016-01-04 | 2016-12-30 | 251 | TRAIN |
| Phase 2017 | 2017-01-03 | 2017-12-29 | 250 | FINE-TUNE |
| Phase 2018 | 2018-01-02 | 2018-12-28 | 248 | FINE-TUNE |
| Phase 2019 | 2019-01-02 | 2019-12-31 | 250 | FINE-TUNE |
| Phase 2020 | 2020-01-02 | 2020-12-31 | 252 | FINE-TUNE |
| Phase 2021 | 2021-01-04 | 2021-12-31 | 250 | FINE-TUNE |
| Phase 2022 | 2022-01-04 | 2022-12-30 | 249 | FINE-TUNE |
| Phase 2023 | 2023-01-03 | 2023-12-29 | 249 | FINE-TUNE |
| Phase 2024 | 2024-01-02 | 2024-12-31 | 250 | FINE-TUNE |
| Phase 2025 | 2025-01-02 | 2025-12-31 | 249 | PRODUCTION |
| Phase 2026 | 2026-01-05 | 2026-03-13 | 45 | PRODUCTION |
| **Total** | **2014-03-06** | **2026-03-13** | **3000** | |

---

## GROUPED PHASES

| Group | Years | Trading Days | Role |
|---|---|---|---|
| Phase TEST | 2014 H1 | 100 | Held-out validation |
| Phase 1 NEN | 2014 H2 + 2015 + 2016 | 608 | Initial training |
| Phase 2 TANG TRUONG | 2017 + 2018 + 2019 | 748 | Fine-tune / OOS validation |
| Phase 3 HIEN DAI | 2020 - 2026 | 1544 | Fine-tune to production |

---

## MARKET CONTEXT BY YEAR

| Year | VNINDEX Range | Context |
|---|---|---|
| 2014 | ~560 - 640 | Recovery, sideways |
| 2015 | ~540 - 640 | Sideways, consolidation |
| 2016 | ~560 - 690 | Gradual bull |
| 2017 | ~680 - 990 | Bull acceleration |
| 2018 | ~890 - 1200 | Peak Apr 1200, sharp correction |
| 2019 | ~900 - 1020 | Recovery, range-bound |
| 2020 | ~660 - 1100 | COVID crash Mar, V-recovery |
| 2021 | ~1070 - 1528 | Super bull, peak Jan 2022 |
| 2022 | ~874 - 1528 | Crash Nov 874, margin cascade |
| 2023 | ~1000 - 1260 | Recovery |
| 2024 | ~1170 - 1300 | Consolidation |
| 2025 | ~1200 - 1770 | Bull expansion |
| 2026 | ~1280 - 1350 | Current |

---

## LABEL HORIZONS

| Horizon | Labels | Note |
|---|---|---|
| T+1 | 245,313 | All except last 1 day |
| T+5 | 244,519 | |
| T+10 | 244,015 | |
| T+20 | 243,099 | |
| T+50 | 240,337 | Last ~50 days = NULL |

---

## TRAINING PIPELINE

```
Phase TEST (100 days)
    verify experts + data pipeline

Phase 2014-2016 (TRAIN, 608 days)
    train R0-R5 initial models
    validate with TimeSeriesSplit

Phase 2017-2019 (FINE-TUNE, 748 days)
    expanding window: train on 2014-2016, validate on 2017
    retrain yearly: add 2017 data, validate on 2018, etc.
    OOS evaluation on each year

Phase 2020-2026 (PRODUCTION, 1544 days)
    walk-forward: retrain quarterly/yearly
    live predictions
```

---

## DATA LEAKAGE RULES

- Phase TEST NEVER used for training
- Each year trains on all prior years (expanding window)
- TimeSeriesSplit within each training window
- Never peek at future data
- See: DATA_LEAKAGE_PREVENTION.md

---

*All dates verified from TRADING_CALENDAR_MASTER.csv.*
*Total: 3000 trading days, 14 phases (TEST + 13 years).*
