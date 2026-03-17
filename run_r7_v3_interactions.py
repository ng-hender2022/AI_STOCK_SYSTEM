"""
R7 v3: Retrain with 140 features (8 regime interactions added).
Clean → Recalc Meta → Retrain R7 → OOS evaluation.
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
# STEP 1: Clean R Layer data
# ================================================================
print("=" * 65)
print("STEP 1: Clean R Layer data")
print("=" * 65)
conn = sqlite3.connect(MODELS_DB)
for t in ["r_predictions", "master_summary", "x1_decisions", "symbol_phase_metrics"]:
    try:
        n = conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
        conn.execute(f"DELETE FROM {t}")
        print(f"  {t}: {n} -> 0")
    except:
        print(f"  {t}: (not found)")
conn.commit()
conn.close()

# ================================================================
# STEP 2: Recalculate Meta Layer (interactions only, experts intact)
# ================================================================
print(f"\n{'=' * 65}")
print("STEP 2: Recalculate Meta Layer with regime interactions")
print("=" * 65)

from AI_engine.meta_layer.feature_matrix_writer import FeatureMatrixWriter
FeatureMatrixWriter.ensure_schema(SIGNALS_DB)

conn = sqlite3.connect(MARKET_DB)
symbols = [r[0] for r in conn.execute("SELECT symbol FROM symbols_master ORDER BY symbol").fetchall()]
conn.close()

# Get all dates with expert_signals
conn = sqlite3.connect(SIGNALS_DB)
all_meta_dates = [r[0] for r in conn.execute(
    "SELECT DISTINCT date FROM expert_signals ORDER BY date"
).fetchall()]
conn.close()
print(f"  Dates to recalculate: {len(all_meta_dates)}")

fw = FeatureMatrixWriter(SIGNALS_DB, MARKET_DB)
t2 = time.time()
for i, d in enumerate(all_meta_dates):
    fw.run(d)
    if (i + 1) % 500 == 0:
        elapsed = time.time() - t2
        rate = (i + 1) / elapsed
        remaining = (len(all_meta_dates) - i - 1) / rate if rate > 0 else 0
        print(f"  [{i+1}/{len(all_meta_dates)}] {d} | {elapsed:.0f}s, ~{remaining/60:.0f}min remaining")

print(f"  Meta recalc done: {len(all_meta_dates)} dates in {(time.time()-t2)/60:.1f} min")

# Verify interactions populated
conn = sqlite3.connect(SIGNALS_DB)
sample = conn.execute(
    "SELECT rsi_x_regime, macd_x_regime, volume_x_regime FROM meta_features WHERE date=(SELECT MAX(date) FROM meta_features) LIMIT 3"
).fetchall()
conn.close()
print(f"  Sample interactions (last date): {[(round(r[0],3), round(r[1],3), round(r[2],3)) for r in sample]}")

# ================================================================
# STEP 3: Retrain R7 with 140 features
# ================================================================
print(f"\n{'=' * 65}")
print("STEP 3: Retrain R7 (140 features, monotonic+regime, CPU)")
print("=" * 65)

t3 = time.time()
from AI_engine.r_layer.r7_catboost.model import R7Model, MONOTONIC_CONSTRAINTS
m = R7Model(SIGNALS_DB, MODELS_DB, MARKET_DB)
metrics = m.train("2014-03-06", "2026-03-13", horizon=5)
m.save_model("D:/AI/AI_engine/r_layer/r7_catboost/model.pkl")
print(f"  R7: {metrics}")
print(f"  Time: {time.time()-t3:.1f}s")

# ================================================================
# STEP 4: Rolling OOS evaluation
# ================================================================
print(f"\n{'=' * 65}")
print("STEP 4: Rolling OOS evaluation (R7 only, 2014-2026)")
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

# R7 v2 results (before interactions) for comparison
r7_v2 = {
    "2014": {"signals": 79, "precision": 60.8, "ev": 0.0566, "sharpe": 0.470},
    "2015": {"signals": 45, "precision": 55.6, "ev": 0.0221, "sharpe": 0.336},
    "2016": {"signals": 6, "precision": 66.7, "ev": 0.2201, "sharpe": 1.262},
    "2018": {"signals": 4, "precision": 75.0, "ev": 0.0141, "sharpe": 0.173},
    "2020": {"signals": 479, "precision": 75.6, "ev": 0.0857, "sharpe": 0.661},
    "2021": {"signals": 21, "precision": 28.6, "ev": -0.0152, "sharpe": -0.139},
    "2022": {"signals": 500, "precision": 37.6, "ev": -0.0333, "sharpe": -0.268},
    "2023": {"signals": 21, "precision": 42.9, "ev": -0.0094, "sharpe": -0.130},
    "2024": {"signals": 45, "precision": 88.9, "ev": 0.0663, "sharpe": 1.327},
    "2025": {"signals": 50, "precision": 64.0, "ev": 0.0848, "sharpe": 0.519},
}

phase_results = {}

for pi in range(1, len(phases)):
    test_name, test_start, test_end = phases[pi]
    train_end = phases[pi-1][2]

    m2 = R7Model(SIGNALS_DB, MODELS_DB, MARKET_DB)
    try:
        m2.train("2014-03-06", train_end, horizon=5)
    except:
        continue

    sconn = sqlite3.connect(SIGNALS_DB)
    td = [r[0] for r in sconn.execute(
        "SELECT DISTINCT date FROM meta_features WHERE date>=? AND date<=? ORDER BY date",
        (test_start, test_end),
    ).fetchall()]
    sconn.close()

    if not td:
        continue

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
        "avg_ret": avg_ret, "ev": ev, "sharpe": sharpe,
    }
    print(f"  Phase {test_name}: {stats['total']} signals, prec={precision*100:.1f}%, EV={ev:+.4f}, sharpe={sharpe:.3f}")

# ================================================================
# Comparison: R7 v2 vs v3
# ================================================================
print(f"\n{'=' * 65}")
print("COMPARISON: R7 v2 (no interactions) vs R7 v3 (with interactions)")
print("=" * 65)
print(f"{'Phase':<8} {'v2 Sig':>6} {'v2 Prec':>8} {'v2 EV':>8} {'v2 Sha':>7} | {'v3 Sig':>6} {'v3 Prec':>8} {'v3 EV':>8} {'v3 Sha':>7} | {'Delta EV':>9}")
print("-" * 95)

focus_phases = ["2021", "2022", "2023"]
for pname in sorted(set(list(r7_v2.keys()) + list(phase_results.keys()))):
    v2 = r7_v2.get(pname, {})
    v3 = phase_results.get(pname, {})
    v2s = v2.get("signals", 0)
    v3s = v3.get("signals", 0)
    v2p = v2.get("precision", 0)
    v3p = v3.get("precision", 0)
    v2e = v2.get("ev", 0)
    v3e = v3.get("ev", 0)
    v2sh = v2.get("sharpe", 0)
    v3sh = v3.get("sharpe", 0)
    delta = v3e - v2e
    marker = " <-- FOCUS" if pname in focus_phases else ""
    print(f"{pname:<8} {v2s:>6} {v2p:>7.1f}% {v2e:>+7.4f} {v2sh:>7.3f} | {v3s:>6} {v3p:>7.1f}% {v3e:>+7.4f} {v3sh:>7.3f} | {delta:>+8.4f}{marker}")

# Summary
v3_total = sum(r["signals"] for r in phase_results.values())
v3_ev_pos = sum(1 for r in phase_results.values() if r.get("ev", 0) > 0 and r["signals"] > 0)
v3_ev_neg = sum(1 for r in phase_results.values() if r.get("ev", 0) <= 0 and r["signals"] > 0)
print(f"\nR7 v3: {v3_total} total signals, {v3_ev_pos} phases EV+, {v3_ev_neg} phases EV-")

total = time.time() - t0
print(f"\nTotal: {total:.1f}s ({total/60:.1f} min)")
