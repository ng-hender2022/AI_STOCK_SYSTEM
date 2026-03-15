"""
Vdata CLI — AI_STOCK Data Pipeline

Usage:
    python run.py --import-ami PATH          Import AmiBroker CSV
    python run.py --import-ami-dir PATH      Import all CSVs in directory
    python run.py --import-calendar PATH     Build trading calendar from CSV
    python run.py --update                   Update from vnstock API
    python run.py --update-intraday          Update intraday from vnstock
    python run.py --normalize                Normalize all data
    python run.py --validate                 Validate data quality
    python run.py --check-leakage TRAIN_END VAL_START
                                             Check for data leakage
    python run.py --build-calendar-from-db   Build calendar from existing VNINDEX data
    python run.py --labels SYMBOL START END  Compute labels for a symbol

Multiple flags can be combined. They execute in logical order.
"""

import argparse
import sys
from pathlib import Path

MARKET_DB = Path(r"D:\AI\AI_data\market.db")
SIGNALS_DB = Path(r"D:\AI\AI_data\signals.db")


def main():
    parser = argparse.ArgumentParser(
        description="Vdata — AI_STOCK Data Pipeline Tool"
    )
    parser.add_argument("--import-ami", metavar="PATH",
                        help="Import AmiBroker CSV file")
    parser.add_argument("--import-ami-dir", metavar="PATH",
                        help="Import all CSVs from directory")
    parser.add_argument("--import-calendar", metavar="PATH",
                        help="Build trading calendar from VNINDEX CSV")
    parser.add_argument("--build-calendar-from-db", action="store_true",
                        help="Build calendar from existing VNINDEX data in DB")
    parser.add_argument("--update", action="store_true",
                        help="Update daily data from vnstock API")
    parser.add_argument("--update-intraday", action="store_true",
                        help="Update intraday data from vnstock API")
    parser.add_argument("--normalize", action="store_true",
                        help="Normalize data (dates, numerics, symbols)")
    parser.add_argument("--validate", action="store_true",
                        help="Validate data quality")
    parser.add_argument("--check-leakage", nargs=2,
                        metavar=("TRAIN_END", "VAL_START"),
                        help="Check data leakage before training")
    parser.add_argument("--labels", nargs=3,
                        metavar=("SYMBOL", "START", "END"),
                        help="Compute labels for symbol in date range")

    args = parser.parse_args()

    if len(sys.argv) == 1:
        parser.print_help()
        return

    # --- Import AmiBroker ---
    if args.import_ami:
        from importers.amibroker_importer import AmiBrokerImporter
        print(f"[Vdata] Importing AmiBroker CSV: {args.import_ami}")
        importer = AmiBrokerImporter(MARKET_DB)
        stats = importer.import_file(args.import_ami)
        print(f"  Imported: {stats['imported']} rows, "
              f"Skipped: {stats['skipped']}, Errors: {stats['errors']}, "
              f"Symbols: {stats['symbols']}")

    if args.import_ami_dir:
        from importers.amibroker_importer import AmiBrokerImporter
        print(f"[Vdata] Importing directory: {args.import_ami_dir}")
        importer = AmiBrokerImporter(MARKET_DB)
        stats = importer.import_directory(args.import_ami_dir)
        print(f"  Files: {stats['files']}, Imported: {stats['imported']}, "
              f"Skipped: {stats['skipped']}, Errors: {stats['errors']}")

    # --- Calendar ---
    if args.import_calendar:
        from calendar_builder import CalendarBuilder
        print(f"[Vdata] Building calendar from: {args.import_calendar}")
        builder = CalendarBuilder(MARKET_DB)
        stats = builder.build_from_csv(args.import_calendar)
        print(f"  Dates: {stats['dates_parsed']}, "
              f"Range: {stats['date_range']}, "
              f"Master CSV: {stats['written_csv']}")

    if args.build_calendar_from_db:
        from calendar_builder import CalendarBuilder
        print("[Vdata] Building calendar from existing VNINDEX data...")
        builder = CalendarBuilder(MARKET_DB)
        stats = builder.build_from_db()
        print(f"  Dates from DB: {stats['dates_from_db']}")

    # --- Normalize ---
    if args.normalize:
        from normalizer import Normalizer
        print("[Vdata] Normalizing data...")
        norm = Normalizer(MARKET_DB)
        stats = norm.normalize_all()
        print(f"  Dates fixed: {stats['dates_fixed']}, "
              f"Numerics fixed: {stats['numerics_fixed']}, "
              f"Symbols fixed: {stats['symbols_fixed']}")

    # --- Update from vnstock ---
    if args.update:
        from importers.vnstock_updater import VnstockUpdater
        print("[Vdata] Updating daily data from vnstock...")
        updater = VnstockUpdater(MARKET_DB)
        stats = updater.update_daily()
        if "error" in stats:
            print(f"  Error: {stats['error']}")
        else:
            print(f"  Updated: {stats['updated_symbols']} symbols, "
                  f"New rows: {stats['new_rows']}, "
                  f"Errors: {len(stats['errors'])}")

    if args.update_intraday:
        from importers.vnstock_updater import VnstockUpdater
        print("[Vdata] Updating intraday data from vnstock...")
        updater = VnstockUpdater(MARKET_DB)
        stats = updater.update_intraday()
        if "error" in stats:
            print(f"  Error: {stats['error']}")
        else:
            print(f"  Updated: {stats['updated_symbols']} symbols, "
                  f"New rows: {stats['new_rows']}")

    # --- Validate ---
    if args.validate:
        from validator import Validator
        print("[Vdata] Validating data...")
        v = Validator(MARKET_DB)
        report = v.validate_all()
        print(f"  Total rows: {report.total_rows}")
        print(f"  Duplicates: {report.duplicates}")
        print(f"  Missing close: {report.missing_close}")
        print(f"  OHLC issues: {report.ohlc_inconsistencies}")
        print(f"  Spikes >15%: {report.spike_violations}")
        print(f"  Negative vol: {report.negative_volumes}")
        if report.is_clean:
            print("  Status: CLEAN")
        else:
            print("  Status: ISSUES FOUND")
            for d in report.details[:10]:
                print(f"    {d}")

    # --- Check leakage ---
    if args.check_leakage:
        from leak_checker import LeakChecker, LeakageError
        train_end, val_start = args.check_leakage
        print(f"[Vdata] Checking leakage: train_end={train_end}, val_start={val_start}")
        checker = LeakChecker(MARKET_DB, SIGNALS_DB)
        try:
            results = checker.check_all(train_end, val_start)
            for k, v in results.items():
                status = "PASS" if v["passed"] else "FAIL"
                print(f"  [{status}] {k}: {v['message']}")
            print("  All checks passed.")
        except LeakageError as e:
            print(f"  LEAKAGE DETECTED: {e}")
            sys.exit(1)

    # --- Labels ---
    if args.labels:
        from label_builder import LabelBuilder
        symbol, start, end = args.labels
        print(f"[Vdata] Computing labels: {symbol} {start} → {end}")
        lb = LabelBuilder(MARKET_DB)
        results = lb.compute_labels_range(symbol, start, end)
        print(f"  Computed {len(results)} label rows")
        for r in results[:5]:
            t1 = r.get("t1_label", "?")
            t5 = r.get("t5_label", "?")
            t10 = r.get("t10_label", "?")
            print(f"    {r['feature_date']}: T1={t1} T5={t5} T10={t10}")
        if len(results) > 5:
            print(f"    ... ({len(results) - 5} more)")


if __name__ == "__main__":
    main()
