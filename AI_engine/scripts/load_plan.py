"""
Load Plan - Restore a backed-up plan (databases + models).

Usage:
    python load_plan.py --plan plan_a
    python load_plan.py --plan plan_a --dry-run
"""

import argparse
import os
import shutil
import sqlite3
import sys

sys.stdout.reconfigure(encoding="utf-8")

BASE_DIR = r"D:\AI"
DATA_DIR = os.path.join(BASE_DIR, "AI_data")
PLANS_DIR = os.path.join(DATA_DIR, "plans")
ENGINE_DIR = os.path.join(BASE_DIR, "AI_engine")

MODEL_TARGETS = {
    "R0": os.path.join(ENGINE_DIR, "r_layer", "r0_baseline", "model.pkl"),
    "R2": os.path.join(ENGINE_DIR, "r_layer", "r2_rf", "model.pkl"),
    "R3": os.path.join(ENGINE_DIR, "r_layer", "r3_gbdt", "model.pkl"),
    "R4": os.path.join(ENGINE_DIR, "r_layer", "r4_regime", "model.pkl"),
    "R5": os.path.join(ENGINE_DIR, "r_layer", "r5_sector", "model.pkl"),
    "R6": os.path.join(ENGINE_DIR, "r_layer", "r6_xgboost", "model.pkl"),
    "R7": os.path.join(ENGINE_DIR, "r_layer", "r7_catboost", "model.pkl"),
}

DB_FILES = ["models.db", "signals.db", "market.db"]


def verify_schema(db_path: str, table: str, required_cols: list[str]) -> list[str]:
    """Check if a table has required columns. Returns list of missing columns."""
    conn = sqlite3.connect(db_path)
    existing = {r[1] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()}
    conn.close()
    return [c for c in required_cols if c not in existing]


def get_db_stats(db_path: str) -> dict:
    """Get row counts for key tables."""
    stats = {}
    conn = sqlite3.connect(db_path)
    for table in ["expert_signals", "meta_features", "training_labels",
                   "r_predictions", "training_history", "prices_daily",
                   "symbols_master", "market_regime"]:
        try:
            n = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            stats[table] = n
        except Exception:
            pass
    conn.close()
    return stats


def main():
    parser = argparse.ArgumentParser(description="Restore a backed-up plan")
    parser.add_argument("--plan", required=True, help="Plan name (e.g. plan_a)")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be done without copying")
    parser.add_argument("--skip-db", action="store_true", help="Skip database restore, only restore models")
    args = parser.parse_args()

    plan_dir = os.path.join(PLANS_DIR, args.plan)
    if not os.path.isdir(plan_dir):
        print(f"ERROR: Plan directory not found: {plan_dir}")
        sys.exit(1)

    print(f"{'=' * 60}")
    print(f"RESTORE PLAN: {args.plan}")
    print(f"Source: {plan_dir}")
    print(f"Mode: {'DRY RUN' if args.dry_run else 'LIVE'}")
    print(f"{'=' * 60}")

    # --- Spec file ---
    spec_path = os.path.join(plan_dir, "PLAN_A_SPEC.md")
    if os.path.exists(spec_path):
        print(f"\nSpec file: {spec_path} (found)")
    else:
        print(f"\nSpec file: NOT FOUND (non-critical)")

    # --- Databases ---
    if not args.skip_db:
        print(f"\n--- Databases ---")
        for db in DB_FILES:
            src = os.path.join(plan_dir, db)
            dst = os.path.join(DATA_DIR, db)
            if os.path.exists(src):
                size_mb = os.path.getsize(src) / (1024 * 1024)
                print(f"  {db}: {size_mb:.1f} MB", end="")

                # Verify schema for signals.db
                if db == "signals.db":
                    missing = verify_schema(src, "meta_features", [
                        "trend_alignment_score", "bull_bear_ratio", "breakout_count"
                    ])
                    if missing:
                        print(f" [WARNING: missing columns: {missing}]", end="")
                    else:
                        print(f" [schema OK]", end="")

                    stats = get_db_stats(src)
                    if stats:
                        parts = [f"{k}={v:,}" for k, v in sorted(stats.items()) if v > 0]
                        print(f"\n    Tables: {', '.join(parts)}", end="")

                if args.dry_run:
                    print(f" → WOULD COPY to {dst}")
                else:
                    shutil.copy2(src, dst)
                    print(f" → COPIED to {dst}")
            else:
                print(f"  {db}: NOT FOUND in backup (skipping)")
    else:
        print(f"\n--- Databases: SKIPPED (--skip-db) ---")

    # --- Model files ---
    print(f"\n--- Models ---")
    models_dir = os.path.join(plan_dir, "models")
    restored = 0
    for model_id, target_path in sorted(MODEL_TARGETS.items()):
        src = os.path.join(models_dir, f"{model_id}.pkl")
        if os.path.exists(src):
            size_kb = os.path.getsize(src) / 1024
            if args.dry_run:
                print(f"  {model_id}: {size_kb:.0f} KB → WOULD COPY to {target_path}")
            else:
                os.makedirs(os.path.dirname(target_path), exist_ok=True)
                shutil.copy2(src, target_path)
                print(f"  {model_id}: {size_kb:.0f} KB → COPIED")
                restored += 1
        else:
            print(f"  {model_id}: NOT FOUND in backup")

    # --- Source code backup ---
    code_dir = os.path.join(plan_dir, "code")
    if os.path.isdir(code_dir):
        print(f"\n--- Source code backup ---")
        for root, dirs, files in os.walk(code_dir):
            rel = os.path.relpath(root, code_dir)
            py_files = [f for f in files if f.endswith(".py") or f.endswith(".yaml") or f.endswith(".md")]
            if py_files:
                print(f"  {rel}: {len(py_files)} files")

    # --- Summary ---
    print(f"\n{'=' * 60}")
    if args.dry_run:
        print("DRY RUN complete. No files were modified.")
    else:
        print(f"RESTORE COMPLETE: {restored} models restored")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
