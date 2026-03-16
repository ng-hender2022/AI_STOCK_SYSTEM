"""
Retrain R0-R5 on full data, predict on 2026-03-13, analyze BUY precision.
"""
import sqlite3, time, sys, os
import numpy as np
sys.path.insert(0, r"D:\AI")
sys.path.insert(0, r"D:\AI\data")

MARKET_DB = r"D:\AI\AI_data\market.db"
SIGNALS_DB = r"D:\AI\AI_data\signals.db"
MODELS_DB = r"D:\AI\AI_data\models.db"

TRAIN_START = "2014-03-06"
TRAIN_END = "2026-03-13"
PREDICT_DATE = "2026-03-13"

t0 = time.time()

# Get symbols
conn = sqlite3.connect(MARKET_DB)
symbols = [r[0] for r in conn.execute("SELECT symbol FROM symbols_master ORDER BY symbol").fetchall()]
conn.close()

# ================================================================
# STEP 1: Retrain R0-R5
# ================================================================
print("=" * 65)
print("STEP 1: Retraining R0-R5 on full data")
print("=" * 65)

MODEL_DEFS = [
    ("R0", "AI_engine.r_layer.r0_baseline.model", "R0Model", "r0_baseline"),
    ("R1", "AI_engine.r_layer.r1_linear.model", "R1Model", "r1_linear"),
    ("R2", "AI_engine.r_layer.r2_rf.model", "R2Model", "r2_rf"),
    ("R3", "AI_engine.r_layer.r3_gbdt.model", "R3Model", "r3_gbdt"),
    ("R4", "AI_engine.r_layer.r4_regime.model", "R4Model", "r4_regime"),
    ("R5", "AI_engine.r_layer.r5_sector.model", "R5Model", "r5_sector"),
]

models = {}
for name, modpath, clsname, folder in MODEL_DEFS:
    try:
        mod = __import__(modpath, fromlist=[clsname])
        cls = getattr(mod, clsname)
        m = cls(SIGNALS_DB, MODELS_DB, MARKET_DB)
        horizon = 20 if name == "R4" else 5
        metrics = m.train(TRAIN_START, TRAIN_END, horizon=horizon)
        pkl_path = f"D:/AI/AI_engine/r_layer/{folder}/model.pkl"
        m.save_model(pkl_path)
        models[name] = m

        if "error" in metrics:
            print(f"  {name}: SKIPPED - {metrics['error']}")
        else:
            acc = metrics.get("accuracy", metrics.get("r2", metrics.get("mse", "?")))
            print(f"  {name}: OK ({metrics.get('samples', '?')} samples, metric={acc})")
    except Exception as e:
        print(f"  {name}: FAIL - {e}")

print(f"  Time: {time.time()-t0:.1f}s")

# ================================================================
# STEP 2: Predict on 2026-03-13
# ================================================================
print(f"\n{'=' * 65}")
print(f"STEP 2: Predicting on {PREDICT_DATE}")
print("=" * 65)

for name, m in models.items():
    try:
        preds = m.predict(PREDICT_DATE, symbols=symbols)
        if preds:
            m.write_predictions(preds)
            print(f"  {name}: {len(preds)} predictions")
        else:
            print(f"  {name}: 0 predictions")
    except Exception as e:
        print(f"  {name}: FAIL - {e}")

# Ensemble + Master Summary + X1
from AI_engine.r_layer.ensemble import EnsembleEngine
from AI_engine.r_layer.master_summary import MasterSummary
from AI_engine.x1.portfolio_engine import PortfolioEngine
from AI_engine.x1.output_writer import OutputWriter

EnsembleEngine(MODELS_DB).compute_ensemble(PREDICT_DATE)
MasterSummary(MODELS_DB).compute(PREDICT_DATE)

pe = PortfolioEngine(MODELS_DB, MARKET_DB)
portfolio = pe.build(PREDICT_DATE)
stats = OutputWriter(MODELS_DB).write(portfolio)

buys = [e for e in portfolio.entries if e.action == "BUY"]
sells = [e for e in portfolio.entries if e.action == "SELL"]

print(f"\n  X1 Decisions ({PREDICT_DATE}):")
print(f"  BUY: {stats['buys']}, SELL: {stats['sells']}, HOLD: {stats['holds']}")
print(f"  Buy weight: {stats['total_buy_weight']:.1%}, Cash: {stats['cash_weight']:.1%}")

if buys:
    print(f"\n  Top BUY signals:")
    for b in sorted(buys, key=lambda x: x.score, reverse=True)[:10]:
        print(f"    {b.symbol}: score={b.score:.2f}, conf={b.confidence:.2f}, weight={b.weight:.1%}, {b.strength}")

if sells:
    print(f"\n  Top SELL signals:")
    for s in sorted(sells, key=lambda x: x.score)[:5]:
        print(f"    {s.symbol}: score={s.score:.2f}, {s.strength}")

# ================================================================
# STEP 3: BUY Signal Precision Analysis
# ================================================================
print(f"\n{'=' * 65}")
print("STEP 3: BUY Signal Precision Analysis (historical)")
print("=" * 65)

# Get all X1 BUY decisions from history (we need to generate them first)
# Use master_summary to find dates with positive ensemble scores
mconn = sqlite3.connect(MODELS_DB)
# Check if we have historical decisions
dec_count = 0
try:
    dec_count = mconn.execute("SELECT COUNT(*) FROM x1_decisions WHERE action='BUY'").fetchone()[0]
except:
    pass
mconn.close()

# Alternative: analyze based on ensemble_score > threshold as proxy for BUY signal
# Use r_predictions table which has scores for dates we ran predictions on
print("  Analyzing R model ensemble scores vs actual returns...")

sconn = sqlite3.connect(SIGNALS_DB)
lconn = sqlite3.connect(MODELS_DB)

# Get all r_predictions with ensemble scores
try:
    r_preds = lconn.execute("""
        SELECT symbol, date, ensemble_score, ensemble_confidence, ensemble_direction
        FROM r_predictions WHERE ensemble_score IS NOT NULL
    """).fetchall()
except:
    r_preds = []

if not r_preds:
    print("  No ensemble predictions available for analysis.")
    print("  Running batch predictions on sampled dates...")

    # Get sampled dates with meta_features
    meta_dates = [r[0] for r in sconn.execute(
        "SELECT DISTINCT date FROM meta_features ORDER BY date"
    ).fetchall()]

    # Sample every 10th date for predictions
    sample_dates = meta_dates[::10]
    print(f"  Predicting on {len(sample_dates)} sampled dates...")

    for sd in sample_dates:
        for name, m in models.items():
            try:
                preds = m.predict(sd, symbols=symbols)
                if preds:
                    m.write_predictions(preds)
            except:
                pass
        EnsembleEngine(MODELS_DB).compute_ensemble(sd)

    r_preds = lconn.execute("""
        SELECT symbol, date, ensemble_score, ensemble_confidence, ensemble_direction
        FROM r_predictions WHERE ensemble_score IS NOT NULL
    """).fetchall()
    print(f"  Generated {len(r_preds)} predictions")

# Now analyze: for each prediction, match with actual return from training_labels
thresholds = [0.0, 0.01, 0.02, 0.03, 0.05]
horizons = [1, 5, 10, 20, 50]

# Build prediction dict
pred_dict = {}
for r in r_preds:
    pred_dict[(r[0], r[1])] = {"score": r[2], "confidence": r[3], "direction": r[4]}

# Get labels
labels = sconn.execute("SELECT symbol, feature_date, t1_return, t5_return, t10_return, t20_return, t50_return FROM training_labels").fetchall()

label_dict = {}
for l in labels:
    label_dict[(l[0], l[1])] = {1: l[2], 5: l[3], 10: l[4], 20: l[5], 50: l[6]}

# Analyze BUY signals (ensemble_score > 1.0)
buy_threshold = 1.0
strong_buy_threshold = 2.0

print(f"\n  BUY signal analysis (ensemble_score > {buy_threshold}):")
print(f"  {'Horizon':<10} {'Total':>7} {'> 0%':>8} {'> 1%':>8} {'> 2%':>8} {'> 3%':>8} {'> 5%':>8}")
print("  " + "-" * 60)

for h in horizons:
    total = 0
    wins = {t: 0 for t in thresholds}

    for key, pred in pred_dict.items():
        if pred["score"] <= buy_threshold:
            continue
        if key not in label_dict:
            continue
        ret = label_dict[key].get(h)
        if ret is None:
            continue

        total += 1
        for t in thresholds:
            if ret > t:
                wins[t] += 1

    if total > 0:
        pcts = "  ".join(f"{100*wins[t]/total:5.1f}%" for t in thresholds)
        print(f"  T+{h:<7d} {total:>7d} {pcts}")
    else:
        print(f"  T+{h:<7d}       0   (no data)")

print(f"\n  STRONG BUY analysis (ensemble_score > {strong_buy_threshold}):")
print(f"  {'Horizon':<10} {'Total':>7} {'> 0%':>8} {'> 1%':>8} {'> 2%':>8} {'> 3%':>8} {'> 5%':>8}")
print("  " + "-" * 60)

for h in horizons:
    total = 0
    wins = {t: 0 for t in thresholds}

    for key, pred in pred_dict.items():
        if pred["score"] <= strong_buy_threshold:
            continue
        if key not in label_dict:
            continue
        ret = label_dict[key].get(h)
        if ret is None:
            continue

        total += 1
        for t in thresholds:
            if ret > t:
                wins[t] += 1

    if total > 0:
        pcts = "  ".join(f"{100*wins[t]/total:5.1f}%" for t in thresholds)
        print(f"  T+{h:<7d} {total:>7d} {pcts}")
    else:
        print(f"  T+{h:<7d}       0   (no data)")

sconn.close()
lconn.close()

# ================================================================
# STEP 4: Backup Plan A
# ================================================================
print(f"\n{'=' * 65}")
print("STEP 4: Backup Plan A")
print("=" * 65)

import shutil
plan_dir = r"D:\AI\AI_data\plans\plan_a"
os.makedirs(plan_dir, exist_ok=True)

for src, dst_name in [
    (MARKET_DB, "market.db"),
    (SIGNALS_DB, "signals.db"),
    (MODELS_DB, "models.db"),
]:
    dst = os.path.join(plan_dir, dst_name)
    shutil.copy2(src, dst)
    size_mb = os.path.getsize(dst) / 1e6
    print(f"  {dst_name}: {size_mb:.1f} MB")

# Copy model pickles
model_plan_dir = os.path.join(plan_dir, "models")
os.makedirs(model_plan_dir, exist_ok=True)
for name, _, _, folder in MODEL_DEFS:
    src = f"D:/AI/AI_engine/r_layer/{folder}/model.pkl"
    if os.path.exists(src):
        shutil.copy2(src, os.path.join(model_plan_dir, f"{name}.pkl"))
        print(f"  {name}.pkl copied")

total = time.time() - t0
print(f"\nTotal time: {total:.1f}s ({total/60:.1f} min)")
print("=" * 65)
