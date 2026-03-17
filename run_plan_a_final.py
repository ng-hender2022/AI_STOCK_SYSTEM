"""
Plan A Final: Experts → Retrain → Rolling OOS → EV Report → Backup
Steps 3-7 of the clean retrain pipeline.
"""
import sqlite3, time, sys, os, shutil, json
import numpy as np
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, r"D:\AI")
sys.path.insert(0, r"D:\AI\data")

MARKET_DB = r"D:\AI\AI_data\market.db"
SIGNALS_DB = r"D:\AI\AI_data\signals.db"
MODELS_DB = r"D:\AI\AI_data\models.db"
REPORT = r"D:\AI\AI_data\reports\plan_a_final_phase_symbol_precision.txt"

t0 = time.time()

# ================================================================
# STEP 3: Run 20 experts + Meta Layer on ALL trading days
# ================================================================
print("=" * 65)
print("STEP 3: Run 20 experts + Meta Layer on full 3000 days")
print("=" * 65)

conn = sqlite3.connect(MARKET_DB)
all_dates = [r[0] for r in conn.execute(
    "SELECT DISTINCT date FROM prices_daily WHERE symbol='VNINDEX' ORDER BY date"
).fetchall()]
symbols = [r[0] for r in conn.execute("SELECT symbol FROM symbols_master ORDER BY symbol").fetchall()]
conn.close()
print(f"  Total dates: {len(all_dates)}, Symbols: {len(symbols)}")

# Check which dates already done
conn = sqlite3.connect(SIGNALS_DB)
done_dates = set(r[0] for r in conn.execute("SELECT DISTINCT date FROM meta_features").fetchall())
conn.close()
todo_dates = [d for d in all_dates if d not in done_dates]
print(f"  Already done: {len(done_dates)}, Todo: {len(todo_dates)}")

EXPERT_IMPORTS = [
    ("V4I",    "AI_engine.experts.trend.v4i.expert_writer", "IchimokuExpertWriter"),
    ("V4MA",   "AI_engine.experts.trend.v4ma.expert_writer", "MAExpertWriter"),
    ("V4ADX",  "AI_engine.experts.trend.v4adx.expert_writer", "ADXExpertWriter"),
    ("V4MACD", "AI_engine.experts.momentum.v4macd.expert_writer", "MACDExpertWriter"),
    ("V4RSI",  "AI_engine.experts.momentum.v4rsi.expert_writer", "RSIExpertWriter"),
    ("V4STO",  "AI_engine.experts.momentum.v4sto.expert_writer", "STOExpertWriter"),
    ("V4V",    "AI_engine.experts.volume.v4v.expert_writer", "VolExpertWriter"),
    ("V4OBV",  "AI_engine.experts.volume.v4obv.expert_writer", "OBVExpertWriter"),
    ("V4ATR",  "AI_engine.experts.volatility.v4atr.expert_writer", "ATRExpertWriter"),
    ("V4BB",   "AI_engine.experts.volatility.v4bb.expert_writer", "BBExpertWriter"),
    ("V4P",    "AI_engine.experts.price_structure.v4p.expert_writer", "PAExpertWriter"),
    ("V4CANDLE", "AI_engine.experts.price_structure.v4candle.expert_writer", "CandleExpertWriter"),
    ("V4PIVOT", "AI_engine.experts.price_structure.v4pivot.expert_writer", "PivotExpertWriter"),
    ("V4SR",   "AI_engine.experts.price_structure.v4sr.expert_writer", "SRExpertWriter"),
    ("V4TREND_PATTERN", "AI_engine.experts.price_structure.v4trend_pattern.expert_writer", "TPExpertWriter"),
    ("V4RS",   "AI_engine.experts.market_context.v4rs.expert_writer", "RSExpertWriter"),
    ("V4S",    "AI_engine.experts.market_context.v4s.expert_writer", "SectorExpertWriter"),
    ("V4LIQ",  "AI_engine.experts.market_context.v4liq.expert_writer", "LiqExpertWriter"),
]

from AI_engine.experts.market_context.v4reg.regime_writer import RegimeWriter
from AI_engine.experts.market_context.v4br.expert_writer import BreadthExpertWriter
from AI_engine.meta_layer.feature_matrix_writer import FeatureMatrixWriter

fw = FeatureMatrixWriter(SIGNALS_DB, MARKET_DB)

t3 = time.time()
for i, d in enumerate(todo_dates):
    RegimeWriter(MARKET_DB).run(d)
    for eid, modpath, clsname in EXPERT_IMPORTS:
        try:
            mod = __import__(modpath, fromlist=[clsname])
            cls = getattr(mod, clsname)
            w = cls(MARKET_DB, SIGNALS_DB)
            w.run_all(d, symbols=symbols)
        except Exception:
            pass
    try:
        BreadthExpertWriter(MARKET_DB, SIGNALS_DB).run(d)
    except Exception:
        pass
    fw.run(d)
    if (i + 1) % 100 == 0:
        elapsed = time.time() - t3
        rate = (i + 1) / elapsed
        remaining = (len(todo_dates) - i - 1) / rate if rate > 0 else 0
        print(f"  [{i+1}/{len(todo_dates)}] {d} | {elapsed:.0f}s, ~{remaining/60:.0f}min remaining")

print(f"  Experts done: {len(todo_dates)} dates in {(time.time()-t3)/60:.1f} min")

conn = sqlite3.connect(SIGNALS_DB)
sig_total = conn.execute("SELECT COUNT(*) FROM expert_signals").fetchone()[0]
meta_total = conn.execute("SELECT COUNT(*) FROM meta_features").fetchone()[0]
conn.close()
print(f"  Signals: {sig_total}, Meta features: {meta_total}")

# ================================================================
# STEP 4: Retrain R0, R2~R7
# ================================================================
print(f"\n{'=' * 65}")
print("STEP 4: Retrain R0, R2~R7 on full data (130 features, normalized)")
print("=" * 65)

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

for name, modpath, clsname, folder in MODEL_DEFS:
    t1 = time.time()
    try:
        mod = __import__(modpath, fromlist=[clsname])
        cls = getattr(mod, clsname)
        m = cls(SIGNALS_DB, MODELS_DB, MARKET_DB)
        horizon = 20 if name == "R4" else 5
        metrics = m.train("2014-03-06", "2026-03-13", horizon=horizon)
        m.save_model(f"D:/AI/AI_engine/r_layer/{folder}/model.pkl")
        print(f"  {name}: OK ({metrics.get('samples','?')} samples, {time.time()-t1:.1f}s)")
    except Exception as e:
        print(f"  {name}: FAIL - {e}")

# ================================================================
# STEP 5: Rolling OOS evaluation with EV metrics
# ================================================================
print(f"\n{'=' * 65}")
print("STEP 5: Rolling OOS evaluation (2014-2026) with EV metrics")
print("=" * 65)

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

phases = load_phases()

# Load all labels (T+10 for evaluation)
sconn = sqlite3.connect(SIGNALS_DB)
labels_raw = sconn.execute("SELECT symbol, feature_date, t10_return FROM training_labels WHERE t10_return IS NOT NULL").fetchall()
sconn.close()
label_dict = {}
for l in labels_raw:
    label_dict[(l[0], l[1])] = l[2]

from AI_engine.r_layer.ensemble import EnsembleEngine

# {phase: {symbol: {model: {total, correct, rets}}}}
all_phase_stats = {}
phase_summary = {}

for pi in range(1, len(phases)):
    test_phase = phases[pi]
    test_name, test_start, test_end = test_phase
    train_end = phases[pi-1][2]

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

    # Get test dates
    sconn2 = sqlite3.connect(SIGNALS_DB)
    test_dates = [r[0] for r in sconn2.execute(
        "SELECT DISTINCT date FROM meta_features WHERE date>=? AND date<=? ORDER BY date",
        (test_start, test_end),
    ).fetchall()]
    sconn2.close()

    if not test_dates:
        print(f"    No meta_features for {test_name}, skipping")
        continue

    mconn = sqlite3.connect(MODELS_DB)
    mconn.execute("DELETE FROM r_predictions WHERE date>=? AND date<=?", (test_start, test_end))
    mconn.commit()
    mconn.close()

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

    # Load predictions
    mconn = sqlite3.connect(MODELS_DB)
    mconn.row_factory = sqlite3.Row
    phase_preds = mconn.execute(
        "SELECT * FROM r_predictions WHERE date>=? AND date<=?", (test_start, test_end)
    ).fetchall()
    mconn.close()

    # Compute stats with EV metrics
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

    ens_precs = []
    for sym, mdata in pstats.items():
        ed = mdata.get("ensemble")
        if ed and ed["total"] >= 3:
            ens_precs.append(100 * ed["correct"] / ed["total"])
    avg_prec = np.mean(ens_precs) if ens_precs else 0
    phase_summary[test_name] = avg_prec
    print(f"    {len(phase_preds)} predictions, {len(pstats)} symbols, avg ensemble prec={avg_prec:.1f}%")

# ================================================================
# STEP 6: Generate EV report
# ================================================================
print(f"\n{'=' * 65}")
print("STEP 6: Generate EV report")
print("=" * 65)

os.makedirs(os.path.dirname(REPORT), exist_ok=True)
L = []
L.append("=" * 100)
L.append("PLAN A FINAL - PHASE x SYMBOL x MODEL PRECISION + EV REPORT")
L.append(f"Generated: 2026-03-16")
L.append("Horizon: T+10, BUY signals (score > 1.0)")
L.append("Models: R0, R2, R3, R4, R5, R6, R7 (R1 excluded)")
L.append("Features: 130 (normalized per NORMALIZATION_RULEBOOK)")
L.append("Rolling OOS: train on prior phases, test on current")
L.append("=" * 100)
L.append("")
L.append(f"{'Symbol':<8} {'Model':<14} {'Signals':>7} {'Precision':>9} {'AvgRet':>8} {'AvgWin':>8} {'AvgLoss':>8} {'EV':>8} {'SharpeLike':>10}")
L.append("-" * 100)

overall_model_stats = {m: {"total":0,"correct":0,"rets":[]} for m in MODEL_IDS}

for pname in sorted(all_phase_stats.keys()):
    pdata = all_phase_stats[pname]
    L.append(f"\nPHASE {pname}")
    L.append("=" * 100)

    for sym in sorted(pdata.keys()):
        sdata = pdata[sym]
        has = any(sdata.get(m, {}).get("total", 0) >= 3 for m in MODEL_IDS)
        if not has:
            continue

        for mid in MODEL_IDS:
            mn = MODEL_NAMES.get(mid, mid)
            d = sdata.get(mid)
            if d and d["total"] >= 1:
                pct = 100 * d["correct"] / d["total"]
                rets = np.array(d["rets"])
                avg_ret = float(np.mean(rets))
                wins = rets[rets > 0]
                losses = rets[rets <= 0]
                avg_win = float(np.mean(wins)) if len(wins) > 0 else 0.0
                avg_loss = float(np.mean(losses)) if len(losses) > 0 else 0.0
                precision = d["correct"] / d["total"]
                ev = precision * avg_win + (1 - precision) * avg_loss
                ret_std = float(np.std(rets)) if len(rets) > 1 else 1e-9
                sharpe = avg_ret / ret_std if ret_std > 1e-9 else 0.0

                L.append(f"{sym:<8} {mn:<14} {d['total']:>7} {pct:>8.1f}% {avg_ret:>+7.2%} {avg_win:>+7.2%} {avg_loss:>+7.2%} {ev:>+7.4f} {sharpe:>9.3f}")

                # Accumulate overall
                overall_model_stats[mid]["total"] += d["total"]
                overall_model_stats[mid]["correct"] += d["correct"]
                overall_model_stats[mid]["rets"].extend(d["rets"])

# Overall summary
L.append("")
L.append("=" * 100)
L.append("OVERALL SUMMARY (2014-2026 Rolling OOS)")
L.append("=" * 100)
L.append("")

# Phase summary
L.append("Phase Ensemble Precision:")
for pname in sorted(phase_summary.keys()):
    L.append(f"  {pname}: {phase_summary[pname]:.1f}%")

vals = [phase_summary[p] for p in sorted(phase_summary) if phase_summary[p] > 0]
if len(vals) >= 3:
    if vals[-1] > vals[0] + 3:
        lt = "IMPROVING"
    elif vals[-1] < vals[0] - 3:
        lt = "DEGRADING"
    else:
        lt = "STABLE"
    L.append(f"  Learning trend: {lt} ({vals[0]:.1f}% -> {vals[-1]:.1f}%)")

L.append("")
L.append(f"{'Model':<14} {'Signals':>7} {'Precision':>9} {'AvgRet':>8} {'AvgWin':>8} {'AvgLoss':>8} {'EV':>8} {'SharpeLike':>10}")
L.append("-" * 80)

model_ev_ranking = []
for mid in MODEL_IDS:
    d = overall_model_stats[mid]
    if d["total"] == 0:
        continue
    rets = np.array(d["rets"])
    pct = 100 * d["correct"] / d["total"]
    avg_ret = float(np.mean(rets))
    wins = rets[rets > 0]
    losses = rets[rets <= 0]
    avg_win = float(np.mean(wins)) if len(wins) > 0 else 0.0
    avg_loss = float(np.mean(losses)) if len(losses) > 0 else 0.0
    precision = d["correct"] / d["total"]
    ev = precision * avg_win + (1 - precision) * avg_loss
    ret_std = float(np.std(rets)) if len(rets) > 1 else 1e-9
    sharpe = avg_ret / ret_std if ret_std > 1e-9 else 0.0
    mn = MODEL_NAMES.get(mid, mid)
    L.append(f"{mn:<14} {d['total']:>7} {pct:>8.1f}% {avg_ret:>+7.2%} {avg_win:>+7.2%} {avg_loss:>+7.2%} {ev:>+7.4f} {sharpe:>9.3f}")
    model_ev_ranking.append((mn, ev, sharpe, d["total"]))

L.append("")
model_ev_ranking.sort(key=lambda x: -x[1])
L.append("EV Ranking: " + " > ".join(f"{n}({ev:+.4f})" for n, ev, _, _ in model_ev_ranking))

# Filter check
L.append("")
L.append("EV Filter (min_signals>=20, EV>0, sharpe>0.2):")
for n, ev, sharpe, total in model_ev_ranking:
    passed = total >= 20 and ev > 0 and sharpe > 0.2
    L.append(f"  {n}: {'PASS' if passed else 'FAIL'} (signals={total}, EV={ev:+.4f}, sharpe={sharpe:.3f})")

L.append("")
L.append("=" * 100)

with open(REPORT, "w", encoding="utf-8") as f:
    f.write("\n".join(L))
print(f"  Report: {REPORT} ({len(L)} lines)")

# ================================================================
# STEP 7: Backup to plan_a (overwrite)
# ================================================================
print(f"\n{'=' * 65}")
print("STEP 7: Backup Plan A (overwrite)")
print("=" * 65)

plan_dir = r"D:\AI\AI_data\plans\plan_a"
# Clean and recreate
if os.path.exists(plan_dir):
    shutil.rmtree(plan_dir)
os.makedirs(os.path.join(plan_dir, "models"), exist_ok=True)

# Databases
for db in ["models.db", "signals.db", "market.db", "audit.db"]:
    src = os.path.join(r"D:\AI\AI_data", db)
    if os.path.exists(src):
        shutil.copy2(src, os.path.join(plan_dir, db))
        size = os.path.getsize(src) / (1024*1024)
        print(f"  {db}: {size:.1f} MB")

# Model pkl files
for name, _, _, folder in MODEL_DEFS:
    src = f"D:/AI/AI_engine/r_layer/{folder}/model.pkl"
    if os.path.exists(src):
        shutil.copy2(src, os.path.join(plan_dir, "models", f"{name}.pkl"))

# Brain docs
brain_dst = os.path.join(plan_dir, "brain")
os.makedirs(brain_dst, exist_ok=True)
brain_src = r"D:\AI\AI_brain\SYSTEM"
for f in os.listdir(brain_src):
    fp = os.path.join(brain_src, f)
    if os.path.isfile(fp) and f.endswith(('.md', '.txt')):
        shutil.copy2(fp, os.path.join(brain_dst, f))
knowledge_src = os.path.join(brain_src, "KNOWLEDGE")
if os.path.isdir(knowledge_src):
    shutil.copytree(knowledge_src, os.path.join(brain_dst, "KNOWLEDGE"))

# Engine code
engine_dst = os.path.join(plan_dir, "engine")
engine_src = r"D:\AI\AI_engine"
for subdir in ["experts", "r_layer", "meta_layer", "x1", "scripts"]:
    src_path = os.path.join(engine_src, subdir)
    dst_path = os.path.join(engine_dst, subdir)
    if os.path.isdir(src_path):
        for root, dirs, files in os.walk(src_path):
            rel = os.path.relpath(root, src_path)
            dst_root = os.path.join(dst_path, rel)
            os.makedirs(dst_root, exist_ok=True)
            for fn in files:
                if fn.endswith(('.py', '.yaml', '.md')):
                    shutil.copy2(os.path.join(root, fn), os.path.join(dst_root, fn))

# PLAN_A_SPEC.md
spec = f"""================================================================
PLAN A - OFFICIAL SPECIFICATION
Version: 1.1
Date: 2026-03-16
Status: BASELINE (post feature expansion + normalization)
================================================================

ARCHITECTURE:
- 20 experts, deterministic, rulebook-based
- Feature Matrix: 130 features (19 norms + 85 sub-features + 25 meta + 3 regime)
- Normalization: AI_STOCK_FEATURE_NORMALIZATION_RULEBOOK (8 categories)
- R Layer: R0, R2, R3, R4, R5, R6(GPU), R7(GPU) - R1 excluded
- Weights: R0=0.8, R2=1.2, R3=1.0, R4=0.8, R5=0.8, R6=1.0, R7=1.2

EVALUATION:
- Metrics: precision, avg_return, avg_win, avg_loss, EV, return_std, sharpe_like
- Primary ranking: Expected Value (EV)
- Filter: min_signals>=20, EV>0, sharpe_like>0.2

R4 REGIME FILTER: abs(score)>=3, confidence>=0.70 (hard threshold)
R5 SECTOR FILTER: abs(score)>=3.5, top 10% sector, quality>=3

RESTORE: python D:\\AI\\AI_engine\\scripts\\load_plan.py --plan plan_a
================================================================
"""
with open(os.path.join(plan_dir, "PLAN_A_SPEC.md"), "w", encoding="utf-8") as f:
    f.write(spec)

# Report
shutil.copy2(REPORT, os.path.join(plan_dir, "report.txt"))

total_size = sum(
    os.path.getsize(os.path.join(r, f))
    for r, _, files in os.walk(plan_dir)
    for f in files
)
print(f"  Backed up to {plan_dir} ({total_size/(1024*1024):.0f} MB)")

total = time.time() - t0
print(f"\nTotal: {total:.1f}s ({total/60:.1f} min)")

# Print summary
print("\n" + "\n".join(L[-25:]))
