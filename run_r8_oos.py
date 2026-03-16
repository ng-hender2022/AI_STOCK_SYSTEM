"""
Retrain R0-R7, then OOS analysis comparing 6-model vs 8-model ensemble.
Train: 2014-2016, Test: 2017-2019
"""
import sqlite3, time, sys
import numpy as np
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, r"D:\AI")
sys.path.insert(0, r"D:\AI\data")

MARKET_DB = r"D:\AI\AI_data\market.db"
SIGNALS_DB = r"D:\AI\AI_data\signals.db"
MODELS_DB = r"D:\AI\AI_data\models.db"

TRAIN_START = "2014-03-06"
TRAIN_END = "2016-12-30"
TEST_START = "2017-01-03"
TEST_END = "2019-12-31"

t0 = time.time()

MODEL_DEFS = [
    ("R0", "AI_engine.r_layer.r0_baseline.model", "R0Model", "r0_baseline"),
    ("R1", "AI_engine.r_layer.r1_linear.model", "R1Model", "r1_linear"),
    ("R2", "AI_engine.r_layer.r2_rf.model", "R2Model", "r2_rf"),
    ("R3", "AI_engine.r_layer.r3_gbdt.model", "R3Model", "r3_gbdt"),
    ("R4", "AI_engine.r_layer.r4_regime.model", "R4Model", "r4_regime"),
    ("R5", "AI_engine.r_layer.r5_sector.model", "R5Model", "r5_sector"),
    ("R6", "AI_engine.r_layer.r6_xgboost.model", "R6Model", "r6_xgboost"),
    ("R7", "AI_engine.r_layer.r7_catboost.model", "R7Model", "r7_catboost"),
]

# Step 1: Train R0-R7
print("=" * 65)
print(f"STEP 1: Train R0-R7 on {TRAIN_START} -> {TRAIN_END}")
print("=" * 65)

models = {}
for name, modpath, clsname, folder in MODEL_DEFS:
    try:
        mod = __import__(modpath, fromlist=[clsname])
        cls = getattr(mod, clsname)
        m = cls(SIGNALS_DB, MODELS_DB, MARKET_DB)
        horizon = 20 if name == "R4" else 5
        metrics = m.train(TRAIN_START, TRAIN_END, horizon=horizon)
        models[name] = m
        if "error" in metrics:
            print(f"  {name}: SKIPPED - {metrics['error']}")
        else:
            acc = metrics.get("accuracy", metrics.get("r2", "?"))
            print(f"  {name}: OK ({metrics.get('samples','?')} samples, metric={acc})")
    except Exception as e:
        print(f"  {name}: FAIL - {e}")

print(f"  Time: {time.time()-t0:.1f}s")

# Step 2: Predict on OOS dates
conn = sqlite3.connect(SIGNALS_DB)
test_dates = [r[0] for r in conn.execute(
    "SELECT DISTINCT date FROM meta_features WHERE date>=? AND date<=? ORDER BY date",
    (TEST_START, TEST_END),
).fetchall()]
conn.close()

print(f"\nSTEP 2: Predicting on {len(test_dates)} OOS dates...")

conn2 = sqlite3.connect(MARKET_DB)
symbols = [r[0] for r in conn2.execute("SELECT symbol FROM symbols_master ORDER BY symbol").fetchall()]
conn2.close()

from AI_engine.r_layer.ensemble import EnsembleEngine

for i, d in enumerate(test_dates):
    for name, m in models.items():
        try:
            preds = m.predict(d, symbols=symbols)
            if preds:
                m.write_predictions(preds)
        except:
            pass
    EnsembleEngine(MODELS_DB).compute_ensemble(d)
    if (i+1) % 50 == 0:
        print(f"  [{i+1}/{len(test_dates)}] {d}")

print(f"  Time: {time.time()-t0:.1f}s")

# Step 3: OOS Analysis
print(f"\n{'=' * 65}")
print("STEP 3: OOS BUY Precision — 8-model ensemble")
print(f"Train: {TRAIN_START} -> {TRAIN_END}")
print(f"Test:  {TEST_START} -> {TEST_END}")
print("=" * 65)

mconn = sqlite3.connect(MODELS_DB)
mconn.row_factory = sqlite3.Row
r_preds = mconn.execute(
    "SELECT * FROM r_predictions WHERE ensemble_score IS NOT NULL AND date>=? AND date<=?",
    (TEST_START, TEST_END),
).fetchall()
mconn.close()

sconn = sqlite3.connect(SIGNALS_DB)
labels_raw = sconn.execute(
    "SELECT symbol, feature_date, t1_return, t5_return, t10_return, t20_return, t50_return "
    "FROM training_labels WHERE feature_date>=? AND feature_date<=?",
    (TEST_START, TEST_END),
).fetchall()
sconn.close()

label_dict = {}
for l in labels_raw:
    label_dict[(l[0], l[1])] = {1: l[2], 5: l[3], 10: l[4], 20: l[5], 50: l[6]}

# Build prediction dicts for both 6-model and 8-model
pred_6model = {}
pred_8model = {}

for p in r_preds:
    key = (p["symbol"], p["date"])
    scores_6 = []
    scores_8 = []
    w6 = {"r0": 0.10, "r1": 0.15, "r2": 0.20, "r3": 0.25, "r4": 0.15, "r5": 0.15}
    w8 = {"r0": 0.05, "r1": 0.10, "r2": 0.15, "r3": 0.20, "r4": 0.10, "r5": 0.10, "r6": 0.15, "r7": 0.15}

    for rid in ["r0", "r1", "r2", "r3", "r4", "r5"]:
        v = p[f"{rid}_score"]
        if v is not None:
            scores_6.append((rid, float(v)))
    for rid in ["r0", "r1", "r2", "r3", "r4", "r5", "r6", "r7"]:
        v = p[f"{rid}_score"]
        if v is not None:
            scores_8.append((rid, float(v)))

    if scores_6:
        tw = sum(w6.get(k, 0) for k, _ in scores_6)
        ens6 = sum(v * w6.get(k, 0) for k, v in scores_6) / tw if tw > 0 else 0
        pred_6model[key] = max(-4, min(4, ens6))

    if scores_8:
        tw = sum(w8.get(k, 0) for k, _ in scores_8)
        ens8 = sum(v * w8.get(k, 0) for k, v in scores_8) / tw if tw > 0 else 0
        pred_8model[key] = max(-4, min(4, ens8))

print(f"\nOOS predictions: 6-model={len(pred_6model)}, 8-model={len(pred_8model)}")

thresholds_ret = [0.0, 0.01, 0.02, 0.03, 0.05]
horizons = [1, 5, 10, 20, 50]

for label, pred_dict in [("6-MODEL ENSEMBLE (R0-R5)", pred_6model), ("8-MODEL ENSEMBLE (R0-R7)", pred_8model)]:
    for buy_thresh, blabel in [(1.0, "BUY >1.0"), (2.0, "STRONG BUY >2.0")]:
        print(f"\n  {label} — {blabel}:")
        print(f"  {'Horizon':<10} {'N':>6} {'> 0%':>8} {'> 1%':>8} {'> 2%':>8} {'> 3%':>8} {'> 5%':>8}")
        print("  " + "-" * 55)
        for h in horizons:
            total = 0
            wins = {t: 0 for t in thresholds_ret}
            for key, score in pred_dict.items():
                if score <= buy_thresh:
                    continue
                if key not in label_dict:
                    continue
                ret = label_dict[key].get(h)
                if ret is None:
                    continue
                total += 1
                for t in thresholds_ret:
                    if ret > t:
                        wins[t] += 1
            if total > 0:
                pcts = "  ".join(f"{100*wins[t]/total:5.1f}%" for t in thresholds_ret)
                print(f"  T+{h:<7d} {total:>6} {pcts}")
            else:
                print(f"  T+{h:<7d}      0   (no signals)")

# Compare R6/R7 individual accuracy
print(f"\n{'=' * 65}")
print("INDIVIDUAL MODEL COMPARISON (OOS)")
print("=" * 65)

for rid in ["r0", "r1", "r2", "r3", "r4", "r5", "r6", "r7"]:
    buy_count = 0
    correct_10 = 0
    for p in r_preds:
        v = p[f"{rid}_score"]
        if v is None or float(v) <= 1.0:
            continue
        key = (p["symbol"], p["date"])
        if key not in label_dict:
            continue
        ret = label_dict[key].get(10)
        if ret is None:
            continue
        buy_count += 1
        if ret > 0:
            correct_10 += 1

    pct = f"{100*correct_10/buy_count:.1f}%" if buy_count > 0 else "N/A"
    print(f"  {rid.upper()}: {buy_count:>6} BUY signals (>1.0), T+10 precision: {pct}")

total_time = time.time() - t0
print(f"\nTotal time: {total_time:.1f}s ({total_time/60:.1f} min)")
