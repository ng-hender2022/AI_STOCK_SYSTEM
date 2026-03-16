# TRAINING PHASES — AI_STOCK

Version: 1.0
Date: 2026-03-16
Source: TRADING_CALENDAR_MASTER.csv
Status: ACTIVE

---

## PHASE DEFINITIONS

| Phase | Start | End | Trading Days | Purpose |
|---|---|---|---|---|
| Phase 1 | 2014-03-06 | 2016-12-30 | 708 | Initial training / baseline |
| Phase 2 | 2017-01-03 | 2019-12-31 | 748 | Validation / walk-forward |
| Phase 3 | 2020-01-02 | 2026-03-13 | 1544 | Out-of-sample / live period |
| **Total** | **2014-03-06** | **2026-03-13** | **3000** | |

---

## PHASE DETAILS

### Phase 1 — Initial Training (708 days)
- Start: 2014-03-06 (first trading day in calendar)
- End: 2016-12-30 (last trading day of 2016)
- Duration: 708 trading days (~2.8 years)
- Market context: Post-2012 recovery, sideways-to-bull transition

### Phase 2 — Validation (748 days)
- Start: 2017-01-03 (first trading day of 2017)
- End: 2019-12-31 (last trading day of 2019)
- Duration: 748 trading days (~3.0 years)
- Market context: 2017-2018 bull run, 2018 correction, 2019 recovery

### Phase 3 — Out-of-Sample (1544 days)
- Start: 2020-01-02 (first trading day of 2020)
- End: 2026-03-13 (last trading day in calendar)
- Duration: 1544 trading days (~6.2 years)
- Market context: COVID crash 2020, 2020-2021 bull, 2022 crash, 2023-2026 recovery

---

## DATA LEAKAGE RULE

- Phase 1 data NEVER used as validation for Phase 1 training
- Phase 2 data NEVER seen during Phase 1 training
- Phase 3 data NEVER seen during Phase 1 or Phase 2 training
- R Layer must use TimeSeriesSplit within each phase
- See: DATA_LEAKAGE_PREVENTION.md

---

## USAGE

### For R Layer Training
```
Train on Phase 1 → Validate on Phase 2 → Test on Phase 3
```

### For Walk-Forward
```
Expanding window within Phase 1+2, test on rolling Phase 3 windows
```

---

*Dates are exact trading days from TRADING_CALENDAR_MASTER.csv.*
*Total: 3000 trading days across 3 phases.*
