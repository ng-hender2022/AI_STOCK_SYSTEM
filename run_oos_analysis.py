"""
PROPER OUT-OF-SAMPLE BUY Precision Analysis
Train: Phase TEST + Phase 1 (2014-03-06 -> 2016-12-30)
Test:  Phase 2 (2017-01-03 -> 2019-12-31) — NEVER seen in training

Walk-forward: retrain at start of Phase 2, predict on Phase 2 dates.
"""
import sqlite3, time, sys
import numpy as np
sys.path.insert(0, r"D:\AI")
sys.path.insert(0, r"D:\AI\data")

MARKET_DB = r"D:\AI\AI_data\market.db"
SIGNALS_DB = r"D:\AI\AI_data\signals.db"
MODELS_DB = r"D:\AI\AI_data\models.db"

TRAIN_START = "2014-03-06"
TRAIN_END = "2016-12-30"
TEST_START = "2017-01-03"
TEST_END = "2019-12-31"

t0 = time.time()

print("=" * 70)
print("OUT-OF-SAMPLE BUY PRECISION ANALYSIS")
print(f"Train: {TRAIN_START} -> {TRAIN_END} (Phase TEST + Phase 1)")
print(f"Test:  {TEST_START} -> {TEST_END} (Phase 2 — never seen)")
print("=" * 70)

# Get symbols
conn = sqlite3.connect(MARKET_DB)
symbols = [r[0] for r in conn.execute("SELECT symbol FROM symbols_master ORDER BY symbol").fetchall()]
conn.close()

# Step 1: Train R0-R5 on Phase TEST + Phase 1 ONLY
print(f"\nStep 1: Training R0-R5 on {TRAIN_START} -> {TRAIN_END}...")

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
        models[name] = m
        if "error" in metrics:
            print(f"  {name}: SKIPPED - {metrics['error']}")
        else:
            acc = metrics.get("accuracy", metrics.get("r2", "?"))
            print(f"  {name}: OK ({metrics.get('samples', '?')} samples, metric={acc})")
    except Exception as e:
        print(f"  {name}: FAIL - {e}")

print(f"  Training time: {time.time()-t0:.1f}s")

# Step 2: Get test dates with meta_features
conn = sqlite3.connect(SIGNALS_DB)
test_dates_with_meta = [r[0] for r in conn.execute(
    "SELECT DISTINCT date FROM meta_features WHERE date>=? AND date<=? ORDER BY date",
    (TEST_START, TEST_END),
).fetchall()]
conn.close()
print(f"\nStep 2: Test dates with meta_features: {len(test_dates_with_meta)}")

if not test_dates_with_meta:
    print("  No meta_features for test period. Running experts...")
    # Need to generate expert signals for test dates
    from AI_engine.meta_layer.feature_matrix_writer import FeatureMatrixWriter
    from AI_engine.experts.market_context.v4reg.regime_writer import RegimeWriter
    from AI_engine.experts.market_context.v4br.expert_writer import BreadthExpertWriter

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
    fw = FeatureMatrixWriter(SIGNALS_DB, MARKET_DB)

    # Sample test dates (every 5th)
    conn2 = sqlite3.connect(MARKET_DB)
    all_test_dates = [r[0] for r in conn2.execute(
        "SELECT DISTINCT date FROM prices_daily WHERE symbol='VNINDEX' AND date>=? AND date<=? ORDER BY date",
        (TEST_START, TEST_END),
    ).fetchall()]
    conn2.close()

    sample_test = all_test_dates[::5]
    print(f"  Running experts on {len(sample_test)} test dates...")

    for i, d in enumerate(sample_test):
        RegimeWriter(MARKET_DB).run(d)
        for eid, mp, cn in EXPERT_IMPORTS:
            try:
                mod2 = __import__(mp, fromlist=[cn])
                cls2 = getattr(mod2, cn)
                w = cls2(MARKET_DB, SIGNALS_DB)
                w.run_all(d, symbols=symbols)
            except:
                pass
        try:
            BreadthExpertWriter(MARKET_DB, SIGNALS_DB).run(d)
        except:
            pass
        fw.run(d)
        if (i+1) % 20 == 0:
            print(f"    [{i+1}/{len(sample_test)}] {d}")

    conn = sqlite3.connect(SIGNALS_DB)
    test_dates_with_meta = [r[0] for r in conn.execute(
        "SELECT DISTINCT date FROM meta_features WHERE date>=? AND date<=? ORDER BY date",
        (TEST_START, TEST_END),
    ).fetchall()]
    conn.close()
    print(f"  Test dates with meta: {len(test_dates_with_meta)}")

# Step 3: Predict on ALL test dates (out-of-sample)
print(f"\nStep 3: Predicting on {len(test_dates_with_meta)} OOS dates...")

from AI_engine.r_layer.ensemble import EnsembleEngine

pred_count = 0
for i, d in enumerate(test_dates_with_meta):
    for name, m in models.items():
        try:
            preds = m.predict(d, symbols=symbols)
            if preds:
                m.write_predictions(preds)
        except:
            pass
    EnsembleEngine(MODELS_DB).compute_ensemble(d)
    pred_count += 1
    if (i+1) % 20 == 0:
        print(f"  [{i+1}/{len(test_dates_with_meta)}] {d}")

print(f"  Predictions generated for {pred_count} dates")

# Step 4: Analyze OOS precision
print(f"\n{'=' * 70}")
print("OUT-OF-SAMPLE BUY SIGNAL PRECISION")
print(f"Train: {TRAIN_START} -> {TRAIN_END}")
print(f"Test:  {TEST_START} -> {TEST_END} (NEVER seen in training)")
print("=" * 70)

# Load predictions
mconn = sqlite3.connect(MODELS_DB)
r_preds = mconn.execute("""
    SELECT symbol, date, ensemble_score, ensemble_confidence
    FROM r_predictions
    WHERE ensemble_score IS NOT NULL AND date>=? AND date<=?
""", (TEST_START, TEST_END)).fetchall()
mconn.close()

pred_dict = {}
for r in r_preds:
    pred_dict[(r[0], r[1])] = {"score": r[2], "confidence": r[3]}

# Load labels
sconn = sqlite3.connect(SIGNALS_DB)
labels = sconn.execute("""
    SELECT symbol, feature_date, t1_return, t5_return, t10_return, t20_return, t50_return
    FROM training_labels WHERE feature_date>=? AND feature_date<=?
""", (TEST_START, TEST_END)).fetchall()
sconn.close()

label_dict = {}
for l in labels:
    label_dict[(l[0], l[1])] = {1: l[2], 5: l[3], 10: l[4], 20: l[5], 50: l[6]}

print(f"\nOOS predictions: {len(pred_dict)}")
print(f"OOS labels: {len(label_dict)}")

thresholds = [0.0, 0.01, 0.02, 0.03, 0.05]
horizons = [1, 5, 10, 20, 50]

for buy_thresh, label in [(1.0, "BUY (score > 1.0)"), (2.0, "STRONG BUY (score > 2.0)"), (0.5, "WEAK BUY (score > 0.5)")]:
    print(f"\n  {label}:")
    print(f"  {'Horizon':<10} {'Total':>7} {'> 0%':>8} {'> 1%':>8} {'> 2%':>8} {'> 3%':>8} {'> 5%':>8}")
    print("  " + "-" * 60)

    for h in horizons:
        total = 0
        wins = {t: 0 for t in thresholds}

        for key, pred in pred_dict.items():
            if pred["score"] <= buy_thresh:
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
            print(f"  T+{h:<7d}       0   (no signals)")

    # Also show SELL precision
    print(f"\n  SELL (score < -{buy_thresh}):")
    print(f"  {'Horizon':<10} {'Total':>7} {'< 0%':>8} {'<-1%':>8} {'<-2%':>8} {'<-3%':>8} {'<-5%':>8}")
    print("  " + "-" * 60)

    for h in horizons:
        total = 0
        wins = {t: 0 for t in thresholds}

        for key, pred in pred_dict.items():
            if pred["score"] >= -buy_thresh:
                continue
            if key not in label_dict:
                continue
            ret = label_dict[key].get(h)
            if ret is None:
                continue

            total += 1
            for t in thresholds:
                if ret < -t:
                    wins[t] += 1

        if total > 0:
            pcts = "  ".join(f"{100*wins[t]/total:5.1f}%" for t in thresholds)
            print(f"  T+{h:<7d} {total:>7d} {pcts}")
        else:
            print(f"  T+{h:<7d}       0   (no signals)")

# Random baseline for comparison
print(f"\n  RANDOM BASELINE (all predictions):")
print(f"  {'Horizon':<10} {'Total':>7} {'> 0%':>8}")
print("  " + "-" * 30)
for h in horizons:
    total = 0
    pos = 0
    for key in pred_dict:
        if key in label_dict:
            ret = label_dict[key].get(h)
            if ret is not None:
                total += 1
                if ret > 0:
                    pos += 1
    if total > 0:
        print(f"  T+{h:<7d} {total:>7d} {100*pos/total:5.1f}%")

total_time = time.time() - t0
print(f"\nTotal time: {total_time:.1f}s ({total_time/60:.1f} min)")
print("=" * 70)
