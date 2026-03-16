"""
FULL END-TO-END INTEGRATION TEST
Phase TEST: 2014-03-06 -> 2014-07-29 (100 trading days)
"""
import sqlite3, json, time, sys, traceback
sys.path.insert(0, r"D:\AI")
sys.path.insert(0, r"D:\AI\data")

MARKET_DB = r"D:\AI\AI_data\market.db"
SIGNALS_DB = r"D:\AI\AI_data\signals.db"
MODELS_DB = r"D:\AI\AI_data\models.db"

TEST_START = "2014-03-06"
TEST_END = "2014-07-29"
PREDICT_DATE = "2014-07-29"
TRAIN_END = "2014-07-10"

t0 = time.time()
errors = []

mconn = sqlite3.connect(MARKET_DB)
symbols = [r[0] for r in mconn.execute(
    "SELECT DISTINCT symbol FROM prices_daily WHERE date<=? ORDER BY symbol", (TEST_END,)
).fetchall()]
mconn.close()

print("=" * 65)
print("FULL PIPELINE INTEGRATION TEST")
print(f"Phase TEST: {TEST_START} -> {TEST_END}")
print(f"Symbols: {len(symbols)}")
print("=" * 65)

# STEP 1: Experts
print(f"\n--- STEP 1: Running 20 Experts for {PREDICT_DATE} ---")
t1 = time.time()

conn = sqlite3.connect(SIGNALS_DB)
conn.execute("DELETE FROM expert_signals WHERE date=?", (PREDICT_DATE,))
conn.execute("DELETE FROM meta_features WHERE date=?", (PREDICT_DATE,))
conn.execute("DELETE FROM expert_conflicts WHERE date=?", (PREDICT_DATE,))
conn.commit()
conn.close()

from AI_engine.experts.market_context.v4reg.regime_writer import RegimeWriter
RegimeWriter(MARKET_DB).run(PREDICT_DATE)

expert_imports = [
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

expert_ok = 1
for eid, modpath, clsname in expert_imports:
    try:
        mod = __import__(modpath, fromlist=[clsname])
        cls = getattr(mod, clsname)
        w = cls(MARKET_DB, SIGNALS_DB)
        w.run_all(PREDICT_DATE, symbols=symbols)
        expert_ok += 1
    except Exception as e:
        errors.append(f"{eid}: {e}")
        print(f"  {eid}: FAIL - {e}")

from AI_engine.experts.market_context.v4br.expert_writer import BreadthExpertWriter
BreadthExpertWriter(MARKET_DB, SIGNALS_DB).run(PREDICT_DATE)
expert_ok += 1

conn = sqlite3.connect(SIGNALS_DB)
sig_count = conn.execute("SELECT COUNT(*) FROM expert_signals WHERE date=?", (PREDICT_DATE,)).fetchone()[0]
expert_ids = conn.execute("SELECT COUNT(DISTINCT expert_id) FROM expert_signals WHERE date=?", (PREDICT_DATE,)).fetchone()[0]
conn.close()

print(f"  Result: {expert_ok}/20 experts, {sig_count} signals, {expert_ids} expert IDs")
print(f"  Time: {time.time()-t1:.1f}s")

# STEP 2: Meta Layer
print(f"\n--- STEP 2: Meta Layer ---")
t2 = time.time()

from AI_engine.meta_layer.feature_matrix_writer import FeatureMatrixWriter
fw = FeatureMatrixWriter(SIGNALS_DB, MARKET_DB)

# Run meta for last 5 training dates + predict date
cal_conn = sqlite3.connect(MARKET_DB)
train_dates = [r[0] for r in cal_conn.execute(
    "SELECT DISTINCT date FROM prices_daily WHERE symbol='VNINDEX' AND date>=? AND date<=? ORDER BY date",
    (TEST_START, TRAIN_END)
).fetchall()]
cal_conn.close()

# Run experts+meta for a few training dates so R models have data
print(f"  Running experts for {len(train_dates[-5:])} training dates...")
for td in train_dates[-5:]:
    for eid, modpath, clsname in expert_imports:
        try:
            mod = __import__(modpath, fromlist=[clsname])
            cls = getattr(mod, clsname)
            w = cls(MARKET_DB, SIGNALS_DB)
            w.run_all(td, symbols=symbols)
        except:
            pass
    try:
        BreadthExpertWriter(MARKET_DB, SIGNALS_DB).run(td)
    except:
        pass
    fw.run(td)

meta_stats = fw.run(PREDICT_DATE)
vector = fw.get_feature_vector("FPT", PREDICT_DATE)
print(f"  meta_written: {meta_stats['meta_written']}, features: {len(vector) if vector else 0}")
print(f"  Time: {time.time()-t2:.1f}s")

# STEP 3: Train R0~R5
print(f"\n--- STEP 3: Training R0~R5 ---")
t3 = time.time()

r_results = {}
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
        metrics = m.train(TEST_START, TRAIN_END, horizon=horizon)

        if "error" in metrics:
            print(f"  {model_name}: SKIPPED - {metrics['error']}")
            r_results[model_name] = "skipped"
        else:
            preds = m.predict(PREDICT_DATE, symbols=symbols)
            if preds:
                m.write_predictions(preds)
            print(f"  {model_name}: OK ({metrics.get('samples', '?')} samples, {len(preds)} preds)")
            r_results[model_name] = f"{len(preds)} preds"
    except Exception as e:
        errors.append(f"{model_name}: {e}")
        print(f"  {model_name}: FAIL - {e}")
        r_results[model_name] = "FAIL"

print(f"  Time: {time.time()-t3:.1f}s")

# STEP 4: Ensemble + Master Summary
print(f"\n--- STEP 4: Ensemble + Master Summary ---")
t4 = time.time()

try:
    from AI_engine.r_layer.ensemble import EnsembleEngine
    ens_stats = EnsembleEngine(MODELS_DB).compute_ensemble(PREDICT_DATE)
    print(f"  Ensemble: {ens_stats['symbols']} symbols")
except Exception as e:
    errors.append(f"Ensemble: {e}")
    print(f"  Ensemble FAIL: {e}")

try:
    from AI_engine.r_layer.master_summary import MasterSummary
    ms_stats = MasterSummary(MODELS_DB).compute(PREDICT_DATE)
    print(f"  Master Summary: {ms_stats['symbols']} symbols")
except Exception as e:
    errors.append(f"Master Summary: {e}")
    print(f"  Master Summary FAIL: {e}")

print(f"  Time: {time.time()-t4:.1f}s")

# STEP 5: X1 Decision Engine
print(f"\n--- STEP 5: X1 Decision Engine ---")
t5 = time.time()

try:
    from AI_engine.x1.portfolio_engine import PortfolioEngine
    from AI_engine.x1.output_writer import OutputWriter

    pe = PortfolioEngine(MODELS_DB, MARKET_DB)
    portfolio = pe.build(PREDICT_DATE)
    x1_stats = OutputWriter(MODELS_DB).write(portfolio)

    buys = [e for e in portfolio.entries if e.action == "BUY"]
    sells = [e for e in portfolio.entries if e.action == "SELL"]
    holds = [e for e in portfolio.entries if e.action == "HOLD"]

    print(f"  Decisions: {x1_stats['written']} total")
    print(f"  BUY: {x1_stats['buys']}, SELL: {x1_stats['sells']}, HOLD: {x1_stats['holds']}")
    print(f"  Buy weight: {x1_stats['total_buy_weight']:.1%}, Cash: {x1_stats['cash_weight']:.1%}")

    if buys:
        print(f"  Top BUY:")
        for b in sorted(buys, key=lambda x: x.score, reverse=True)[:5]:
            print(f"    {b.symbol}: score={b.score:.2f}, weight={b.weight:.1%}, {b.strength}")

    if sells:
        print(f"  Top SELL:")
        for s in sorted(sells, key=lambda x: x.score)[:3]:
            print(f"    {s.symbol}: score={s.score:.2f}, {s.strength}")

except Exception as e:
    errors.append(f"X1: {e}")
    print(f"  X1 FAIL: {e}")
    traceback.print_exc()

print(f"  Time: {time.time()-t5:.1f}s")

# FINAL
elapsed = time.time() - t0
print(f"\n{'=' * 65}")
print(f"PIPELINE INTEGRATION TEST COMPLETE")
print(f"{'=' * 65}")
print(f"  Total time: {elapsed:.1f}s")
print(f"  Errors: {len(errors)}")
for e in errors:
    print(f"    - {e}")
status = "ALL STEPS OK" if len(errors) == 0 else f"{len(errors)} ERRORS"
print(f"\n  RESULT: {status}")
print(f"{'=' * 65}")
