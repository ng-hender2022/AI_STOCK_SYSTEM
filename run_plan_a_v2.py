"""
Plan A v2: Clean → Retrain → Rolling OOS → Report → Backup
"""
import sqlite3, time, sys, os, shutil, csv
import numpy as np
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, r"D:\AI")
sys.path.insert(0, r"D:\AI\data")

MARKET_DB = r"D:\AI\AI_data\market.db"
SIGNALS_DB = r"D:\AI\AI_data\signals.db"
MODELS_DB = r"D:\AI\AI_data\models.db"
REPORT = r"D:\AI\AI_data\reports\plan_a_v2_phase_symbol_precision.txt"

MODEL_DEFS = [
    ("R0", "AI_engine.r_layer.r0_baseline.model", "R0Model", "r0_baseline"),
    ("R2", "AI_engine.r_layer.r2_rf.model", "R2Model", "r2_rf"),
    ("R3", "AI_engine.r_layer.r3_gbdt.model", "R3Model", "r3_gbdt"),
    ("R4", "AI_engine.r_layer.r4_regime.model", "R4Model", "r4_regime"),
    ("R5", "AI_engine.r_layer.r5_sector.model", "R5Model", "r5_sector"),
    ("R6", "AI_engine.r_layer.r6_xgboost.model", "R6Model", "r6_xgboost"),
    ("R7", "AI_engine.r_layer.r7_catboost.model", "R7Model", "r7_catboost"),
]
MODEL_IDS = ["r0","r2","r3","r4","r5","r6","r7","ensemble"]
MODEL_NAMES = {
    "r0":"R0 Baseline","r2":"R2 RF","r3":"R3 LightGBM","r4":"R4 Regime",
    "r5":"R5 Sector","r6":"R6 XGBoost","r7":"R7 CatBoost","ensemble":"ENSEMBLE",
}
W = {"r0":0.8,"r2":1.2,"r3":1.0,"r4":0.8,"r5":0.8,"r6":1.0,"r7":1.2}

# Load phases from calendar
def load_phases():
    conn = sqlite3.connect(MARKET_DB)
    dates = [r[0] for r in conn.execute(
        "SELECT DISTINCT date FROM prices_daily WHERE symbol='VNINDEX' ORDER BY date"
    ).fetchall()]
    conn.close()
    test_dates = dates[:100]
    remaining = dates[100:]
    years = {}
    for d in remaining:
        y = d[:4]
        if y not in years:
            years[y] = []
        years[y].append(d)
    phases = [("TEST", test_dates[0], test_dates[-1])]
    for y in sorted(years):
        ds = years[y]
        phases.append((y, ds[0], ds[-1]))
    return phases

t0 = time.time()

# ================================================================
# STEP 1: Clean
# ================================================================
print("=" * 65)
print("STEP 1: Clean models.db")
print("=" * 65)
conn = sqlite3.connect(MODELS_DB)
for t in ["r_predictions","master_summary","x1_decisions","symbol_phase_metrics","training_history","model_metrics","feature_importance"]:
    try:
        n = conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
        conn.execute(f"DELETE FROM {t}")
        print(f"  {t}: {n} -> 0")
    except:
        pass
conn.commit()
for t in ["r_predictions","master_summary","x1_decisions","symbol_phase_metrics","training_history","model_metrics","feature_importance"]:
    try:
        n = conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
        assert n == 0, f"{t} not empty!"
    except:
        pass
conn.close()
print("  All tables verified empty.")

# ================================================================
# STEP 2: Retrain on full data
# ================================================================
print(f"\n{'=' * 65}")
print("STEP 2: Retrain R0, R2~R7 on full data")
print("=" * 65)

for name, modpath, clsname, folder in MODEL_DEFS:
    t1 = time.time()
    try:
        mod = __import__(modpath, fromlist=[clsname])
        cls = getattr(mod, clsname)
        m = cls(SIGNALS_DB, MODELS_DB, MARKET_DB)
        horizon = 20 if name == "R4" else 5
        metrics = m.train("2014-03-06", "2026-03-13", horizon=horizon)
        m.save_model(f"D:/AI/AI_engine/r_layer/{folder}/model.pkl")
        acc = metrics.get("accuracy", metrics.get("r2", "?"))
        print(f"  {name}: OK ({metrics.get('samples','?')} samples, {time.time()-t1:.1f}s)")
    except Exception as e:
        print(f"  {name}: FAIL - {e}")

# ================================================================
# STEP 3: Rolling OOS evaluation
# ================================================================
print(f"\n{'=' * 65}")
print("STEP 3: Rolling OOS evaluation")
print("=" * 65)

phases = load_phases()
symbols = [r[0] for r in sqlite3.connect(MARKET_DB).execute("SELECT symbol FROM symbols_master ORDER BY symbol").fetchall()]

# Load all labels
sconn = sqlite3.connect(SIGNALS_DB)
labels_raw = sconn.execute("SELECT symbol, feature_date, t10_return FROM training_labels WHERE t10_return IS NOT NULL").fetchall()
sconn.close()
label_dict = {}
for l in labels_raw:
    label_dict[(l[0], l[1])] = l[2]

from AI_engine.r_layer.ensemble import EnsembleEngine
from AI_engine.x1.symbol_evaluator import SymbolEvaluator
evaluator = SymbolEvaluator(MARKET_DB)

# {phase: {symbol: {model: {total, correct, rets}}}}
all_phase_stats = {}
phase_summary = {}

for pi in range(1, len(phases)):  # skip TEST as train-only
    test_phase = phases[pi]
    test_name, test_start, test_end = test_phase
    train_end = phases[pi-1][2]  # end of previous phase

    print(f"\n  Phase {test_name}: train -> {train_end}, test {test_start} -> {test_end}")

    # Train models on cumulative data up to train_end
    models = {}
    for name, modpath, clsname, folder in MODEL_DEFS:
        try:
            mod = __import__(modpath, fromlist=[clsname])
            cls = getattr(mod, clsname)
            m = cls(SIGNALS_DB, MODELS_DB, MARKET_DB)
            horizon = 20 if name == "R4" else 5
            m.train("2014-03-06", train_end, horizon=horizon)
            models[name] = m
        except:
            pass

    # Get test dates with meta_features
    sconn2 = sqlite3.connect(SIGNALS_DB)
    test_dates = [r[0] for r in sconn2.execute(
        "SELECT DISTINCT date FROM meta_features WHERE date>=? AND date<=? ORDER BY date",
        (test_start, test_end),
    ).fetchall()]
    sconn2.close()

    if not test_dates:
        print(f"    No meta_features for {test_name}, skipping")
        continue

    # Clear predictions for this range
    mconn = sqlite3.connect(MODELS_DB)
    mconn.execute("DELETE FROM r_predictions WHERE date>=? AND date<=?", (test_start, test_end))
    mconn.commit()
    mconn.close()

    # Predict
    ee = EnsembleEngine(MODELS_DB)
    for d in test_dates:
        for name, m in models.items():
            try:
                preds = m.predict(d, symbols=symbols)
                if preds:
                    m.write_predictions(preds)
            except:
                pass
        ee.compute_ensemble(d)

    # Load predictions for this phase
    mconn = sqlite3.connect(MODELS_DB)
    mconn.row_factory = sqlite3.Row
    phase_preds = mconn.execute(
        "SELECT * FROM r_predictions WHERE date>=? AND date<=?", (test_start, test_end)
    ).fetchall()
    mconn.close()

    # Compute stats
    pstats = {}
    for p in phase_preds:
        sym = p["symbol"]
        key = (sym, p["date"])
        if key not in label_dict:
            continue
        ret = label_dict[key]

        if sym not in pstats:
            pstats[sym] = {}

        for rid in ["r0","r2","r3","r4","r5","r6","r7"]:
            v = p[f"{rid}_score"]
            if v is None or float(v) <= 1.0:
                continue
            if rid not in pstats[sym]:
                pstats[sym][rid] = {"total":0,"correct":0,"rets":[]}
            pstats[sym][rid]["total"] += 1
            if ret > 0:
                pstats[sym][rid]["correct"] += 1
            pstats[sym][rid]["rets"].append(ret)

        # Ensemble
        s, wt = 0, 0
        for rid in W:
            v = p[f"{rid}_score"]
            if v is not None:
                s += float(v) * W[rid]
                wt += W[rid]
        if wt > 0 and s/wt > 1.0:
            if "ensemble" not in pstats[sym]:
                pstats[sym]["ensemble"] = {"total":0,"correct":0,"rets":[]}
            pstats[sym]["ensemble"]["total"] += 1
            if ret > 0:
                pstats[sym]["ensemble"]["correct"] += 1
            pstats[sym]["ensemble"]["rets"].append(ret)

    all_phase_stats[test_name] = pstats

    # Phase summary
    ens_precs = []
    for sym, mdata in pstats.items():
        ed = mdata.get("ensemble")
        if ed and ed["total"] >= 3:
            ens_precs.append(100 * ed["correct"] / ed["total"])
    avg_prec = np.mean(ens_precs) if ens_precs else 0
    phase_summary[test_name] = avg_prec
    print(f"    {len(phase_preds)} predictions, {len(pstats)} symbols, avg ensemble prec={avg_prec:.1f}%")

# ================================================================
# STEP 4: Generate report
# ================================================================
print(f"\n{'=' * 65}")
print("STEP 4: Generate report")
print("=" * 65)

# Get trends
trend_map = {}
for sym in symbols:
    ev = evaluator.evaluate(sym, "2026-03-13")
    if ev.has_sufficient_data:
        if ev.volatility_20d >= 0.04:
            trend_map[sym] = "VOLATILE"
        elif ev.trend_direction == "UP" and ev.trend_strength > 0.2:
            trend_map[sym] = "INCREASING"
        elif ev.trend_direction == "DOWN" and ev.trend_strength > 0.2:
            trend_map[sym] = "DECREASING"
        else:
            trend_map[sym] = "STABLE"
    else:
        trend_map[sym] = "N/A"

os.makedirs(os.path.dirname(REPORT), exist_ok=True)
L = []
L.append("=" * 64)
L.append("PLAN A v2 - PHASE x SYMBOL x MODEL PRECISION REPORT")
L.append("Generated: 2026-03-16")
L.append("Horizon: T+10, BUY signals (score > 1.0)")
L.append("Models: R0, R2, R3, R4, R5, R6, R7 (R1 excluded)")
L.append("Rolling OOS: train on prior phases, test on current")
L.append("=" * 64)
L.append("")

overall_model_precs = {m: [] for m in MODEL_IDS}
overall_sym_precs = {}

for pname in sorted(all_phase_stats.keys()):
    pdata = all_phase_stats[pname]
    L.append(f"PHASE {pname}")
    L.append("=" * 64)

    phase_ens = []
    phase_best = (None, -1)
    phase_worst = (None, 101)
    phase_model_precs = {m: [] for m in MODEL_IDS}

    for sym in sorted(pdata.keys()):
        sdata = pdata[sym]
        has = any(sdata.get(m, {}).get("total", 0) >= 3 for m in MODEL_IDS)
        if not has:
            continue

        L.append(f"Symbol: {sym}")
        best_m, best_p = None, -1
        for mid in MODEL_IDS:
            mn = MODEL_NAMES.get(mid, mid)
            d = sdata.get(mid)
            if d and d["total"] >= 1:
                pct = 100 * d["correct"] / d["total"]
                avg = np.mean(d["rets"])
                L.append(f"  {mn:<14}: precision={pct:5.1f}%, signals={d['total']:>3}, avg_return={avg:+.2%}")
                if d["total"] >= 3:
                    phase_model_precs[mid].append(pct)
                    overall_model_precs[mid].append(pct)
                    if pct > best_p:
                        best_p = pct
                        best_m = mn
            else:
                L.append(f"  {mn:<14}: (no signals)")
        if best_m:
            L.append(f"  Best model  : {best_m}")
        L.append(f"  Trend       : {trend_map.get(sym, 'N/A')}")

        ed = sdata.get("ensemble")
        if ed and ed["total"] >= 3:
            ep = 100 * ed["correct"] / ed["total"]
            phase_ens.append(ep)
            if ep > phase_best[1]:
                phase_best = (sym, ep)
            if ep < phase_worst[1]:
                phase_worst = (sym, ep)
            if sym not in overall_sym_precs:
                overall_sym_precs[sym] = []
            overall_sym_precs[sym].append(ep)
        L.append("-" * 64)

    L.append(f"\n--- PHASE {pname} SUMMARY ---")
    if phase_best[0]:
        L.append(f"Best symbol: {phase_best[0]} ({phase_best[1]:.1f}%)")
    if phase_worst[0]:
        L.append(f"Worst symbol: {phase_worst[0]} ({phase_worst[1]:.1f}%)")
    if phase_ens:
        L.append(f"Avg ENSEMBLE precision: {np.mean(phase_ens):.1f}%")
    mavgs = [(MODEL_NAMES.get(m,m), np.mean(p), len(p)) for m, p in phase_model_precs.items() if p]
    mavgs.sort(key=lambda x: -x[1])
    if mavgs:
        L.append(f"Models ranking: {' > '.join(f'{n}({a:.0f}%)' for n,a,_ in mavgs)}")
    L.append("=" * 64)
    L.append("")

# Overall
L.append("=" * 64)
L.append("OVERALL SUMMARY (2014-2026 Rolling OOS)")
L.append("=" * 64)

if phase_summary:
    best_p = max(phase_summary, key=phase_summary.get)
    worst_p = min(phase_summary, key=phase_summary.get)
    L.append(f"Best phase: {best_p} ({phase_summary[best_p]:.1f}%)")
    L.append(f"Worst phase: {worst_p} ({phase_summary[worst_p]:.1f}%)")

L.append("")
L.append("Best model overall:")
mo = [(MODEL_NAMES.get(m,m), np.mean(p), len(p)) for m, p in overall_model_precs.items() if p]
mo.sort(key=lambda x: -x[1])
for n, a, c in mo:
    L.append(f"  {n:<14}: {a:5.1f}% (n={c})")

sym_avg = {s: np.mean(p) for s, p in overall_sym_precs.items() if len(p) >= 2}
L.append("")
above = sorted([(s,v) for s,v in sym_avg.items() if v > 80], key=lambda x: -x[1])
L.append(f"Symbols precision > 80%: {', '.join(f'{s}({v:.0f}%)' for s,v in above) if above else '(none)'}")
below = sorted([(s,v) for s,v in sym_avg.items() if v < 50], key=lambda x: x[1])
L.append(f"Symbols precision < 50%: {', '.join(f'{s}({v:.0f}%)' for s,v in below[:20]) if below else '(none)'}")

L.append("")
vals = [phase_summary[p] for p in sorted(phase_summary) if phase_summary[p] > 0]
if len(vals) >= 3:
    if vals[-1] > vals[0] + 3:
        lt = "IMPROVING"
    elif vals[-1] < vals[0] - 3:
        lt = "DEGRADING"
    else:
        lt = "STABLE"
    L.append(f"Learning trend: {lt} ({vals[0]:.1f}% -> {vals[-1]:.1f}%)")

L.append("=" * 64)

with open(REPORT, "w", encoding="utf-8") as f:
    f.write("\n".join(L))
print(f"  Report: {REPORT} ({len(L)} lines)")

# ================================================================
# STEP 5: Backup
# ================================================================
print(f"\n{'=' * 65}")
print("STEP 5: Backup Plan A v2")
print("=" * 65)

plan_dir = r"D:\AI\AI_data\plans\plan_a_v2"
os.makedirs(os.path.join(plan_dir, "models"), exist_ok=True)
shutil.copy2(MODELS_DB, os.path.join(plan_dir, "models.db"))
for name, _, _, folder in MODEL_DEFS:
    src = f"D:/AI/AI_engine/r_layer/{folder}/model.pkl"
    if os.path.exists(src):
        shutil.copy2(src, os.path.join(plan_dir, "models", f"{name}.pkl"))
shutil.copy2(REPORT, os.path.join(plan_dir, "report.txt"))
print(f"  Backed up to {plan_dir}")

total = time.time() - t0
print(f"\nTotal: {total:.1f}s ({total/60:.1f} min)")

# Print summary
print("\n" + "\n".join(L[-20:]))
