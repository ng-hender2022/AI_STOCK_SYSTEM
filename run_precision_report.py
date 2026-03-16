"""
Generate detailed per-symbol per-model precision report.
OOS BUY signals (score > 1.0), T+10, 2017-2019.
"""
import sqlite3, sys, os
import numpy as np
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, r"D:\AI")

MODELS_DB = r"D:\AI\AI_data\models.db"
SIGNALS_DB = r"D:\AI\AI_data\signals.db"
TEST_START = "2017-01-03"
TEST_END = "2019-12-31"
BUY_THRESH = 1.0
HORIZON = 10
OUTPUT = r"D:\AI\AI_data\reports\plan_a_symbol_precision.txt"

MODEL_NAMES = {
    "r0": "R0 Baseline",
    "r1": "R1 Linear",
    "r2": "R2 RF",
    "r3": "R3 LightGBM",
    "r4": "R4 Regime",
    "r5": "R5 Sector",
    "r6": "R6 XGBoost",
    "r7": "R7 CatBoost",
    "ensemble": "ENSEMBLE",
}
MODEL_IDS = ["r0","r1","r2","r3","r4","r5","r6","r7","ensemble"]

# Load predictions
mconn = sqlite3.connect(MODELS_DB)
mconn.row_factory = sqlite3.Row
all_preds = mconn.execute(
    "SELECT * FROM r_predictions WHERE date>=? AND date<=?",
    (TEST_START, TEST_END),
).fetchall()
mconn.close()

# Load labels
sconn = sqlite3.connect(SIGNALS_DB)
labels_raw = sconn.execute(
    "SELECT symbol, feature_date, t10_return FROM training_labels "
    "WHERE feature_date>=? AND feature_date<=? AND t10_return IS NOT NULL",
    (TEST_START, TEST_END),
).fetchall()
sconn.close()

label_dict = {}
for l in labels_raw:
    label_dict[(l[0], l[1])] = l[2]

# Ensemble weights
W8 = {"r0":0.05,"r1":0.10,"r2":0.15,"r3":0.20,"r4":0.10,"r5":0.10,"r6":0.15,"r7":0.15}

# Build per-symbol per-model stats
# {symbol: {model_id: {"total":N, "correct":N, "rets":[]}}}
stats = {}
symbols_seen = set()

for p in all_preds:
    sym = p["symbol"]
    date = p["date"]
    key = (sym, date)
    symbols_seen.add(sym)

    if key not in label_dict:
        continue
    ret = label_dict[key]

    # Per individual model
    for rid in ["r0","r1","r2","r3","r4","r5","r6","r7"]:
        v = p[f"{rid}_score"]
        if v is None or float(v) <= BUY_THRESH:
            continue
        if sym not in stats:
            stats[sym] = {}
        if rid not in stats[sym]:
            stats[sym][rid] = {"total": 0, "correct": 0, "rets": []}
        stats[sym][rid]["total"] += 1
        if ret > 0:
            stats[sym][rid]["correct"] += 1
        stats[sym][rid]["rets"].append(ret)

    # Ensemble
    s8, w8t = 0, 0
    for rid in ["r0","r1","r2","r3","r4","r5","r6","r7"]:
        v = p[f"{rid}_score"]
        if v is not None:
            s8 += float(v) * W8[rid]
            w8t += W8[rid]
    if w8t > 0:
        ens = s8 / w8t
        if ens > BUY_THRESH:
            if sym not in stats:
                stats[sym] = {}
            if "ensemble" not in stats[sym]:
                stats[sym]["ensemble"] = {"total": 0, "correct": 0, "rets": []}
            stats[sym]["ensemble"]["total"] += 1
            if ret > 0:
                stats[sym]["ensemble"]["correct"] += 1
            stats[sym]["ensemble"]["rets"].append(ret)

# Generate report
os.makedirs(os.path.dirname(OUTPUT), exist_ok=True)
lines = []

lines.append("=" * 64)
lines.append("PLAN A - SYMBOL PRECISION REPORT")
lines.append("Generated: 2026-03-16")
lines.append(f"OOS Period: {TEST_START} -> {TEST_END}")
lines.append(f"Signal: BUY (score > {BUY_THRESH}), Horizon: T+{HORIZON}")
lines.append("=" * 64)
lines.append("")

# Track for summary
all_model_precs = {m: [] for m in MODEL_IDS}
symbols_above_80 = []
symbols_below_50 = []
best_overall_sym = None
best_overall_pct = 0

for sym in sorted(symbols_seen):
    lines.append(f"Symbol: {sym}")
    sym_data = stats.get(sym, {})
    best_model = None
    best_pct = -1

    for mid in MODEL_IDS:
        mname = MODEL_NAMES[mid]
        d = sym_data.get(mid)
        if d and d["total"] >= 1:
            pct = 100 * d["correct"] / d["total"]
            avg = np.mean(d["rets"])
            lines.append(f"  {mname:<14}: precision={pct:5.1f}%, signals={d['total']:>3}, avg_return={avg:+.2%}")
            if d["total"] >= 3:
                all_model_precs[mid].append(pct)
            if pct > best_pct and d["total"] >= 3:
                best_pct = pct
                best_model = mname
        else:
            lines.append(f"  {mname:<14}: (no signals)")

    if best_model:
        lines.append(f"  Best model  : {best_model}")

    # Track ensemble for summary
    ens = sym_data.get("ensemble")
    if ens and ens["total"] >= 5:
        ens_pct = 100 * ens["correct"] / ens["total"]
        if ens_pct > 80:
            symbols_above_80.append((sym, ens_pct, ens["total"]))
        if ens_pct < 50:
            symbols_below_50.append((sym, ens_pct, ens["total"]))
        if ens_pct > best_overall_pct:
            best_overall_pct = ens_pct
            best_overall_sym = sym

    lines.append("-" * 64)

# Summary
lines.append("")
lines.append("=" * 64)
lines.append("SUMMARY")
lines.append("=" * 64)

if best_overall_sym:
    lines.append(f"Best symbol overall: {best_overall_sym} ({best_overall_pct:.1f}%)")

lines.append("")
lines.append("Best model overall (avg precision across symbols with >=3 signals):")
for mid in MODEL_IDS:
    precs = all_model_precs[mid]
    if precs:
        avg = np.mean(precs)
        lines.append(f"  {MODEL_NAMES[mid]:<14}: {avg:5.1f}% avg (n={len(precs)} symbols)")
    else:
        lines.append(f"  {MODEL_NAMES[mid]:<14}: (no data)")

lines.append("")
if symbols_above_80:
    syms_str = ", ".join(f"{s}({p:.0f}%,n={n})" for s, p, n in sorted(symbols_above_80, key=lambda x: -x[1]))
    lines.append(f"Symbols with ENSEMBLE precision > 80% (>=5 signals):")
    lines.append(f"  {syms_str}")
else:
    lines.append("Symbols with ENSEMBLE precision > 80%: (none with >=5 signals)")

lines.append("")
if symbols_below_50:
    syms_str = ", ".join(f"{s}({p:.0f}%,n={n})" for s, p, n in sorted(symbols_below_50, key=lambda x: x[1]))
    lines.append(f"Symbols with ENSEMBLE precision < 50% (consider AVOID):")
    lines.append(f"  {syms_str}")
else:
    lines.append("Symbols with ENSEMBLE precision < 50%: (none)")

lines.append("")
lines.append("=" * 64)

report = "\n".join(lines)

with open(OUTPUT, "w", encoding="utf-8") as f:
    f.write(report)

print(f"Report written to {OUTPUT}")
print(f"Lines: {len(lines)}")
print()

# Print summary to console too
for line in lines[-25:]:
    print(line)
