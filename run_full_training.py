"""
FULL TRAINING PIPELINE — 4 Phases
Phase TEST → Phase 1 → Phase 2 → Phase 3

Per TRAINING_PHASES.md:
  Phase TEST: 2014-03-06 → 2014-07-29 (100 days) — TEST
  Phase 1:    2014-07-30 → 2016-12-30 (608 days) — TRAIN
  Phase 2:    2017-01-03 → 2019-12-31 (748 days) — FINE-TUNE
  Phase 3:    2020-01-02 → 2026-03-13 (1544 days) — FINE-TUNE → PRODUCTION
"""
import sqlite3, time, sys, traceback
sys.path.insert(0, r"D:\AI")
sys.path.insert(0, r"D:\AI\data")

MARKET_DB = r"D:\AI\AI_data\market.db"
SIGNALS_DB = r"D:\AI\AI_data\signals.db"
MODELS_DB = r"D:\AI\AI_data\models.db"

PHASES = [
    ("Phase TEST", "2014-03-06", "2014-07-29"),
    ("Phase 1 NEN", "2014-07-30", "2016-12-30"),
    ("Phase 2 TANG TRUONG", "2017-01-03", "2019-12-31"),
    ("Phase 3 HIEN DAI", "2020-01-02", "2026-03-13"),
]

# ---------------------------------------------------------------------------
# Expert runner
# ---------------------------------------------------------------------------

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


def get_symbols():
    conn = sqlite3.connect(MARKET_DB)
    syms = [r[0] for r in conn.execute("SELECT symbol FROM symbols_master ORDER BY symbol").fetchall()]
    conn.close()
    return syms


def get_trading_dates(start, end):
    conn = sqlite3.connect(MARKET_DB)
    dates = [r[0] for r in conn.execute(
        "SELECT DISTINCT date FROM prices_daily WHERE symbol='VNINDEX' AND date>=? AND date<=? ORDER BY date",
        (start, end),
    ).fetchall()]
    conn.close()
    return dates


def run_experts_for_date(date, symbols):
    """Run all 20 experts for a single date."""
    from AI_engine.experts.market_context.v4reg.regime_writer import RegimeWriter
    RegimeWriter(MARKET_DB).run(date)

    for eid, modpath, clsname in EXPERT_IMPORTS:
        try:
            mod = __import__(modpath, fromlist=[clsname])
            cls = getattr(mod, clsname)
            w = cls(MARKET_DB, SIGNALS_DB)
            w.run_all(date, symbols=symbols)
        except Exception:
            pass

    from AI_engine.experts.market_context.v4br.expert_writer import BreadthExpertWriter
    try:
        BreadthExpertWriter(MARKET_DB, SIGNALS_DB).run(date)
    except Exception:
        pass


def run_meta_for_date(date):
    from AI_engine.meta_layer.feature_matrix_writer import FeatureMatrixWriter
    fw = FeatureMatrixWriter(SIGNALS_DB, MARKET_DB)
    fw.run(date)


def train_r_models(train_start, train_end):
    """Train R0-R5 on date range. Returns metrics dict."""
    results = {}
    for model_name, module_path, class_name in [
        ("R0", "AI_engine.r_layer.r0_baseline.model", "R0Model"),
        ("R1", "AI_engine.r_layer.r1_linear.model", "R1Model"),
        ("R2", "AI_engine.r_layer.r2_rf.model", "R2Model"),
        ("R3", "AI_engine.r_layer.r3_gbdt.model", "R3Model"),
        ("R4", "AI_engine.r_layer.r4_regime.model", "R4Model"),
        ("R5", "AI_engine.r_layer.r5_sector.model", "R5Model"),
    ]:
        try:
            mod = __import__(module_path, fromlist=[class_name])
            cls = getattr(mod, class_name)
            m = cls(SIGNALS_DB, MODELS_DB, MARKET_DB)
            horizon = 20 if model_name == "R4" else 5
            metrics = m.train(train_start, train_end, horizon=horizon)
            results[model_name] = metrics

            # Save model
            model_dir = f"D:/AI/AI_engine/r_layer/{model_name.lower()}_{'baseline' if model_name=='R0' else 'linear' if model_name=='R1' else 'rf' if model_name=='R2' else 'gbdt' if model_name=='R3' else 'regime' if model_name=='R4' else 'sector'}"
            try:
                m.save_model(f"{model_dir}/model.pkl")
            except Exception:
                pass

        except Exception as e:
            results[model_name] = {"error": str(e)}

    return results


def predict_and_write(predict_date, symbols):
    """Run R0-R5 predictions + ensemble + master summary + X1."""
    for model_name, module_path, class_name in [
        ("R0", "AI_engine.r_layer.r0_baseline.model", "R0Model"),
        ("R1", "AI_engine.r_layer.r1_linear.model", "R1Model"),
        ("R2", "AI_engine.r_layer.r2_rf.model", "R2Model"),
        ("R3", "AI_engine.r_layer.r3_gbdt.model", "R3Model"),
        ("R4", "AI_engine.r_layer.r4_regime.model", "R4Model"),
        ("R5", "AI_engine.r_layer.r5_sector.model", "R5Model"),
    ]:
        try:
            mod = __import__(module_path, fromlist=[class_name])
            cls = getattr(mod, class_name)
            m = cls(SIGNALS_DB, MODELS_DB, MARKET_DB)
            model_suffix = {'R0': 'baseline', 'R1': 'linear', 'R2': 'rf', 'R3': 'gbdt', 'R4': 'regime', 'R5': 'sector'}
            model_path = f"D:/AI/AI_engine/r_layer/{model_name.lower()}_{model_suffix[model_name]}/model.pkl"
            try:
                m.load_model(model_path)
            except Exception:
                pass
            if m.model is not None:
                preds = m.predict(predict_date, symbols=symbols)
                if preds:
                    m.write_predictions(preds)
        except Exception:
            pass

    # Ensemble
    from AI_engine.r_layer.ensemble import EnsembleEngine
    EnsembleEngine(MODELS_DB).compute_ensemble(predict_date)

    # Master Summary
    from AI_engine.r_layer.master_summary import MasterSummary
    MasterSummary(MODELS_DB).compute(predict_date)

    # X1
    from AI_engine.x1.portfolio_engine import PortfolioEngine
    from AI_engine.x1.output_writer import OutputWriter
    pe = PortfolioEngine(MODELS_DB, MARKET_DB)
    portfolio = pe.build(predict_date)
    stats = OutputWriter(MODELS_DB).write(portfolio)
    return stats


# ---------------------------------------------------------------------------
# MAIN TRAINING LOOP
# ---------------------------------------------------------------------------

symbols = get_symbols()
overall_t0 = time.time()
all_results = {}

for phase_name, phase_start, phase_end in PHASES:
    print("\n" + "=" * 70)
    print(f"  {phase_name}: {phase_start} -> {phase_end}")
    print("=" * 70)
    phase_t0 = time.time()

    dates = get_trading_dates(phase_start, phase_end)
    print(f"  Trading days: {len(dates)}")

    # --- Run experts for sampled dates (every 5th day to save time) ---
    sample_dates = dates[::5] + [dates[-1]]  # every 5th + last
    sample_dates = sorted(set(sample_dates))
    print(f"  Running experts for {len(sample_dates)} sampled dates...")

    expert_t0 = time.time()
    for i, d in enumerate(sample_dates):
        run_experts_for_date(d, symbols)
        run_meta_for_date(d)
        if (i + 1) % 20 == 0:
            print(f"    [{i+1}/{len(sample_dates)}] {d}")
    print(f"  Experts done: {time.time()-expert_t0:.1f}s")

    # --- Count signals ---
    conn = sqlite3.connect(SIGNALS_DB)
    sig_count = conn.execute(
        "SELECT COUNT(*) FROM expert_signals WHERE date>=? AND date<=?",
        (phase_start, phase_end),
    ).fetchone()[0]
    meta_count = conn.execute(
        "SELECT COUNT(*) FROM meta_features WHERE date>=? AND date<=?",
        (phase_start, phase_end),
    ).fetchone()[0]
    conn.close()
    print(f"  Signals: {sig_count}, Meta features: {meta_count}")

    # --- Determine training range ---
    # For each phase, train on all data from start of data up to phase end
    # This is expanding window: Phase 1 trains on TEST+Phase1, Phase 2 on TEST+1+2, etc.
    cumulative_start = "2014-03-06"  # always start from beginning
    train_end = phase_end

    print(f"  Training R0-R5 on {cumulative_start} -> {train_end}...")
    train_t0 = time.time()
    r_metrics = train_r_models(cumulative_start, train_end)
    print(f"  Training done: {time.time()-train_t0:.1f}s")

    for model_name, metrics in r_metrics.items():
        if "error" in metrics:
            status = f"FAIL: {metrics['error']}"
        else:
            samples = metrics.get("samples", "?")
            acc = metrics.get("accuracy", metrics.get("r2", metrics.get("mse", "?")))
            status = f"OK ({samples} samples, metric={acc})"
        print(f"    {model_name}: {status}")

    # --- Predict on last date of phase ---
    predict_date = dates[-1]
    print(f"  Predicting on {predict_date}...")
    try:
        run_experts_for_date(predict_date, symbols)
        run_meta_for_date(predict_date)
        x1_stats = predict_and_write(predict_date, symbols)
        print(f"  X1: BUY={x1_stats['buys']}, SELL={x1_stats['sells']}, HOLD={x1_stats['holds']}")
        print(f"  Buy weight: {x1_stats['total_buy_weight']:.1%}, Cash: {x1_stats['cash_weight']:.1%}")
    except Exception as e:
        print(f"  Prediction FAIL: {e}")
        traceback.print_exc()

    phase_time = time.time() - phase_t0
    print(f"  Phase time: {phase_time:.1f}s")
    all_results[phase_name] = {
        "dates": len(dates),
        "signals": sig_count,
        "r_metrics": r_metrics,
        "time": round(phase_time, 1),
    }

# ---------------------------------------------------------------------------
# FINAL REPORT
# ---------------------------------------------------------------------------
total_time = time.time() - overall_t0
print("\n" + "=" * 70)
print("  FULL TRAINING COMPLETE")
print("=" * 70)

for phase_name, result in all_results.items():
    r_ok = sum(1 for m in result["r_metrics"].values() if "error" not in m)
    print(f"  {phase_name}: {result['dates']} days, {result['signals']} signals, {r_ok}/6 models, {result['time']}s")

print(f"\n  Total time: {total_time:.1f}s ({total_time/60:.1f} minutes)")
print("=" * 70)
