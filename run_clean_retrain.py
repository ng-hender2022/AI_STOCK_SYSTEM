"""
Clean R Layer outputs, retrain R0-R7 on full data, backup Plan A.
"""
import sqlite3, time, sys, shutil, os
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, r"D:\AI")
sys.path.insert(0, r"D:\AI\data")

MARKET_DB = r"D:\AI\AI_data\market.db"
SIGNALS_DB = r"D:\AI\AI_data\signals.db"
MODELS_DB = r"D:\AI\AI_data\models.db"

t0 = time.time()

# ================================================================
# STEP 1: Clean R Layer outputs
# ================================================================
print("=" * 65)
print("STEP 1: Cleaning R Layer outputs in models.db")
print("=" * 65)

conn = sqlite3.connect(MODELS_DB)
for table in ["r_predictions", "master_summary", "x1_decisions", "symbol_phase_metrics"]:
    try:
        count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        conn.execute(f"DELETE FROM {table}")
        print(f"  {table}: deleted {count} rows")
    except Exception as e:
        print(f"  {table}: {e}")
conn.commit()

# Verify empty
print("\nVerification:")
for table in ["r_predictions", "master_summary", "x1_decisions", "symbol_phase_metrics"]:
    try:
        count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        print(f"  {table}: {count} rows {'OK' if count == 0 else 'NOT EMPTY!'}")
    except:
        print(f"  {table}: table not found")

# Verify signals.db untouched
sconn = sqlite3.connect(SIGNALS_DB)
for table in ["expert_signals", "meta_features", "training_labels"]:
    count = sconn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    print(f"  signals.db/{table}: {count} rows (preserved)")
sconn.close()
conn.close()

print(f"  Time: {time.time()-t0:.1f}s")

# ================================================================
# STEP 2: Retrain R0-R7 on full data
# ================================================================
print(f"\n{'=' * 65}")
print("STEP 2: Retrain R0-R7 on full 3000 days")
print("=" * 65)

TRAIN_START = "2014-03-06"
TRAIN_END = "2026-03-13"

MODEL_DEFS = [
    ("R0", "AI_engine.r_layer.r0_baseline.model", "R0Model", "r0_baseline"),
    ("R1", "AI_engine.r_layer.r1_linear.model", "R1Model", "r1_linear"),
    ("R2", "AI_engine.r_layer.r2_rf.model", "R2Model", "r2_rf"),
    ("R3", "AI_engine.r_layer.r3_gbdt.model", "R3Model", "r3_gbdt"),
    ("R4", "AI_engine.r_layer.r4_regime.model", "R4Model", "r4_regime"),
    ("R5", "AI_engine.r_layer.r5_sector.model", "R5Model", "r5_sector"),
    ("R6", "AI_engine.r_layer.r6_xgboost.model", "R6Model", "r6_xgboost"),
    ("R7", "AI_engine.r_layer.r7_catboost.model", "R7Model", "r7_catboost"),
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
# STEP 3: Verify models saved
# ================================================================
print(f"\n{'=' * 65}")
print("STEP 3: Verify")
print("=" * 65)

conn = sqlite3.connect(MODELS_DB)
th_count = conn.execute("SELECT COUNT(*) FROM training_history").fetchone()[0]
print(f"  training_history: {th_count} rows")
conn.close()

for name, _, _, folder in MODEL_DEFS:
    pkl = f"D:/AI/AI_engine/r_layer/{folder}/model.pkl"
    exists = os.path.exists(pkl)
    size = os.path.getsize(pkl) / 1e6 if exists else 0
    print(f"  {name}: {'OK' if exists else 'MISSING'} ({size:.1f} MB)")

# ================================================================
# STEP 4: Backup Plan A
# ================================================================
print(f"\n{'=' * 65}")
print("STEP 4: Backup Plan A")
print("=" * 65)

plan_dir = r"D:\AI\AI_data\plans\plan_a"
os.makedirs(plan_dir, exist_ok=True)

for src, dst_name in [
    (MODELS_DB, "models.db"),
]:
    dst = os.path.join(plan_dir, dst_name)
    shutil.copy2(src, dst)
    print(f"  {dst_name}: {os.path.getsize(dst)/1e6:.1f} MB")

model_plan_dir = os.path.join(plan_dir, "models")
os.makedirs(model_plan_dir, exist_ok=True)
for name, _, _, folder in MODEL_DEFS:
    src = f"D:/AI/AI_engine/r_layer/{folder}/model.pkl"
    if os.path.exists(src):
        shutil.copy2(src, os.path.join(model_plan_dir, f"{name}.pkl"))
        print(f"  {name}.pkl: {os.path.getsize(src)/1e6:.1f} MB")

total = time.time() - t0
print(f"\nTotal: {total:.1f}s ({total/60:.1f} min)")
print("=" * 65)
