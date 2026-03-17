"""
R7 v4: Leakage fix + bear block + threshold tuning for ~6000 signals.
Meta recalc already done. Pre-listing already cleaned.
"""
import sqlite3, time, sys, os, warnings
import numpy as np
warnings.filterwarnings("ignore")
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, r"D:\AI")
sys.path.insert(0, r"D:\AI\data")

MARKET_DB = r"D:\AI\AI_data\market.db"
SIGNALS_DB = r"D:\AI\AI_data\signals.db"
MODELS_DB = r"D:\AI\AI_data\models.db"

t0 = time.time()

# ================================================================
# STEP 1: Recalculate meta features (regime T-1 fix)
# ================================================================
print("=" * 65)
print("STEP 1: Recalculate meta features (regime T-1 fix)")
print("=" * 65)

from AI_engine.meta_layer.feature_matrix_writer import FeatureMatrixWriter
FeatureMatrixWriter.ensure_schema(SIGNALS_DB)
fw = FeatureMatrixWriter(SIGNALS_DB, MARKET_DB)

conn = sqlite3.connect(SIGNALS_DB)
all_dates = [r[0] for r in conn.execute(
    "SELECT DISTINCT date FROM expert_signals ORDER BY date"
).fetchall()]
conn.close()
print(f"  Dates: {len(all_dates)}")

t1 = time.time()
for i, d in enumerate(all_dates):
    fw.run(d)
    if (i + 1) % 500 == 0:
        elapsed = time.time() - t1
        rate = (i + 1) / elapsed
        remaining = (len(all_dates) - i - 1) / rate if rate > 0 else 0
        print(f"  [{i+1}/{len(all_dates)}] {d} | {elapsed:.0f}s, ~{remaining/60:.0f}min")
print(f"  Done: {(time.time()-t1)/60:.1f} min")

# ================================================================
# STEP 2: Retrain R7 with regime T-1 data
# ================================================================
print(f"\n{'=' * 65}")
print("STEP 2: Retrain R7 (monotonic + regime-aware, CPU)")
print("=" * 65)

t2 = time.time()
from AI_engine.r_layer.r7_catboost.model import R7Model
m = R7Model(SIGNALS_DB, MODELS_DB, MARKET_DB)
metrics = m.train("2014-03-06", "2026-03-13", horizon=5)
m.save_model("D:/AI/AI_engine/r_layer/r7_catboost/model.pkl")
print(f"  R7: {metrics}")
print(f"  Time: {time.time()-t2:.1f}s")

# ================================================================
# STEP 3: Threshold tuning - try 0.55, 0.57, 0.58 for neutral/bull
# ================================================================
print(f"\n{'=' * 65}")
print("STEP 3: Threshold tuning (target ~6000 signals)")
print("=" * 65)

conn = sqlite3.connect(MARKET_DB)
symbols = [r[0] for r in conn.execute("SELECT symbol FROM symbols_master ORDER BY symbol").fetchall()]
conn.close()

conn = sqlite3.connect(SIGNALS_DB)
predict_dates = [r[0] for r in conn.execute(
    "SELECT DISTINCT date FROM meta_features ORDER BY date"
).fetchall()]
conn.close()

# Collect raw predictions (p_up + regime) without thresholding
print("  Collecting raw predictions...")
m2 = R7Model(SIGNALS_DB, MODELS_DB, MARKET_DB)
m2.load_model("D:/AI/AI_engine/r_layer/r7_catboost/model.pkl")

raw_preds = []  # (date, symbol, p_up, raw_regime)
t3 = time.time()
for i, d in enumerate(predict_dates):
    X = m2.load_feature_matrix(d, d, symbols)
    if X.empty:
        continue
    sym_dates = X[["symbol", "date"]].copy()
    X_feat = X.drop(columns=["symbol", "date"], errors="ignore")
    for col in m2._feature_names:
        if col not in X_feat.columns:
            X_feat[col] = 0.0
    X_feat = X_feat[m2._feature_names].fillna(0.0)

    probs = m2.model.predict_proba(X_feat)
    for j in range(len(sym_dates)):
        p_up = float(probs[j][1]) if probs.shape[1] > 1 else float(probs[j][0])
        raw_regime = float(X_feat.iloc[j].get("regime_score", 0.0)) * 4.0
        raw_preds.append((d, sym_dates.iloc[j]["symbol"], p_up, raw_regime))

    if (i + 1) % 500 == 0:
        print(f"    [{i+1}/{len(predict_dates)}] collected {len(raw_preds)} raw preds")

print(f"  Collected {len(raw_preds)} raw predictions in {(time.time()-t3)/60:.1f} min")

# Test thresholds
for bull_th in [0.55, 0.57, 0.58, 0.60]:
    count = 0
    for d, sym, p_up, raw_reg in raw_preds:
        if raw_reg <= -2.0:
            continue  # bear block
        elif raw_reg <= -1.0:
            if p_up >= 0.70:
                count += 1
        else:
            if p_up >= bull_th:
                count += 1
    print(f"  bull_threshold={bull_th}: {count} signals")

# Pick best
best_th = None
best_diff = 999999
for bull_th in [0.54, 0.55, 0.56, 0.57, 0.58, 0.59, 0.60]:
    count = 0
    for d, sym, p_up, raw_reg in raw_preds:
        if raw_reg <= -2.0:
            continue
        elif raw_reg <= -1.0:
            if p_up >= 0.70:
                count += 1
        else:
            if p_up >= bull_th:
                count += 1
    diff = abs(count - 6000)
    if diff < best_diff:
        best_diff = diff
        best_th = bull_th
        best_count = count

print(f"\n  BEST: bull_threshold={best_th} → {best_count} signals (target 6000, diff {best_diff})")

# ================================================================
# STEP 4: Write predictions with best threshold
# ================================================================
print(f"\n{'=' * 65}")
print(f"STEP 4: Write R7 predictions (bull_th={best_th})")
print("=" * 65)

# Clear R7 scores
conn = sqlite3.connect(MODELS_DB)
conn.execute("UPDATE r_predictions SET r7_score = NULL")
conn.commit()
conn.close()

total_signals = 0
phase_counts = {}
conn = sqlite3.connect(MODELS_DB)
conn.execute("PRAGMA journal_mode=WAL")

for d, sym, p_up, raw_reg in raw_preds:
    # Apply regime-adaptive threshold
    if raw_reg <= -2.0:
        score = 0.0
    elif raw_reg <= -1.0:
        if p_up >= 0.70:
            score = max(-4.0, min(4.0, (p_up - 0.5) * 8))
        else:
            score = 0.0
    else:
        if p_up >= best_th:
            score = max(-4.0, min(4.0, (p_up - 0.5) * 8))
        else:
            score = 0.0

    # Write to DB
    row = conn.execute(
        "SELECT rowid FROM r_predictions WHERE symbol=? AND date=? AND snapshot_time='EOD'",
        (sym, d),
    ).fetchone()
    if row:
        conn.execute(
            "UPDATE r_predictions SET r7_score=? WHERE symbol=? AND date=? AND snapshot_time='EOD'",
            (score, sym, d),
        )
    else:
        conn.execute(
            "INSERT INTO r_predictions (symbol, date, snapshot_time, r7_score, model_version) VALUES (?, ?, 'EOD', ?, ?)",
            (sym, d, score, m2.model_version),
        )

    if score != 0:
        total_signals += 1
        y = d[:4]
        phase_counts[y] = phase_counts.get(y, 0) + 1

conn.commit()
conn.close()

print(f"  Total non-zero signals: {total_signals}")
print(f"\n  Signals per phase:")
for y in sorted(phase_counts):
    print(f"    {y}: {phase_counts[y]}")

# ================================================================
# STEP 5: Verify leakage
# ================================================================
print(f"\n{'=' * 65}")
print("STEP 5: Leak check")
print("=" * 65)

from leak_checker import LeakChecker
checker = LeakChecker(market_db=MARKET_DB, signals_db=SIGNALS_DB)
try:
    results = checker.check_all(train_end="2025-12-31", val_start="2026-01-01")
    for k, v in results.items():
        print(f"  {k}: {'PASS' if v['passed'] else 'FAIL'} - {v['message']}")
except Exception as e:
    print(f"  {e}")

# DB verify
conn = sqlite3.connect(MODELS_DB)
db_count = conn.execute("SELECT COUNT(*) FROM r_predictions WHERE r7_score IS NOT NULL AND r7_score != 0").fetchone()[0]
conn.close()
print(f"\n  DB verify: {db_count} non-zero r7_score rows")

total = time.time() - t0
print(f"\nTotal: {total:.1f}s ({total/60:.1f} min)")
