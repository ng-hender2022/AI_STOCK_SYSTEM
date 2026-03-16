"""
SELL Signal Failure Analysis - OOS Phase 2 (2017-2019)
"""
import sqlite3, sys, re, os
import numpy as np
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, r"D:\AI")

MARKET_DB = r"D:\AI\AI_data\market.db"
SIGNALS_DB = r"D:\AI\AI_data\signals.db"
MODELS_DB = r"D:\AI\AI_data\models.db"
TEST_START = "2017-01-03"
TEST_END = "2019-12-31"

# Load predictions
mconn = sqlite3.connect(MODELS_DB)
mconn.row_factory = sqlite3.Row
preds = mconn.execute(
    "SELECT * FROM r_predictions WHERE ensemble_score IS NOT NULL AND date>=? AND date<=?",
    (TEST_START, TEST_END),
).fetchall()
mconn.close()

# Load labels
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

# Load sectors
with open(r"D:\AI\AI_brain\SYSTEM\MASTER_UNIVERSE.md", "r", encoding="utf-8") as f:
    text = f.read()
sector_map = {}
for m in re.finditer(r"\| (\w+) \| (.+?) \|", text):
    s, sec = m.group(1), m.group(2).strip()
    if s not in ("Symbol", "Item"):
        sector_map[s] = sec

# Load regime
mkconn = sqlite3.connect(MARKET_DB)
mkconn.row_factory = sqlite3.Row
regimes = {}
for r in mkconn.execute("SELECT date, regime_score FROM market_regime WHERE date>=? AND date<=?", (TEST_START, TEST_END)).fetchall():
    regimes[r["date"]] = float(r["regime_score"]) if r["regime_score"] else 0.0
mkconn.close()

# Build SELL signals
sell_signals = []
for p in preds:
    if p["ensemble_score"] >= -1.0:
        continue
    key = (p["symbol"], p["date"])
    if key not in label_dict:
        continue
    ret_20 = label_dict[key].get(20)
    if ret_20 is None:
        continue

    r_scores = []
    for col in ["r0_score", "r1_score", "r2_score", "r3_score", "r4_score", "r5_score"]:
        v = p[col]
        if v is not None:
            r_scores.append(float(v))
    bearish_count = sum(1 for s in r_scores if s < -0.5)

    sell_signals.append({
        "symbol": p["symbol"], "date": p["date"],
        "score": float(p["ensemble_score"]),
        "ret_1": label_dict[key].get(1), "ret_5": label_dict[key].get(5),
        "ret_10": label_dict[key].get(10), "ret_20": ret_20,
        "ret_50": label_dict[key].get(50),
        "sector": sector_map.get(p["symbol"], "Unknown"),
        "regime": regimes.get(p["date"], 0.0),
        "bearish_count": bearish_count, "total_models": len(r_scores),
    })

print("=" * 70)
print(f"SELL SIGNAL FAILURE ANALYSIS - OOS Phase 2 (2017-2019)")
print(f"Total SELL signals (score < -1.0): {len(sell_signals)}")
print("=" * 70)

correct_20 = sum(1 for s in sell_signals if s["ret_20"] < 0)
print(f"\nOverall T+20: {100*correct_20/len(sell_signals):.1f}% correct ({correct_20}/{len(sell_signals)})")

# 1. BY SECTOR
print(f"\n--- 1. BY SECTOR (T+20) ---")
sectors = {}
for s in sell_signals:
    sec = s["sector"]
    if sec not in sectors:
        sectors[sec] = {"total": 0, "correct": 0, "rets": []}
    sectors[sec]["total"] += 1
    if s["ret_20"] < 0:
        sectors[sec]["correct"] += 1
    sectors[sec]["rets"].append(s["ret_20"])

print(f"  {'Sector':<25} {'N':>5} {'Prec':>7} {'AvgRet':>8}")
print("  " + "-" * 50)
for sec in sorted(sectors, key=lambda x: sectors[x]["total"], reverse=True):
    d = sectors[sec]
    pct = 100 * d["correct"] / d["total"]
    avg = np.mean(d["rets"])
    flag = " WORST" if pct < 35 else (" BEST" if pct > 55 else "")
    print(f"  {sec:<25} {d['total']:>5} {pct:>5.1f}% {avg:>+7.2%}{flag}")

# 2. BY REGIME
print(f"\n--- 2. BY REGIME (T+20) ---")
for regime_label, lo, hi in [("BULL (>1)", 1.0, 99), ("NEUTRAL", -1.0, 1.0), ("BEAR (<-1)", -99, -1.0)]:
    sigs = [s for s in sell_signals if lo < s["regime"] <= hi] if regime_label != "BEAR (<-1)" else [s for s in sell_signals if s["regime"] <= -1.0]
    if regime_label == "BULL (>1)":
        sigs = [s for s in sell_signals if s["regime"] > 1.0]
    elif regime_label == "NEUTRAL":
        sigs = [s for s in sell_signals if -1.0 <= s["regime"] <= 1.0]
    if not sigs:
        print(f"  {regime_label:<20}     0")
        continue
    correct = sum(1 for s in sigs if s["ret_20"] < 0)
    avg = np.mean([s["ret_20"] for s in sigs])
    print(f"  {regime_label:<20} {len(sigs):>5} {100*correct/len(sigs):>5.1f}% {avg:>+7.2%}")

# 3. BY SCORE RANGE
print(f"\n--- 3. BY SCORE RANGE (T+20) ---")
for label, lo, hi in [("-4 to -3", -4.0, -3.0), ("-3 to -2", -3.0, -2.0), ("-2 to -1", -2.0, -1.0)]:
    sigs = [s for s in sell_signals if lo <= s["score"] < hi]
    if not sigs:
        print(f"  {label:<20}     0")
        continue
    correct = sum(1 for s in sigs if s["ret_20"] < 0)
    avg = np.mean([s["ret_20"] for s in sigs])
    print(f"  {label:<20} {len(sigs):>5} {100*correct/len(sigs):>5.1f}% {avg:>+7.2%}")

# 4. BY MODEL CONSENSUS
print(f"\n--- 4. BY MODEL CONSENSUS (T+20) ---")
for label, lo, hi in [("1-2 bearish", 0, 2), ("3-4 bearish", 3, 4), ("5-6 bearish", 5, 6)]:
    sigs = [s for s in sell_signals if lo <= s["bearish_count"] <= hi]
    if not sigs:
        print(f"  {label:<20}     0")
        continue
    correct = sum(1 for s in sigs if s["ret_20"] < 0)
    avg = np.mean([s["ret_20"] for s in sigs])
    print(f"  {label:<20} {len(sigs):>5} {100*correct/len(sigs):>5.1f}% {avg:>+7.2%}")

# 5. CROSS: Bull regime sells
print(f"\n--- 5. SELL in BULL REGIME breakdown ---")
bull_sells = [s for s in sell_signals if s["regime"] > 1.0]
if bull_sells:
    for h in [1, 5, 10, 20, 50]:
        key = f"ret_{h}"
        rets = [s[key] for s in bull_sells if s[key] is not None]
        if rets:
            went_up = sum(1 for r in rets if r > 0)
            print(f"  T+{h:2d}: avg={np.mean(rets):+.2%}, went UP={100*went_up/len(rets):.1f}% (n={len(rets)})")

# RECOMMENDATIONS
print(f"\n{'=' * 70}")
print("RECOMMENDATIONS")
print("=" * 70)
print("1. REGIME FILTER: Block SELL when regime > +1 (or require score < -3)")
print("2. CONSENSUS: Require 4+ models bearish for SELL")
print("3. ASYMMETRIC THRESHOLD: Raise SELL threshold from -1.0 to -2.0")
print("4. SECTOR FILTER: Suppress SELL for sectors with < 40% precision")
print("5. T+1 SELL useless (45.8%=random) - only use SELL for T+5+ horizon")
