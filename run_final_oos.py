"""
FINAL OOS Analysis — Plan A with 8 models (R0-R7)
Train: 2014-03-06 -> 2016-12-30
Test:  2017-01-03 -> 2019-12-31
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

W6 = {"r0": 0.10, "r1": 0.15, "r2": 0.20, "r3": 0.25, "r4": 0.15, "r5": 0.15}
W8 = {"r0": 0.05, "r1": 0.10, "r2": 0.15, "r3": 0.20, "r4": 0.10, "r5": 0.10, "r6": 0.15, "r7": 0.15}

# Step 1: Train on Phase TEST + Phase 1 only
print("=" * 70)
print(f"STEP 1: Train R0-R7 on {TRAIN_START} -> {TRAIN_END}")
print("=" * 70)

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
            print(f"  {name}: SKIP - {metrics['error']}")
        else:
            print(f"  {name}: OK ({metrics.get('samples','?')} samples)")
    except Exception as e:
        print(f"  {name}: FAIL - {e}")

print(f"  Time: {time.time()-t0:.1f}s")

# Step 2: Predict on OOS
conn = sqlite3.connect(SIGNALS_DB)
test_dates = [r[0] for r in conn.execute(
    "SELECT DISTINCT date FROM meta_features WHERE date>=? AND date<=? ORDER BY date",
    (TEST_START, TEST_END),
).fetchall()]
conn.close()

mkconn = sqlite3.connect(MARKET_DB)
symbols = [r[0] for r in mkconn.execute("SELECT symbol FROM symbols_master ORDER BY symbol").fetchall()]
mkconn.close()

print(f"\nSTEP 2: Predicting on {len(test_dates)} OOS dates...")

# Clear old predictions for test range
mconn = sqlite3.connect(MODELS_DB)
mconn.execute("DELETE FROM r_predictions WHERE date>=? AND date<=?", (TEST_START, TEST_END))
mconn.commit()
mconn.close()

from AI_engine.r_layer.ensemble import EnsembleEngine
ee = EnsembleEngine(MODELS_DB)

for i, d in enumerate(test_dates):
    for name, m in models.items():
        try:
            preds = m.predict(d, symbols=symbols)
            if preds:
                m.write_predictions(preds)
        except:
            pass
    ee.compute_ensemble(d)
    if (i+1) % 100 == 0:
        print(f"  [{i+1}/{len(test_dates)}] {d}")

print(f"  Time: {time.time()-t0:.1f}s")

# Step 3: Load predictions + labels
print(f"\n{'=' * 70}")
print("STEP 3: OOS ANALYSIS")
print(f"Train: {TRAIN_START} -> {TRAIN_END}")
print(f"Test:  {TEST_START} -> {TEST_END} (NEVER seen)")
print("=" * 70)

mconn = sqlite3.connect(MODELS_DB)
mconn.row_factory = sqlite3.Row
all_preds = mconn.execute(
    "SELECT * FROM r_predictions WHERE date>=? AND date<=?",
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

# Build ensemble scores (6-model and 8-model)
pred_6 = {}
pred_8 = {}
pred_per_model = {f"r{i}": {} for i in range(8)}

for p in all_preds:
    key = (p["symbol"], p["date"])
    s6, w6t = [], 0
    s8, w8t = [], 0
    for rid in ["r0","r1","r2","r3","r4","r5"]:
        v = p[f"{rid}_score"]
        if v is not None:
            s6.append(float(v) * W6[rid])
            w6t += W6[rid]
    for rid in ["r0","r1","r2","r3","r4","r5","r6","r7"]:
        v = p[f"{rid}_score"]
        if v is not None:
            s8.append(float(v) * W8[rid])
            w8t += W8[rid]
            pred_per_model[rid][key] = float(v)

    if w6t > 0:
        pred_6[key] = max(-4, min(4, sum(s6) / w6t))
    if w8t > 0:
        pred_8[key] = max(-4, min(4, sum(s8) / w8t))

print(f"\nPredictions: 6-model={len(pred_6)}, 8-model={len(pred_8)}")

# Analysis function
def analyze(pred_dict, buy_thresh, label_text):
    thresholds = [0.0, 0.01, 0.02, 0.03, 0.05]
    horizons = [1, 5, 10, 20, 50]
    print(f"\n  {label_text}:")
    print(f"  {'Horizon':<8} {'N':>6} {'> 0%':>7} {'> 1%':>7} {'> 2%':>7} {'> 3%':>7} {'> 5%':>7}")
    print("  " + "-" * 50)
    for h in horizons:
        total = 0
        wins = {t: 0 for t in thresholds}
        for key, score in pred_dict.items():
            if score <= buy_thresh:
                continue
            if key not in label_dict:
                continue
            ret = label_dict[key].get(h)
            if ret is None:
                continue
            total += 1
            for t in thresholds:
                if ret > t:
                    wins[t] += 1
        if total > 0:
            pcts = " ".join(f"{100*wins[t]/total:5.1f}%" for t in thresholds)
            print(f"  T+{h:<5d} {total:>6} {pcts}")
        else:
            print(f"  T+{h:<5d}      0")

# 1. STRONG BUY
print(f"\n{'=' * 70}")
print("1. STRONG BUY (score > 2.0)")
print("=" * 70)
analyze(pred_6, 2.0, "6-MODEL (R0-R5)")
analyze(pred_8, 2.0, "8-MODEL (R0-R7)")

# 2. BUY
print(f"\n{'=' * 70}")
print("2. BUY (score > 1.0)")
print("=" * 70)
analyze(pred_6, 1.0, "6-MODEL (R0-R5)")
analyze(pred_8, 1.0, "8-MODEL (R0-R7)")

# 3. SELL with regime-adaptive filter
print(f"\n{'=' * 70}")
print("3. SELL — Regime-Adaptive Filter")
print("=" * 70)

from AI_engine.x1.decision_engine import _get_sell_params

mkconn2 = sqlite3.connect(MARKET_DB)
mkconn2.row_factory = sqlite3.Row
regimes = {r["date"]: float(r["regime_score"]) if r["regime_score"] else 0.0
           for r in mkconn2.execute("SELECT date, regime_score FROM market_regime").fetchall()}
mkconn2.close()

old_sells = []
new_sells = []
for p in all_preds:
    key = (p["symbol"], p["date"])
    ens = p["ensemble_score"]
    if ens is None:
        continue
    score = float(ens)
    regime = regimes.get(p["date"], 0.0)
    bearish = sum(1 for rid in ["r0_score","r1_score","r2_score","r3_score","r4_score","r5_score","r6_score","r7_score"]
                  if p[rid] is not None and float(p[rid]) < -0.5)

    if score <= -1.0:
        old_sells.append(key)
    sell_thresh, min_agree = _get_sell_params(regime)
    if score <= sell_thresh and bearish >= min_agree:
        new_sells.append(key)

for label, keys in [("OLD SELL (score<-1.0)", old_sells), ("NEW SELL (regime-adaptive)", new_sells)]:
    valid = [k for k in keys if k in label_dict and label_dict[k].get(20) is not None]
    if valid:
        correct = sum(1 for k in valid if label_dict[k][20] < 0)
        avg = np.mean([label_dict[k][20] for k in valid])
        print(f"\n  {label}: {len(keys)} signals, T+20 prec={100*correct/len(valid):.1f}%, avg_ret={avg:+.2%}")
    else:
        print(f"\n  {label}: {len(keys)} signals, no labels matched")

# 4. Summary comparison
print(f"\n{'=' * 70}")
print("4. COMPARISON: 6-MODEL vs 8-MODEL")
print("=" * 70)

for thresh, label in [(2.0, "STRONG BUY >2.0"), (1.0, "BUY >1.0")]:
    for h in [10, 20]:
        for pname, pd in [("6-model", pred_6), ("8-model", pred_8)]:
            total = 0
            correct = 0
            for key, score in pd.items():
                if score <= thresh:
                    continue
                if key not in label_dict:
                    continue
                ret = label_dict[key].get(h)
                if ret is None:
                    continue
                total += 1
                if ret > 0:
                    correct += 1
            pct = f"{100*correct/total:.1f}%" if total > 0 else "N/A"
            print(f"  {label} T+{h}: {pname} = {pct} (n={total})")
    print()

# 5. Top 10 symbols
print(f"{'=' * 70}")
print("5. TOP 10 SYMBOLS — 8-MODEL ENSEMBLE BUY >1.0 T+10")
print("=" * 70)

sym_stats = {}
for key, score in pred_8.items():
    if score <= 1.0:
        continue
    sym = key[0]
    if key not in label_dict:
        continue
    ret = label_dict[key].get(10)
    if ret is None:
        continue
    if sym not in sym_stats:
        sym_stats[sym] = {"total": 0, "correct": 0, "rets": []}
    sym_stats[sym]["total"] += 1
    if ret > 0:
        sym_stats[sym]["correct"] += 1
    sym_stats[sym]["rets"].append(ret)

ranked = sorted(
    [(s, d) for s, d in sym_stats.items() if d["total"] >= 5],
    key=lambda x: x[1]["correct"]/x[1]["total"],
    reverse=True,
)

print(f"\n  {'Symbol':<10} {'N':>5} {'Correct':>8} {'Prec':>7} {'AvgRet':>9}")
print("  " + "-" * 45)
for sym, d in ranked[:10]:
    pct = 100 * d["correct"] / d["total"]
    avg = np.mean(d["rets"])
    print(f"  {sym:<10} {d['total']:>5} {d['correct']:>8} {pct:>5.1f}% {avg:>+8.2%}")

# Random baseline
print(f"\n  RANDOM BASELINE:")
for h in [1, 5, 10, 20, 50]:
    total = sum(1 for k in pred_8 if k in label_dict and label_dict[k].get(h) is not None)
    pos = sum(1 for k in pred_8 if k in label_dict and label_dict[k].get(h) is not None and label_dict[k][h] > 0)
    if total > 0:
        print(f"  T+{h}: {100*pos/total:.1f}% positive (n={total})")

total_time = time.time() - t0
print(f"\nTotal time: {total_time:.1f}s ({total_time/60:.1f} min)")
print("=" * 70)
