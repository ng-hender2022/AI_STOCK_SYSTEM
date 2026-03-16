"""
Retrain R0-R7 on full 3000 days, save models, backup Plan A.
"""
import sqlite3, time, sys, shutil, os
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, r"D:\AI")
sys.path.insert(0, r"D:\AI\data")

MARKET_DB = r"D:\AI\AI_data\market.db"
SIGNALS_DB = r"D:\AI\AI_data\signals.db"
MODELS_DB = r"D:\AI\AI_data\models.db"
TRAIN_START = "2014-03-06"
TRAIN_END = "2026-03-13"

t0 = time.time()

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

print("=" * 65)
print(f"RETRAIN R0-R7: {TRAIN_START} -> {TRAIN_END}")
print("=" * 65)

for name, modpath, clsname, folder in MODEL_DEFS:
    t1 = time.time()
    try:
        mod = __import__(modpath, fromlist=[clsname])
        cls = getattr(mod, clsname)
        m = cls(SIGNALS_DB, MODELS_DB, MARKET_DB)
        horizon = 20 if name == "R4" else 5
        metrics = m.train(TRAIN_START, TRAIN_END, horizon=horizon)
        m.save_model(f"D:/AI/AI_engine/r_layer/{folder}/model.pkl")
        if "error" in metrics:
            print(f"  {name}: SKIPPED - {metrics['error']} ({time.time()-t1:.1f}s)")
        else:
            acc = metrics.get("accuracy", metrics.get("r2", metrics.get("mse", "?")))
            print(f"  {name}: OK ({metrics.get('samples','?')} samples, metric={acc}, {time.time()-t1:.1f}s)")
    except Exception as e:
        print(f"  {name}: FAIL - {e}")

# Backup Plan A
plan_dir = r"D:\AI\AI_data\plans\plan_a"
os.makedirs(os.path.join(plan_dir, "models"), exist_ok=True)
shutil.copy2(MODELS_DB, os.path.join(plan_dir, "models.db"))
for name, _, _, folder in MODEL_DEFS:
    src = f"D:/AI/AI_engine/r_layer/{folder}/model.pkl"
    if os.path.exists(src):
        shutil.copy2(src, os.path.join(plan_dir, "models", f"{name}.pkl"))

total = time.time() - t0
print(f"\nTotal: {total:.1f}s ({total/60:.1f} min)")
print(f"Plan A backed up to {plan_dir}")
