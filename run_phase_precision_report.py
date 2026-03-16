"""
Phase x Symbol x Model precision report.
OOS BUY >1.0, T+10, phases 2017/2018/2019.
"""
import sqlite3, sys, os
import numpy as np
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, r"D:\AI")

MODELS_DB = r"D:\AI\AI_data\models.db"
SIGNALS_DB = r"D:\AI\AI_data\signals.db"
MARKET_DB = r"D:\AI\AI_data\market.db"
OUTPUT = r"D:\AI\AI_data\reports\plan_a_phase_symbol_precision.txt"
BUY_THRESH = 1.0
HORIZON = 10
MIN_SIGNALS = 3

PHASES = [
    ("2017", "2017-01-03", "2017-12-29"),
    ("2018", "2018-01-02", "2018-12-28"),
    ("2019", "2019-01-02", "2019-12-31"),
]
MODEL_IDS = ["r0","r1","r2","r3","r4","r5","r6","r7","ensemble"]
MODEL_NAMES = {
    "r0":"R0 Baseline","r1":"R1 Linear","r2":"R2 RF","r3":"R3 LightGBM",
    "r4":"R4 Regime","r5":"R5 Sector","r6":"R6 XGBoost","r7":"R7 CatBoost",
    "ensemble":"ENSEMBLE",
}
W8 = {"r0":0.05,"r1":0.10,"r2":0.15,"r3":0.20,"r4":0.10,"r5":0.10,"r6":0.15,"r7":0.15}

# Load data
mconn = sqlite3.connect(MODELS_DB)
mconn.row_factory = sqlite3.Row
all_preds = mconn.execute(
    "SELECT * FROM r_predictions WHERE date>='2017-01-03' AND date<='2019-12-31'"
).fetchall()
mconn.close()

sconn = sqlite3.connect(SIGNALS_DB)
labels_raw = sconn.execute(
    "SELECT symbol, feature_date, t10_return FROM training_labels "
    "WHERE feature_date>='2017-01-03' AND feature_date<='2019-12-31' AND t10_return IS NOT NULL"
).fetchall()
sconn.close()

label_dict = {}
for l in labels_raw:
    label_dict[(l[0], l[1])] = l[2]

# Symbol trend from evaluator
from AI_engine.x1.symbol_evaluator import SymbolEvaluator
evaluator = SymbolEvaluator(MARKET_DB)

# Compute trend per symbol per phase end date
phase_trends = {}
for pname, ps, pe in PHASES:
    mkconn = sqlite3.connect(MARKET_DB)
    last_date = mkconn.execute(
        "SELECT MAX(date) FROM prices_daily WHERE symbol='VNINDEX' AND date<=?", (pe,)
    ).fetchone()[0]
    mkconn.close()
    syms = sorted(set(p["symbol"] for p in all_preds if ps <= p["date"] <= pe))
    for sym in syms:
        ev = evaluator.evaluate(sym, last_date)
        if ev.has_sufficient_data:
            if ev.volatility_20d >= 0.04:
                trend = "VOLATILE"
            elif ev.trend_direction == "UP" and ev.trend_strength > 0.2:
                trend = "INCREASING"
            elif ev.trend_direction == "DOWN" and ev.trend_strength > 0.2:
                trend = "DECREASING"
            else:
                trend = "STABLE"
        else:
            trend = "N/A"
        phase_trends[(pname, sym)] = trend

# Build stats: {phase: {symbol: {model: {total, correct, rets}}}}
phase_stats = {}
for pname, ps, pe in PHASES:
    phase_stats[pname] = {}

for p in all_preds:
    sym, date = p["symbol"], p["date"]
    key = (sym, date)
    if key not in label_dict:
        continue
    ret = label_dict[key]

    for pname, ps, pe in PHASES:
        if not (ps <= date <= pe):
            continue

        if sym not in phase_stats[pname]:
            phase_stats[pname][sym] = {}

        # Individual models
        for rid in ["r0","r1","r2","r3","r4","r5","r6","r7"]:
            v = p[f"{rid}_score"]
            if v is None or float(v) <= BUY_THRESH:
                continue
            if rid not in phase_stats[pname][sym]:
                phase_stats[pname][sym][rid] = {"total":0,"correct":0,"rets":[]}
            phase_stats[pname][sym][rid]["total"] += 1
            if ret > 0:
                phase_stats[pname][sym][rid]["correct"] += 1
            phase_stats[pname][sym][rid]["rets"].append(ret)

        # Ensemble
        s8, w8t = 0, 0
        for rid in W8:
            v = p[f"{rid}_score"]
            if v is not None:
                s8 += float(v) * W8[rid]
                w8t += W8[rid]
        if w8t > 0 and s8/w8t > BUY_THRESH:
            if "ensemble" not in phase_stats[pname][sym]:
                phase_stats[pname][sym]["ensemble"] = {"total":0,"correct":0,"rets":[]}
            phase_stats[pname][sym]["ensemble"]["total"] += 1
            if ret > 0:
                phase_stats[pname][sym]["ensemble"]["correct"] += 1
            phase_stats[pname][sym]["ensemble"]["rets"].append(ret)

# Generate report
os.makedirs(os.path.dirname(OUTPUT), exist_ok=True)
L = []

L.append("=" * 64)
L.append("PLAN A - PHASE x SYMBOL x MODEL PRECISION REPORT")
L.append("Generated: 2026-03-16")
L.append(f"Horizon: T+{HORIZON}, BUY signals (score > {BUY_THRESH})")
L.append(f"Min signals per phase: {MIN_SIGNALS}")
L.append("=" * 64)
L.append("")

overall_phase_precs = {}
overall_model_precs = {m: [] for m in MODEL_IDS}
overall_sym_precs = {}

for pname, ps, pe in PHASES:
    L.append(f"PHASE {pname}")
    L.append("=" * 64)

    pdata = phase_stats[pname]
    phase_ens_precs = []
    phase_best_sym = (None, -1)
    phase_worst_sym = (None, 101)
    phase_model_precs = {m: [] for m in MODEL_IDS}

    for sym in sorted(pdata.keys()):
        sdata = pdata[sym]
        # Check if any model has >= MIN_SIGNALS
        has_data = any(sdata.get(m, {}).get("total", 0) >= MIN_SIGNALS for m in MODEL_IDS)
        if not has_data:
            continue

        L.append(f"Symbol: {sym}")
        best_model = None
        best_pct = -1

        for mid in MODEL_IDS:
            mname = MODEL_NAMES[mid]
            d = sdata.get(mid)
            if d and d["total"] >= 1:
                pct = 100 * d["correct"] / d["total"]
                avg = np.mean(d["rets"])
                L.append(f"  {mname:<14}: precision={pct:5.1f}%, signals={d['total']:>3}, avg_return={avg:+.2%}")
                if d["total"] >= MIN_SIGNALS:
                    phase_model_precs[mid].append(pct)
                    overall_model_precs[mid].append(pct)
                    if pct > best_pct:
                        best_pct = pct
                        best_model = mname
            else:
                L.append(f"  {mname:<14}: (no signals)")

        if best_model:
            L.append(f"  Best model  : {best_model}")

        trend = phase_trends.get((pname, sym), "N/A")
        L.append(f"  Trend       : {trend}")

        # Track ensemble for phase summary
        ens = sdata.get("ensemble")
        if ens and ens["total"] >= MIN_SIGNALS:
            epct = 100 * ens["correct"] / ens["total"]
            phase_ens_precs.append(epct)
            if epct > phase_best_sym[1]:
                phase_best_sym = (sym, epct)
            if epct < phase_worst_sym[1]:
                phase_worst_sym = (sym, epct)
            if sym not in overall_sym_precs:
                overall_sym_precs[sym] = []
            overall_sym_precs[sym].append(epct)

        L.append("-" * 64)

    # Phase summary
    L.append("")
    L.append(f"--- PHASE {pname} SUMMARY ---")
    if phase_best_sym[0]:
        L.append(f"Best symbol: {phase_best_sym[0]} ({phase_best_sym[1]:.1f}%)")
    if phase_worst_sym[0]:
        L.append(f"Worst symbol: {phase_worst_sym[0]} ({phase_worst_sym[1]:.1f}%)")
    if phase_ens_precs:
        L.append(f"Avg ENSEMBLE precision: {np.mean(phase_ens_precs):.1f}%")
        overall_phase_precs[pname] = np.mean(phase_ens_precs)

    # Model ranking
    model_avgs = []
    for mid in MODEL_IDS:
        precs = phase_model_precs[mid]
        if precs:
            model_avgs.append((MODEL_NAMES[mid], np.mean(precs), len(precs)))
    model_avgs.sort(key=lambda x: -x[1])
    if model_avgs:
        ranking = " > ".join(f"{n}({a:.0f}%)" for n, a, _ in model_avgs)
        L.append(f"Models ranking: {ranking}")

    L.append("=" * 64)
    L.append("")

# Overall summary
L.append("=" * 64)
L.append("OVERALL SUMMARY (2017-2019)")
L.append("=" * 64)

if overall_phase_precs:
    best_phase = max(overall_phase_precs, key=overall_phase_precs.get)
    worst_phase = min(overall_phase_precs, key=overall_phase_precs.get)
    L.append(f"Best phase: {best_phase} ({overall_phase_precs[best_phase]:.1f}% avg)")
    L.append(f"Worst phase: {worst_phase} ({overall_phase_precs[worst_phase]:.1f}% avg)")

L.append("")

# Best/worst symbols across all phases
sym_avg = {s: np.mean(p) for s, p in overall_sym_precs.items() if len(p) >= 2}
if sym_avg:
    best_sym = max(sym_avg, key=sym_avg.get)
    L.append(f"Best symbol overall: {best_sym} ({sym_avg[best_sym]:.1f}%)")

L.append("")

# Best model overall
L.append("Best model overall (avg across all symbols x phases):")
model_overall = []
for mid in MODEL_IDS:
    precs = overall_model_precs[mid]
    if precs:
        model_overall.append((MODEL_NAMES[mid], np.mean(precs), len(precs)))
model_overall.sort(key=lambda x: -x[1])
for n, a, c in model_overall:
    L.append(f"  {n:<14}: {a:5.1f}% (n={c})")

L.append("")

above80 = sorted([(s, v) for s, v in sym_avg.items() if v > 80], key=lambda x: -x[1])
if above80:
    L.append(f"Symbols precision > 80%: {', '.join(f'{s}({v:.0f}%)' for s, v in above80)}")
else:
    L.append("Symbols precision > 80%: (none)")

below50 = sorted([(s, v) for s, v in sym_avg.items() if v < 50], key=lambda x: x[1])
if below50:
    L.append(f"Symbols precision < 50% (AVOID): {', '.join(f'{s}({v:.0f}%)' for s, v in below50)}")

L.append("")

# Learning trend
if len(overall_phase_precs) >= 2:
    vals = [overall_phase_precs[p] for p, _, _ in PHASES if p in overall_phase_precs]
    if len(vals) >= 2:
        if vals[-1] > vals[0] + 2:
            lt = "IMPROVING"
        elif vals[-1] < vals[0] - 2:
            lt = "DEGRADING"
        else:
            lt = "STABLE"
        L.append(f"Learning trend: {lt} ({vals[0]:.1f}% -> {vals[-1]:.1f}%)")

L.append("=" * 64)

report = "\n".join(L)
with open(OUTPUT, "w", encoding="utf-8") as f:
    f.write(report)

print(f"Report: {OUTPUT}")
print(f"Lines: {len(L)}")
print()
# Print summary
for line in L[-30:]:
    print(line)
