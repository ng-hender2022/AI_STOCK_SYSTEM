"""
R7 CatBoost focused retrain + OOS evaluation.
Monotonic constraints + regime-aware + prob_up >= 0.72 threshold.
"""
import sqlite3, time, sys, os
import numpy as np
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, r"D:\AI")
sys.path.insert(0, r"D:\AI\data")

MARKET_DB = r"D:\AI\AI_data\market.db"
SIGNALS_DB = r"D:\AI\AI_data\signals.db"
MODELS_DB = r"D:\AI\AI_data\models.db"

t0 = time.time()

# ================================================================
# STEP 1: Save R7 before stats for comparison
# ================================================================
print("=" * 65)
print("STEP 1: R7 Before stats")
print("=" * 65)
conn = sqlite3.connect(MODELS_DB)
r7_before = conn.execute(
    "SELECT COUNT(*) FROM r_predictions WHERE r7_score IS NOT NULL AND r7_score > 1.0"
).fetchone()[0]
r7_total = conn.execute(
    "SELECT COUNT(*) FROM r_predictions WHERE r7_score IS NOT NULL"
).fetchone()[0]
print(f"  R7 before: {r7_total} total predictions, {r7_before} BUY signals (score>1.0)")
conn.close()

# ================================================================
# STEP 2: Clean R7 data only
# ================================================================
print(f"\n{'=' * 65}")
print("STEP 2: Clean R7 data")
print("=" * 65)
conn = sqlite3.connect(MODELS_DB)
# Set R7 scores to NULL (keep other model scores intact)
conn.execute("UPDATE r_predictions SET r7_score = NULL")
n_ms = conn.execute("SELECT COUNT(*) FROM master_summary").fetchone()[0]
n_x1 = conn.execute("SELECT COUNT(*) FROM x1_decisions").fetchone()[0]
conn.execute("DELETE FROM master_summary")
conn.execute("DELETE FROM x1_decisions")
# Clean R7 training history
conn.execute("DELETE FROM training_history WHERE model_id='R7'")
conn.commit()
conn.close()
print(f"  R7 scores nulled, master_summary: {n_ms}->0, x1_decisions: {n_x1}->0")

# ================================================================
# STEP 3: Retrain R7 on full data
# ================================================================
print(f"\n{'=' * 65}")
print("STEP 3: Retrain R7 (monotonic + regime-aware + GPU)")
print("=" * 65)
t1 = time.time()
from AI_engine.r_layer.r7_catboost.model import R7Model, MONOTONIC_CONSTRAINTS
m = R7Model(SIGNALS_DB, MODELS_DB, MARKET_DB)
metrics = m.train("2014-03-06", "2026-03-13", horizon=5)
m.save_model("D:/AI/AI_engine/r_layer/r7_catboost/model.pkl")
print(f"  R7: {metrics}")
print(f"  Monotonic constraints: {sum(1 for v in MONOTONIC_CONSTRAINTS.values() if v != 0)}")
print(f"  Time: {time.time()-t1:.1f}s")

# ================================================================
# STEP 4: Predict on all dates and count signals
# ================================================================
print(f"\n{'=' * 65}")
print("STEP 4: Predict on all dates + count signals")
print("=" * 65)

conn = sqlite3.connect(MARKET_DB)
all_dates = [r[0] for r in conn.execute(
    "SELECT DISTINCT date FROM prices_daily WHERE symbol='VNINDEX' ORDER BY date"
).fetchall()]
symbols = [r[0] for r in conn.execute("SELECT symbol FROM symbols_master ORDER BY symbol").fetchall()]
conn.close()

# Get dates with meta_features
sconn = sqlite3.connect(SIGNALS_DB)
meta_dates = set(r[0] for r in sconn.execute("SELECT DISTINCT date FROM meta_features").fetchall())
sconn.close()

predict_dates = [d for d in all_dates if d in meta_dates]
print(f"  Predicting on {len(predict_dates)} dates...")

t2 = time.time()
total_signals = 0
buy_signals = 0
for i, d in enumerate(predict_dates):
    preds = m.predict(d, symbols=symbols)
    if preds:
        m.write_predictions(preds)
        for p in preds:
            if p["score"] != 0:
                total_signals += 1
            if p["score"] > 1.0:
                buy_signals += 1
    if (i + 1) % 500 == 0:
        print(f"  [{i+1}/{len(predict_dates)}] signals so far: {total_signals} total, {buy_signals} BUY")

print(f"  Prediction done: {time.time()-t2:.1f}s")
print(f"  Total non-zero signals: {total_signals}")
print(f"  BUY signals (score > 1.0): {buy_signals}")
print(f"  Target was ~1000, {'OK' if 500 < buy_signals < 2000 else 'NEEDS ADJUSTMENT'}")

# ================================================================
# STEP 5: Rolling OOS evaluation R7 only
# ================================================================
print(f"\n{'=' * 65}")
print("STEP 5: Rolling OOS evaluation (R7 only)")
print("=" * 65)

# Load labels
sconn = sqlite3.connect(SIGNALS_DB)
labels_raw = sconn.execute(
    "SELECT symbol, feature_date, t10_return FROM training_labels WHERE t10_return IS NOT NULL"
).fetchall()
sconn.close()
label_dict = {(l[0], l[1]): l[2] for l in labels_raw}

# Load phases
conn = sqlite3.connect(MARKET_DB)
dates = [r[0] for r in conn.execute(
    "SELECT DISTINCT date FROM prices_daily WHERE symbol='VNINDEX' ORDER BY date"
).fetchall()]
conn.close()
test_dates_list = dates[:100]
remaining = dates[100:]
years = {}
for d in remaining:
    y = d[:4]
    if y not in years:
        years[y] = []
    years[y].append(d)
phases = [("TEST", test_dates_list[0], test_dates_list[-1])]
for y in sorted(years):
    ds = years[y]
    phases.append((y, ds[0], ds[-1]))

phase_results = {}

for pi in range(1, len(phases)):
    test_name, test_start, test_end = phases[pi]
    train_end = phases[pi-1][2]

    # Train R7 on cumulative data
    m2 = R7Model(SIGNALS_DB, MODELS_DB, MARKET_DB)
    try:
        m2.train("2014-03-06", train_end, horizon=5)
    except:
        continue

    # Get test dates
    sconn = sqlite3.connect(SIGNALS_DB)
    td = [r[0] for r in sconn.execute(
        "SELECT DISTINCT date FROM meta_features WHERE date>=? AND date<=? ORDER BY date",
        (test_start, test_end),
    ).fetchall()]
    sconn.close()

    if not td:
        continue

    # Predict
    stats = {"total": 0, "correct": 0, "rets": []}
    for d in td:
        preds = m2.predict(d, symbols=symbols)
        for p in preds:
            if p["score"] <= 1.0:
                continue
            key = (p["symbol"], d)
            if key not in label_dict:
                continue
            ret = label_dict[key]
            stats["total"] += 1
            if ret > 0:
                stats["correct"] += 1
            stats["rets"].append(ret)

    if stats["total"] == 0:
        phase_results[test_name] = {"signals": 0, "precision": 0, "ev": 0, "sharpe": 0}
        print(f"  Phase {test_name}: 0 signals")
        continue

    rets = np.array(stats["rets"])
    precision = stats["correct"] / stats["total"]
    avg_ret = float(np.mean(rets))
    wins = rets[rets > 0]
    losses = rets[rets <= 0]
    avg_win = float(np.mean(wins)) if len(wins) > 0 else 0.0
    avg_loss = float(np.mean(losses)) if len(losses) > 0 else 0.0
    ev = precision * avg_win + (1 - precision) * avg_loss
    ret_std = float(np.std(rets)) if len(rets) > 1 else 1e-9
    sharpe = avg_ret / ret_std if ret_std > 1e-9 else 0.0

    phase_results[test_name] = {
        "signals": stats["total"], "precision": round(precision * 100, 1),
        "avg_ret": avg_ret, "avg_win": avg_win, "avg_loss": avg_loss,
        "ev": ev, "sharpe": sharpe,
    }
    print(f"  Phase {test_name}: {stats['total']} signals, prec={precision*100:.1f}%, EV={ev:+.4f}, sharpe={sharpe:.3f}")

# ================================================================
# STEP 6: Summary comparison
# ================================================================
print(f"\n{'=' * 65}")
print("STEP 6: R7 Before vs After Comparison")
print("=" * 65)

print(f"\n  R7 BEFORE: {r7_before} BUY signals")
print(f"  R7 AFTER:  {buy_signals} BUY signals")
print(f"  Reduction: {r7_before - buy_signals} signals ({100*(1-buy_signals/max(1,r7_before)):.0f}% fewer)")

# Overall OOS stats
all_signals = sum(r["signals"] for r in phase_results.values())
all_rets = []
all_correct = 0
for r in phase_results.values():
    if r["signals"] > 0:
        all_correct += int(r["precision"] / 100 * r["signals"])
        # reconstruct rets from stats
        pass

print(f"\n  Rolling OOS by phase:")
print(f"  {'Phase':<8} {'Signals':>7} {'Precision':>9} {'AvgRet':>8} {'EV':>8} {'Sharpe':>8}")
print(f"  {'-'*52}")
for pname in sorted(phase_results.keys()):
    r = phase_results[pname]
    if r["signals"] > 0:
        print(f"  {pname:<8} {r['signals']:>7} {r['precision']:>8.1f}% {r['avg_ret']:>+7.2%} {r['ev']:>+7.4f} {r['sharpe']:>7.3f}")
    else:
        print(f"  {pname:<8} {0:>7} {'---':>9} {'---':>8} {'---':>8} {'---':>8}")

total = time.time() - t0
print(f"\nTotal: {total:.1f}s ({total/60:.1f} min)")
