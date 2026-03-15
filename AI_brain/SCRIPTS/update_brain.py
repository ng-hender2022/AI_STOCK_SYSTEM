"""
AI_STOCK Brain Update Script
Validates Brain documents and checks Brain-Code sync.
"""

import os
import sqlite3
from datetime import datetime
from pathlib import Path

BRAIN_ROOT = Path(r"D:\AI\AI_brain")
DATA_ROOT = Path(r"D:\AI\AI_data")
ENGINE_ROOT = Path(r"D:\AI\AI_engine")

# Expected Brain structure
EXPECTED_STRUCTURE = {
    "SYSTEM": [
        "AI_STOCK_GLOBAL_ARCHITECTURE.md",
        "AI_STOCK_BRAIN_PROTOCOL.md",
        "AI_STOCK_DB_SCHEMA_MASTER.md",
        "AI_STOCK_DATA_PIPELINE_SPEC.md",
    ],
    "SYSTEM/KNOWLEDGE": [
        "ICHIMOKU_RULEBOOK.md",
        "MA_RULEBOOK.md",
        "ADX_RULEBOOK.md",
        "MACD_RULEBOOK.md",
        "RSI_RULEBOOK.md",
        "STOCHASTIC_RULEBOOK.md",
        "VOLUME_RULEBOOK.md",
        "OBV_RULEBOOK.md",
        "ATR_RULEBOOK.md",
        "BOLLINGER_RULEBOOK.md",
        "PRICE_ACTION_RULEBOOK.md",
        "CANDLE_RULEBOOK.md",
        "BREADTH_RULEBOOK.md",
        "RS_RULEBOOK.md",
        "REGIME_RULEBOOK.md",
        "SECTOR_RULEBOOK.md",
        "LIQUIDITY_RULEBOOK.md",
    ],
    "EXPERTS": [
        "EXPERT_LIST.md",
        "EXPERT_PROTOCOL.md",
        "SIGNAL_CODEBOOK.md",
    ],
    "REPORTS": [
        "CURRENT_SYSTEM_STATE.md",
        "MODEL_PERFORMANCE.md",
        "SYSTEM_HEALTH.md",
    ],
    "SNAPSHOTS": [
        "SYSTEM_SNAPSHOT.md",
    ],
    "CLAUDE": [
        "CLAUDE_OPERATING_PROTOCOL.md",
        "SAFE_EDIT_RULES.md",
    ],
    "CHANGELOG": [
        "CHANGELOG.md",
    ],
}

EXPECTED_DBS = ["market.db", "signals.db", "models.db", "audit.db"]

EXPECTED_ENGINE_DIRS = ["experts", "r_layer", "x1"]


def check_brain_structure():
    """Check all expected Brain files exist."""
    print("=" * 60)
    print("BRAIN STRUCTURE CHECK")
    print("=" * 60)

    missing = []
    found = 0

    for folder, files in EXPECTED_STRUCTURE.items():
        folder_path = BRAIN_ROOT / folder
        for f in files:
            file_path = folder_path / f
            if file_path.exists():
                found += 1
                print(f"  [OK] {folder}/{f}")
            else:
                missing.append(f"{folder}/{f}")
                print(f"  [MISSING] {folder}/{f}")

    total = found + len(missing)
    print(f"\nResult: {found}/{total} files found")
    if missing:
        print(f"Missing: {len(missing)} files")
    return missing


def check_databases():
    """Check database files exist."""
    print("\n" + "=" * 60)
    print("DATABASE CHECK")
    print("=" * 60)

    for db_name in EXPECTED_DBS:
        db_path = DATA_ROOT / db_name
        if db_path.exists():
            size = db_path.stat().st_size
            print(f"  [OK] {db_name} ({size} bytes)")

            # Check tables
            try:
                conn = sqlite3.connect(str(db_path))
                cursor = conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                )
                tables = [row[0] for row in cursor.fetchall()]
                conn.close()
                if tables:
                    print(f"       Tables: {', '.join(tables)}")
                else:
                    print("       Tables: (none)")
            except Exception as e:
                print(f"       Error reading: {e}")
        else:
            print(f"  [MISSING] {db_name}")


def check_engine():
    """Check engine directory structure."""
    print("\n" + "=" * 60)
    print("ENGINE CHECK")
    print("=" * 60)

    for dir_name in EXPECTED_ENGINE_DIRS:
        dir_path = ENGINE_ROOT / dir_name
        if dir_path.exists():
            files = list(dir_path.glob("*.py"))
            print(f"  [OK] {dir_name}/ ({len(files)} .py files)")
        else:
            print(f"  [MISSING] {dir_name}/")


def main():
    print(f"AI_STOCK Brain Update Check")
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Brain root: {BRAIN_ROOT}")
    print()

    missing = check_brain_structure()
    check_databases()
    check_engine()

    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    if not missing:
        print("All Brain documents present.")
    else:
        print(f"Action needed: {len(missing)} missing Brain documents")


if __name__ == "__main__":
    main()
