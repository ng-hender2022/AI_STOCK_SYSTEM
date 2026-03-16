"""
Symbol-level evaluation per R model per phase (year).
Computes per-symbol precision for each R model.
"""
import sqlite3, sys, time
import numpy as np
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, r"D:\AI")
sys.path.insert(0, r"D:\AI\data")

MARKET_DB = r"D:\AI\AI_data\market.db"
SIGNALS_DB = r"D:\AI\AI_data\signals.db"
MODELS_DB = r"D:\AI\AI_data\models.db"

t0 = time.time()

# ================================================================
# 1. Create symbol_phase_metrics table
# ================================================================
conn = sqlite3.connect(MODELS_DB)
conn.execute("""
    CREATE TABLE IF NOT EXISTS symbol_phase_metrics (
        symbol          TEXT NOT NULL,
        phase           TEXT NOT NULL,
        model_id        TEXT NOT NULL,
        buy_signals     INTEGER,
        correct_t10     INTEGER,
        precision_t10   REAL,
        avg_return_t10  REAL,
        trend_20d       TEXT,
        trend_slope     REAL,
        volatility_20d  REAL,
        route           TEXT,
        PRIMARY KEY (symbol, phase, model_id)
    )
""")
conn.execute("DELETE FROM symbol_phase_metrics")
conn.commit()
conn.close()

# ================================================================
# 2. Load all data
# ================================================================
print("Loading data...")

# Predictions
mconn = sqlite3.connect(MODELS_DB)
mconn.row_factory = sqlite3.Row
all_preds = mconn.execute("""
    SELECT symbol, date, r0_score, r1_score, r2_score, r3_score,
           r4_score, r5_score, r6_score, r7_score, ensemble_score
    FROM r_predictions WHERE ensemble_score IS NOT NULL
""").fetchall()
mconn.close()

# Labels
sconn = sqlite3.connect(SIGNALS_DB)
labels_raw = sconn.execute("""
    SELECT symbol, feature_date, t10_return
    FROM training_labels WHERE t10_return IS NOT NULL
""").fetchall()
sconn.close()

label_dict = {}
for l in labels_raw:
    label_dict[(l[0], l[1])] = l[2]

# Symbol evaluator for trend
from AI_engine.x1.symbol_evaluator import SymbolEvaluator
evaluator = SymbolEvaluator(MARKET_DB)

# Get symbols
mkconn = sqlite3.connect(MARKET_DB)
symbols = [r[0] for r in mkconn.execute(
    "SELECT symbol FROM symbols_master WHERE is_tradable=1 ORDER BY symbol"
).fetchall()]
mkconn.close()

# ================================================================
# 3. Evaluate trend for each symbol (latest date)
# ================================================================
print(f"Evaluating trends for {len(symbols)} symbols...")
latest_date = max(p["date"] for p in all_preds)
trend_map = {}
for sym in symbols:
    ev = evaluator.evaluate(sym, latest_date)
    trend_map[sym] = ev

# ================================================================
# 4. Compute per-symbol per-model precision
# ================================================================
print("Computing per-symbol per-model precision...")

PHASES = {
    "2017": ("2017-01-03", "2017-12-29"),
    "2018": ("2018-01-02", "2018-12-28"),
    "2019": ("2019-01-02", "2019-12-31"),
    "ALL_OOS": ("2017-01-03", "2019-12-31"),
}

R_MODELS = ["r0", "r1", "r2", "r3", "r4", "r5", "r6", "r7", "ensemble"]

# Build pred index: {(symbol, date): {model: score}}
pred_index = {}
for p in all_preds:
    key = (p["symbol"], p["date"])
    pred_index[key] = {}
    for rid in ["r0", "r1", "r2", "r3", "r4", "r5", "r6", "r7"]:
        v = p[f"{rid}_score"]
        if v is not None:
            pred_index[key][rid] = float(v)
    if p["ensemble_score"] is not None:
        pred_index[key]["ensemble"] = float(p["ensemble_score"])

# Compute metrics
results = []  # list of dicts
for phase_name, (ps, pe) in PHASES.items():
    for sym in symbols:
        ev = trend_map.get(sym)
        for model_id in R_MODELS:
            buy_count = 0
            correct = 0
            returns = []

            for (s, d), scores in pred_index.items():
                if s != sym:
                    continue
                if d < ps or d > pe:
                    continue
                score = scores.get(model_id)
                if score is None or score <= 1.0:
                    continue

                ret = label_dict.get((s, d))
                if ret is None:
                    continue

                buy_count += 1
                if ret > 0:
                    correct += 1
                returns.append(ret)

            if buy_count >= 3:  # minimum 3 signals
                precision = correct / buy_count
                avg_ret = np.mean(returns)
                results.append({
                    "symbol": sym,
                    "phase": phase_name,
                    "model_id": model_id.upper(),
                    "buy_signals": buy_count,
                    "correct_t10": correct,
                    "precision_t10": round(precision, 4),
                    "avg_return_t10": round(float(avg_ret), 6),
                    "trend_20d": ev.trend_direction if ev else "UNKNOWN",
                    "trend_slope": round(ev.trend_slope, 6) if ev else 0,
                    "volatility_20d": round(ev.volatility_20d, 6) if ev else 0,
                    "route": ev.route if ev else "UNKNOWN",
                })

# Write to DB
conn = sqlite3.connect(MODELS_DB)
for r in results:
    conn.execute("""
        INSERT OR REPLACE INTO symbol_phase_metrics
        (symbol, phase, model_id, buy_signals, correct_t10, precision_t10,
         avg_return_t10, trend_20d, trend_slope, volatility_20d, route)
        VALUES (?,?,?,?,?,?,?,?,?,?,?)
    """, (r["symbol"], r["phase"], r["model_id"], r["buy_signals"],
          r["correct_t10"], r["precision_t10"], r["avg_return_t10"],
          r["trend_20d"], r["trend_slope"], r["volatility_20d"], r["route"]))
conn.commit()
total_rows = conn.execute("SELECT COUNT(*) FROM symbol_phase_metrics").fetchone()[0]
conn.close()

print(f"Written {total_rows} rows to symbol_phase_metrics")

# ================================================================
# 5. Reports
# ================================================================
print(f"\n{'=' * 70}")
print("TOP 10 SYMBOLS — HIGHEST PRECISION PER MODEL (OOS 2017-2019, T+10)")
print("=" * 70)

for model_id in ["R2", "R3", "R6", "R7", "ENSEMBLE"]:
    model_results = [r for r in results if r["model_id"] == model_id and r["phase"] == "ALL_OOS" and r["buy_signals"] >= 5]
    model_results.sort(key=lambda x: x["precision_t10"], reverse=True)

    print(f"\n  {model_id} — Top 10:")
    print(f"  {'Symbol':<10} {'BUY':>5} {'Correct':>8} {'Prec':>7} {'AvgRet':>9} {'Trend':>8} {'Route':>12}")
    print("  " + "-" * 62)
    for r in model_results[:10]:
        print(f"  {r['symbol']:<10} {r['buy_signals']:>5} {r['correct_t10']:>8} {r['precision_t10']:>5.1%} {r['avg_return_t10']:>+8.2%} {r['trend_20d']:>8} {r['route']:>12}")

# ================================================================
# 6. R2 RF best vs R7 CatBoost best
# ================================================================
print(f"\n{'=' * 70}")
print("R2 RF vs R7 CATBOOST — BEST SYMBOLS COMPARISON")
print("=" * 70)

r2_best = sorted(
    [r for r in results if r["model_id"] == "R2" and r["phase"] == "ALL_OOS" and r["buy_signals"] >= 5],
    key=lambda x: x["precision_t10"], reverse=True
)[:15]
r7_best = sorted(
    [r for r in results if r["model_id"] == "R7" and r["phase"] == "ALL_OOS" and r["buy_signals"] >= 5],
    key=lambda x: x["precision_t10"], reverse=True
)[:15]

r2_syms = set(r["symbol"] for r in r2_best)
r7_syms = set(r["symbol"] for r in r7_best)
overlap = r2_syms & r7_syms
r2_only = r2_syms - r7_syms
r7_only = r7_syms - r2_syms

print(f"\n  R2 RF top 15 symbols: {sorted(r2_syms)}")
print(f"  R7 CatBoost top 15 symbols: {sorted(r7_syms)}")
print(f"  Overlap: {sorted(overlap)} ({len(overlap)} symbols)")
print(f"  R2-only: {sorted(r2_only)}")
print(f"  R7-only: {sorted(r7_only)}")

# ================================================================
# 7. AVOID symbols
# ================================================================
print(f"\n{'=' * 70}")
print("SYMBOLS TO AVOID (VOLATILE or DECREASING trend)")
print("=" * 70)

avoid_symbols = []
for sym in symbols:
    ev = trend_map.get(sym)
    if not ev or not ev.has_sufficient_data:
        continue
    if ev.route == "AVOID" or ev.trend_direction == "DOWN" and ev.volatility_20d > 0.03:
        avoid_symbols.append({
            "symbol": sym,
            "trend": ev.trend_direction,
            "slope": ev.trend_slope,
            "vol": ev.volatility_20d,
            "route": ev.route,
            "reason": ev.route_reason,
        })

print(f"\n  {'Symbol':<10} {'Trend':>8} {'Slope':>10} {'Vol':>8} {'Route':>15} {'Reason'}")
print("  " + "-" * 70)
for a in sorted(avoid_symbols, key=lambda x: x["vol"], reverse=True):
    print(f"  {a['symbol']:<10} {a['trend']:>8} {a['slope']:>+9.4f} {a['vol']:>7.4f} {a['route']:>15} {a['reason']}")

if not avoid_symbols:
    print("  No symbols to avoid currently")

# Summary
momentum = [sym for sym, ev in trend_map.items() if ev.route == "MOMENTUM"]
mean_rev = [sym for sym, ev in trend_map.items() if ev.route == "MEAN_REVERSION"]
normal = [sym for sym, ev in trend_map.items() if ev.route == "NORMAL"]
avoid = [sym for sym, ev in trend_map.items() if ev.route == "AVOID"]

print(f"\n  Route summary:")
print(f"    MOMENTUM: {len(momentum)} symbols {sorted(momentum)[:10]}")
print(f"    MEAN_REVERSION: {len(mean_rev)} symbols {sorted(mean_rev)[:10]}")
print(f"    NORMAL: {len(normal)} symbols")
print(f"    AVOID: {len(avoid)} symbols {sorted(avoid)[:10]}")

print(f"\nTotal time: {time.time()-t0:.1f}s")
