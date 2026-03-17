"""
R7 v5 retrain + predict + OOS evaluation.
Fixed score formula (center=0.33) + regime-aware BUY/SELL filters.
"""
import sqlite3, time, sys, os, shutil
import numpy as np
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, r"D:\AI")

MARKET_DB = r"D:\AI\AI_data\market.db"
SIGNALS_DB = r"D:\AI\AI_data\signals.db"
MODELS_DB = r"D:\AI\AI_data\models.db"
MODEL_PKL = r"D:\AI\AI_engine\r_layer\r7_catboost\model.pkl"
MODEL_PKL_V2 = r"D:\AI\AI_data\plans\plan_a_v2\models\R7.pkl"

t0 = time.time()

# ================================================================
# STEP 1: Clean R7 data
# ================================================================
print("=" * 65)
print("STEP 1: Clean R7 data")
print("=" * 65)
conn = sqlite3.connect(MODELS_DB)
conn.execute("UPDATE r_predictions SET r7_score = NULL")
conn.execute("DELETE FROM training_history WHERE model_id='R7'")
conn.commit()
conn.close()
print("  r7_score nulled, training_history cleaned")

# ================================================================
# STEP 2: Retrain R7 on full data
# ================================================================
print(f"\n{'=' * 65}")
print("STEP 2: Retrain R7 (monotonic + regime-aware + CPU)")
print("=" * 65)
t1 = time.time()
from AI_engine.r_layer.r7_catboost.model import R7Model, MONOTONIC_CONSTRAINTS
m = R7Model(SIGNALS_DB, MODELS_DB, MARKET_DB)
metrics = m.train("2014-03-06", "2026-03-13", horizon=5)
m.save_model(MODEL_PKL)
shutil.copy2(MODEL_PKL, MODEL_PKL_V2)
print(f"  Metrics: {metrics}")
print(f"  Monotonic: {sum(1 for v in MONOTONIC_CONSTRAINTS.values() if v != 0)} constrained")
print(f"  Features: {len(m._feature_names)}")
print(f"  Time: {time.time()-t1:.1f}s")

# ================================================================
# STEP 3: Predict on all dates
# ================================================================
print(f"\n{'=' * 65}")
print("STEP 3: Predict on all dates")
print("=" * 65)

conn = sqlite3.connect(MARKET_DB)
symbols = [r[0] for r in conn.execute("SELECT symbol FROM symbols_master ORDER BY symbol").fetchall()]
conn.close()

sconn = sqlite3.connect(SIGNALS_DB)
predict_dates = [r[0] for r in sconn.execute(
    "SELECT DISTINCT date FROM meta_features ORDER BY date"
).fetchall()]
sconn.close()
print(f"  {len(predict_dates)} dates, {len(symbols)} symbols")

t2 = time.time()
buy_count = 0
sell_count = 0
neutral_count = 0
for i, d in enumerate(predict_dates):
    preds = m.predict(d, symbols=symbols)
    if preds:
        m.write_predictions(preds)
        for p in preds:
            if p["score"] > 0:
                buy_count += 1
            elif p["score"] < 0:
                sell_count += 1
            else:
                neutral_count += 1
    if (i + 1) % 500 == 0:
        print(f"  [{i+1}/{len(predict_dates)}] BUY={buy_count} SELL={sell_count} NEUTRAL={neutral_count}")

print(f"  Done: {time.time()-t2:.1f}s")
print(f"  BUY={buy_count} SELL={sell_count} NEUTRAL={neutral_count} Total={buy_count+sell_count}")

# ================================================================
# STEP 4: Rolling OOS evaluation (BUY + SELL)
# ================================================================
print(f"\n{'=' * 65}")
print("STEP 4: Rolling OOS evaluation (BUY + SELL)")
print("=" * 65)

# Load labels
sconn = sqlite3.connect(SIGNALS_DB)
labels_raw = sconn.execute(
    "SELECT symbol, feature_date, t10_return FROM training_labels WHERE t10_return IS NOT NULL"
).fetchall()
sconn.close()
label_dict = {(l[0], l[1]): l[2] for l in labels_raw}
print(f"  Labels loaded: {len(label_dict)}")

# Build phases by year
conn = sqlite3.connect(MARKET_DB)
all_dates = [r[0] for r in conn.execute(
    "SELECT DISTINCT date FROM prices_daily WHERE symbol='VNINDEX' ORDER BY date"
).fetchall()]
conn.close()

years = {}
for d in all_dates:
    y = d[:4]
    if y not in years:
        years[y] = []
    years[y].append(d)
phases = []
for y in sorted(years):
    ds = years[y]
    phases.append((y, ds[0], ds[-1]))

# Get meta_features dates
sconn = sqlite3.connect(SIGNALS_DB)
meta_dates = set(r[0] for r in sconn.execute("SELECT DISTINCT date FROM meta_features").fetchall())
sconn.close()

buy_results = {}
sell_results = {}

t3 = time.time()
for pi in range(1, len(phases)):
    test_name, test_start, test_end = phases[pi]
    train_end = phases[pi - 1][2]

    # Train on cumulative data up to previous phase
    m2 = R7Model(SIGNALS_DB, MODELS_DB, MARKET_DB)
    try:
        m2.train("2014-03-06", train_end, horizon=5)
    except Exception as e:
        print(f"  Phase {test_name}: train failed ({e})")
        continue

    # Get test dates with features
    td = sorted(d for d in meta_dates if test_start <= d <= test_end)
    if not td:
        continue

    buy_stats = {"total": 0, "correct": 0, "rets": []}
    sell_stats = {"total": 0, "correct": 0, "rets": []}

    for d in td:
        preds = m2.predict(d, symbols=symbols)
        for p in preds:
            key = (p["symbol"], d)
            if key not in label_dict:
                continue
            ret = label_dict[key]

            # BUY: score > 1.0
            if p["score"] > 1.0:
                buy_stats["total"] += 1
                if ret > 0:
                    buy_stats["correct"] += 1
                buy_stats["rets"].append(ret)

            # SELL: score < -1.0
            elif p["score"] < -1.0:
                sell_stats["total"] += 1
                if ret < 0:
                    sell_stats["correct"] += 1
                sell_stats["rets"].append(ret)

    # Compute BUY metrics
    if buy_stats["total"] > 0:
        rets = np.array(buy_stats["rets"])
        prec = buy_stats["correct"] / buy_stats["total"]
        wins = rets[rets > 0]
        losses = rets[rets <= 0]
        avg_win = float(np.mean(wins)) if len(wins) > 0 else 0.0
        avg_loss = float(np.mean(losses)) if len(losses) > 0 else 0.0
        ev = prec * avg_win + (1 - prec) * avg_loss
        std = float(np.std(rets)) if len(rets) > 1 else 1e-9
        sharpe = float(np.mean(rets)) / std if std > 1e-9 else 0.0
        buy_results[test_name] = {
            "signals": buy_stats["total"], "precision": round(prec * 100, 1),
            "avg_ret": float(np.mean(rets)), "ev": ev, "sharpe": sharpe,
        }
    else:
        buy_results[test_name] = {"signals": 0, "precision": 0, "avg_ret": 0, "ev": 0, "sharpe": 0}

    # Compute SELL metrics (for SELL, "correct" = price went down, profit = -ret)
    if sell_stats["total"] > 0:
        rets = np.array(sell_stats["rets"])
        prec = sell_stats["correct"] / sell_stats["total"]
        # For SELL signals, profit is -return (short position)
        profits = -rets
        wins = profits[profits > 0]
        losses = profits[profits <= 0]
        avg_win = float(np.mean(wins)) if len(wins) > 0 else 0.0
        avg_loss = float(np.mean(losses)) if len(losses) > 0 else 0.0
        ev = prec * avg_win + (1 - prec) * avg_loss
        std = float(np.std(profits)) if len(profits) > 1 else 1e-9
        sharpe = float(np.mean(profits)) / std if std > 1e-9 else 0.0
        sell_results[test_name] = {
            "signals": sell_stats["total"], "precision": round(prec * 100, 1),
            "avg_ret": float(np.mean(profits)), "ev": ev, "sharpe": sharpe,
        }
    else:
        sell_results[test_name] = {"signals": 0, "precision": 0, "avg_ret": 0, "ev": 0, "sharpe": 0}

    b = buy_results[test_name]
    s = sell_results[test_name]
    print(f"  {test_name}: BUY {b['signals']} sig, prec={b['precision']:.1f}%, EV={b['ev']:+.4f} | "
          f"SELL {s['signals']} sig, prec={s['precision']:.1f}%, EV={s['ev']:+.4f}")

print(f"  OOS time: {time.time()-t3:.1f}s")

# ================================================================
# STEP 5: Summary Report
# ================================================================
print(f"\n{'=' * 65}")
print("STEP 5: Summary Report")
print("=" * 65)

print(f"\n  === BUY Signals OOS ===")
print(f"  {'Phase':<8} {'Signals':>7} {'Prec':>7} {'AvgRet':>8} {'EV':>8} {'Sharpe':>8}")
print(f"  {'-'*48}")
total_buy_sig = 0
buy_ev_pos = 0
for y in sorted(buy_results):
    r = buy_results[y]
    total_buy_sig += r["signals"]
    if r["ev"] > 0:
        buy_ev_pos += 1
    if r["signals"] > 0:
        print(f"  {y:<8} {r['signals']:>7} {r['precision']:>6.1f}% {r['avg_ret']:>+7.2%} {r['ev']:>+7.4f} {r['sharpe']:>7.3f}")
    else:
        print(f"  {y:<8} {0:>7} {'---':>7} {'---':>8} {'---':>8} {'---':>8}")

print(f"\n  === SELL Signals OOS ===")
print(f"  {'Phase':<8} {'Signals':>7} {'Prec':>7} {'AvgRet':>8} {'EV':>8} {'Sharpe':>8}")
print(f"  {'-'*48}")
total_sell_sig = 0
sell_ev_pos = 0
for y in sorted(sell_results):
    r = sell_results[y]
    total_sell_sig += r["signals"]
    if r["ev"] > 0:
        sell_ev_pos += 1
    if r["signals"] > 0:
        print(f"  {y:<8} {r['signals']:>7} {r['precision']:>6.1f}% {r['avg_ret']:>+7.2%} {r['ev']:>+7.4f} {r['sharpe']:>7.3f}")
    else:
        print(f"  {y:<8} {0:>7} {'---':>7} {'---':>8} {'---':>8} {'---':>8}")

print(f"\n  === Overall ===")
print(f"  Prediction: BUY={buy_count} SELL={sell_count} Total={buy_count+sell_count}")
print(f"  OOS BUY:  {total_buy_sig} signals, {buy_ev_pos}/{len(buy_results)} phases EV+")
print(f"  OOS SELL: {total_sell_sig} signals, {sell_ev_pos}/{len(sell_results)} phases EV+")

total = time.time() - t0
print(f"\n  Total time: {total:.1f}s ({total/60:.1f} min)")
