"""
Run 20 experts + Meta Layer on ALL 3000 trading days.
Populates signals.db with full expert signals + meta features.
Then runs X1 predictions on last date.
"""
import sqlite3, time, sys
sys.path.insert(0, r"D:\AI")
sys.path.insert(0, r"D:\AI\data")

MARKET_DB = r"D:\AI\AI_data\market.db"
SIGNALS_DB = r"D:\AI\AI_data\signals.db"
MODELS_DB = r"D:\AI\AI_data\models.db"

# Get all trading dates
conn = sqlite3.connect(MARKET_DB)
all_dates = [r[0] for r in conn.execute(
    "SELECT DISTINCT date FROM prices_daily WHERE symbol='VNINDEX' ORDER BY date"
).fetchall()]
symbols = [r[0] for r in conn.execute("SELECT symbol FROM symbols_master ORDER BY symbol").fetchall()]
conn.close()

print(f"Total dates: {len(all_dates)}, Symbols: {len(symbols)}")

# Check which dates already have meta_features
conn = sqlite3.connect(SIGNALS_DB)
done_dates = set(r[0] for r in conn.execute("SELECT DISTINCT date FROM meta_features").fetchall())
conn.close()

todo_dates = [d for d in all_dates if d not in done_dates]
print(f"Already done: {len(done_dates)}, Todo: {len(todo_dates)}")

# Expert imports
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

from AI_engine.experts.market_context.v4reg.regime_writer import RegimeWriter
from AI_engine.experts.market_context.v4br.expert_writer import BreadthExpertWriter
from AI_engine.meta_layer.feature_matrix_writer import FeatureMatrixWriter

fw = FeatureMatrixWriter(SIGNALS_DB, MARKET_DB)

t0 = time.time()
for i, d in enumerate(todo_dates):
    # V4REG
    RegimeWriter(MARKET_DB).run(d)

    # Per-symbol experts
    for eid, modpath, clsname in EXPERT_IMPORTS:
        try:
            mod = __import__(modpath, fromlist=[clsname])
            cls = getattr(mod, clsname)
            w = cls(MARKET_DB, SIGNALS_DB)
            w.run_all(d, symbols=symbols)
        except Exception:
            pass

    # V4BR
    try:
        BreadthExpertWriter(MARKET_DB, SIGNALS_DB).run(d)
    except Exception:
        pass

    # Meta Layer
    fw.run(d)

    if (i + 1) % 50 == 0:
        elapsed = time.time() - t0
        rate = (i + 1) / elapsed
        remaining = (len(todo_dates) - i - 1) / rate if rate > 0 else 0
        print(f"  [{i+1}/{len(todo_dates)}] {d} | {elapsed:.0f}s elapsed, ~{remaining:.0f}s remaining")

elapsed = time.time() - t0
print(f"\nExperts + Meta done: {len(todo_dates)} dates in {elapsed:.1f}s ({elapsed/60:.1f} min)")

# Final counts
conn = sqlite3.connect(SIGNALS_DB)
sig_total = conn.execute("SELECT COUNT(*) FROM expert_signals").fetchone()[0]
meta_total = conn.execute("SELECT COUNT(*) FROM meta_features").fetchone()[0]
meta_dates = conn.execute("SELECT COUNT(DISTINCT date) FROM meta_features").fetchone()[0]
conn.close()
print(f"Total signals: {sig_total}, Meta features: {meta_total}, Meta dates: {meta_dates}")

# Run X1 on last date
print(f"\nRunning X1 on {all_dates[-1]}...")
from AI_engine.r_layer.ensemble import EnsembleEngine
from AI_engine.r_layer.master_summary import MasterSummary
from AI_engine.x1.portfolio_engine import PortfolioEngine
from AI_engine.x1.output_writer import OutputWriter

# Load models and predict
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
        suffix = {'R0':'baseline','R1':'linear','R2':'rf','R3':'gbdt','R4':'regime','R5':'sector'}
        m.load_model(f"D:/AI/AI_engine/r_layer/{model_name.lower()}_{suffix[model_name]}/model.pkl")
        preds = m.predict(all_dates[-1], symbols=symbols)
        if preds:
            m.write_predictions(preds)
            print(f"  {model_name}: {len(preds)} predictions")
    except Exception as e:
        print(f"  {model_name}: {e}")

EnsembleEngine(MODELS_DB).compute_ensemble(all_dates[-1])
MasterSummary(MODELS_DB).compute(all_dates[-1])

pe = PortfolioEngine(MODELS_DB, MARKET_DB)
portfolio = pe.build(all_dates[-1])
stats = OutputWriter(MODELS_DB).write(portfolio)

buys = [e for e in portfolio.entries if e.action == "BUY"]
sells = [e for e in portfolio.entries if e.action == "SELL"]

print(f"\nX1 Decisions ({all_dates[-1]}):")
print(f"  BUY: {stats['buys']}, SELL: {stats['sells']}, HOLD: {stats['holds']}")
print(f"  Buy weight: {stats['total_buy_weight']:.1%}, Cash: {stats['cash_weight']:.1%}")

if buys:
    print(f"  Top BUY:")
    for b in sorted(buys, key=lambda x: x.score, reverse=True)[:10]:
        print(f"    {b.symbol}: score={b.score:.2f}, weight={b.weight:.1%}, {b.strength}")

if sells:
    print(f"  Top SELL:")
    for s in sorted(sells, key=lambda x: x.score)[:5]:
        print(f"    {s.symbol}: score={s.score:.2f}, {s.strength}")

print(f"\nDONE. Total time: {time.time()-t0:.1f}s")
