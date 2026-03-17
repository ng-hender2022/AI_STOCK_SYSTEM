"""
Meta Builder
Reads expert_signals from signals.db, normalizes scores,
computes group averages, alignment/conflict scores.

Output: meta_features row per symbol per date.
"""

import sqlite3
import json
from dataclasses import dataclass, field
from pathlib import Path

# Expert groups — must match config.py
EXPERT_GROUPS = {
    "TREND":      ["V4I", "V4MA", "V4ADX"],
    "MOMENTUM":   ["V4MACD", "V4RSI", "V4STO"],
    "VOLUME":     ["V4V", "V4OBV"],
    "VOLATILITY": ["V4ATR", "V4BB"],
    "STRUCTURE":  ["V4P", "V4CANDLE", "V4PIVOT", "V4SR", "V4TREND_PATTERN"],
    "CONTEXT":    ["V4BR", "V4RS", "V4REG", "V4S", "V4LIQ"],
}

# Experts with 0-100 scale (need different normalization)
SCALE_0_100 = {"V4RSI", "V4STO"}
# Experts with 0-4 scale (direction-neutral)
SCALE_0_4 = {"V4ADX", "V4ATR"}

ALL_EXPERT_IDS = sorted(set(
    eid for group in EXPERT_GROUPS.values() for eid in group
))


def _normalize_score(expert_id: str, primary_score: float) -> float:
    """
    Normalize expert score to -1..+1 range for cross-expert comparison.
    - Standard experts (-4..+4): score / 4
    - RSI/STO (0..100): (score - 50) / 50
    - ADX/ATR (0..4): score / 4 (stays 0..1, no negative)
    """
    if expert_id in SCALE_0_100:
        return (primary_score - 50.0) / 50.0
    elif expert_id in SCALE_0_4:
        return primary_score / 4.0
    else:
        return primary_score / 4.0


@dataclass
class MetaFeatures:
    """Aggregated meta features for 1 symbol, 1 date."""
    symbol: str
    date: str
    snapshot_time: str = "EOD"

    # Expert counts
    bullish_expert_count: int = 0
    bearish_expert_count: int = 0
    neutral_expert_count: int = 0

    # Normalized scores per expert (dict for flexibility)
    expert_norms: dict = field(default_factory=dict)

    # Group scores (average of normalized scores in each group)
    avg_score: float = 0.0
    trend_group_score: float = 0.0
    momentum_group_score: float = 0.0
    volume_group_score: float = 0.0
    volatility_group_score: float = 0.0
    structure_group_score: float = 0.0
    context_group_score: float = 0.0

    # Conflict & alignment
    expert_conflict_score: float = 0.0   # 0=aligned, 1=max conflict
    expert_alignment_score: float = 0.0  # 0=no alignment, 1=perfect

    # Regime (from V4REG)
    regime_score: float = 0.0

    # Count of experts that contributed
    expert_count: int = 0

    # --- NEW: Expanded meta features (14 new) ---
    # Trend context
    trend_alignment_score: float = 0.0  # % of trend experts bullish (0..1)
    trend_strength_max: float = 0.0     # max abs of trend norms
    ma_alignment_pct: float = 0.0       # from V4MA metadata
    trend_persistence_avg: float = 0.0  # from V4P metadata

    # Momentum context
    momentum_divergence_count: int = 0  # count divergence flags
    overbought_count: int = 0           # experts in OB zone
    oversold_count: int = 0             # experts in OS zone

    # Volume context
    volume_pressure: float = 0.0        # V4V vol_ratio
    liquidity_shock_avg: float = 0.0    # from V4LIQ
    climax_volume_count: int = 0        # count climax flags

    # Volatility context
    compression_count: int = 0          # count squeeze/compression flags

    # Market strength
    bull_bear_ratio: float = 0.5        # bullish / (bullish + bearish)
    sector_momentum: float = 0.0        # from V4S metadata

    # Price structure
    breakout_count: int = 0             # count breakout flags

    # Regime context (for regime-aware training)
    regime_duration: int = 0            # days in current regime direction
    regime_transition: float = 0.0      # regime_score[t] - regime_score[t-3]

    # Regime interaction features (expert_norm × trend_regime_norm)
    rsi_x_regime: float = 0.0
    macd_x_regime: float = 0.0
    volume_x_regime: float = 0.0
    breakout_x_regime: float = 0.0
    momentum_x_regime: float = 0.0
    breadth_x_regime: float = 0.0
    rs_x_regime: float = 0.0
    bb_x_regime: float = 0.0


class MetaBuilder:
    """
    Build meta features from expert signals.

    Usage:
        builder = MetaBuilder(signals_db, market_db)
        meta = builder.build("FPT", "2014-07-29")
        batch = builder.build_all("2014-07-29")
    """

    def __init__(self, signals_db: str | Path, market_db: str | Path):
        self.signals_db = str(signals_db)
        self.market_db = str(market_db)

    def _connect_signals(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.signals_db, timeout=30)
        conn.row_factory = sqlite3.Row
        return conn

    def _connect_market(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.market_db, timeout=30)
        conn.row_factory = sqlite3.Row
        return conn

    def _fetch_expert_signals(
        self, conn: sqlite3.Connection, symbol: str, date: str
    ) -> dict[str, dict]:
        """Fetch all expert signals for a symbol on a date."""
        rows = conn.execute(
            """SELECT expert_id, primary_score, secondary_score,
                      signal_code, signal_quality, metadata_json
               FROM expert_signals
               WHERE symbol=? AND date=? AND snapshot_time='EOD'""",
            (symbol, date),
        ).fetchall()

        result = {}
        for r in rows:
            meta = {}
            if r["metadata_json"]:
                try:
                    meta = json.loads(r["metadata_json"])
                except json.JSONDecodeError:
                    pass
            result[r["expert_id"]] = {
                "primary_score": r["primary_score"],
                "secondary_score": r["secondary_score"],
                "signal_code": r["signal_code"],
                "signal_quality": r["signal_quality"],
                "metadata": meta,
            }
        return result

    def _fetch_regime(self, date: str) -> float:
        """Fetch regime score from market.db using T-1 (anti-leakage).
        Features for date T must only use data up to close of T-1."""
        conn = self._connect_market()
        try:
            row = conn.execute(
                "SELECT regime_score FROM market_regime WHERE date<? AND snapshot_time='EOD' ORDER BY date DESC LIMIT 1",
                (date,),
            ).fetchone()
            return float(row["regime_score"]) if row else 0.0
        finally:
            conn.close()

    def build(self, symbol: str, date: str) -> MetaFeatures:
        """Build meta features for 1 symbol on 1 date."""
        conn = self._connect_signals()
        try:
            signals = self._fetch_expert_signals(conn, symbol, date)
        finally:
            conn.close()

        meta = MetaFeatures(symbol=symbol, date=date)

        if not signals:
            return meta

        # Normalize all scores
        norms = {}
        for eid, sig in signals.items():
            norm = _normalize_score(eid, sig["primary_score"])
            norms[eid] = norm

        meta.expert_norms = norms
        meta.expert_count = len(norms)

        # Bullish / bearish / neutral counts
        for norm in norms.values():
            if norm > 0.05:
                meta.bullish_expert_count += 1
            elif norm < -0.05:
                meta.bearish_expert_count += 1
            else:
                meta.neutral_expert_count += 1

        # Average normalized score
        if norms:
            meta.avg_score = sum(norms.values()) / len(norms)

        # Group scores
        meta.trend_group_score = self._group_avg(norms, "TREND")
        meta.momentum_group_score = self._group_avg(norms, "MOMENTUM")
        meta.volume_group_score = self._group_avg(norms, "VOLUME")
        meta.volatility_group_score = self._group_avg(norms, "VOLATILITY")
        meta.structure_group_score = self._group_avg(norms, "STRUCTURE")
        meta.context_group_score = self._group_avg(norms, "CONTEXT")

        # Conflict & alignment
        from .conflict_detector import ConflictDetector
        detector = ConflictDetector()
        meta.expert_conflict_score = detector.compute_conflict_score(norms)
        meta.expert_alignment_score = detector.compute_alignment_score(norms)

        # Regime
        meta.regime_score = self._fetch_regime(date)

        # --- Compute 14 new expanded meta features ---
        # Fetch metadata_json for all experts
        conn2 = self._connect_signals()
        try:
            sig_rows = conn2.execute(
                """SELECT expert_id, metadata_json FROM expert_signals
                   WHERE symbol=? AND date=? AND snapshot_time='EOD'""",
                (symbol, date),
            ).fetchall()
        finally:
            conn2.close()

        metadata_map = {}
        for sr in sig_rows:
            if sr["metadata_json"]:
                try:
                    metadata_map[sr["expert_id"]] = json.loads(sr["metadata_json"])
                except (json.JSONDecodeError, TypeError):
                    pass

        # Trend context
        trend_ids = EXPERT_GROUPS["TREND"]
        trend_norms = [norms[eid] for eid in trend_ids if eid in norms]
        if trend_norms:
            meta.trend_alignment_score = sum(1 for v in trend_norms if v > 0.05) / len(trend_norms)
            meta.trend_strength_max = max(abs(v) for v in trend_norms)
        ma_meta = metadata_map.get("V4MA", {})
        meta.ma_alignment_pct = float(ma_meta.get("alignment_score", 0.0)) / 3.0  # normalize -3..+3 to ~0..1
        p_meta = metadata_map.get("V4P", {})
        meta.trend_persistence_avg = float(p_meta.get("trend_persistence", 0.5))

        # Momentum context
        mom_ids = EXPERT_GROUPS["MOMENTUM"]
        rsi_meta = metadata_map.get("V4RSI", {})
        macd_meta = metadata_map.get("V4MACD", {})
        sto_meta = metadata_map.get("V4STO", {})
        div_count = 0
        for m in [rsi_meta, macd_meta, sto_meta]:
            if m.get("divergence_flag", 0) != 0:
                div_count += 1
        if sto_meta.get("stoch_divergence", 0) != 0 and not sto_meta.get("divergence_flag"):
            div_count += 1
        meta.momentum_divergence_count = div_count

        ob_count = 0
        os_count = 0
        if rsi_meta.get("rsi_zone", 0) >= 1:
            ob_count += 1
        if rsi_meta.get("rsi_zone", 0) <= -1:
            os_count += 1
        if float(sto_meta.get("stoch_k", 0.5)) > 0.8:
            ob_count += 1
        if float(sto_meta.get("stoch_k", 0.5)) < 0.2:
            os_count += 1
        meta.overbought_count = ob_count
        meta.oversold_count = os_count

        # Volume context
        v_meta = metadata_map.get("V4V", {})
        meta.volume_pressure = float(v_meta.get("vol_ratio", 1.0))
        liq_meta = metadata_map.get("V4LIQ", {})
        meta.liquidity_shock_avg = float(liq_meta.get("liquidity_shock", liq_meta.get("adtv_ratio", 1.0)))
        climax = 0
        if v_meta.get("vol_climax", False):
            climax += 1
        meta.climax_volume_count = climax

        # Volatility context
        atr_meta = metadata_map.get("V4ATR", {})
        bb_meta = metadata_map.get("V4BB", {})
        comp = 0
        if float(atr_meta.get("volatility_compression", 1.0)) < 0.5:
            comp += 1
        if bb_meta.get("bb_squeeze_active", False):
            comp += 1
        meta.compression_count = comp

        # Market strength
        total_dir = meta.bullish_expert_count + meta.bearish_expert_count
        meta.bull_bear_ratio = meta.bullish_expert_count / total_dir if total_dir > 0 else 0.5
        s_meta = metadata_map.get("V4S", {})
        meta.sector_momentum = float(s_meta.get("sector_momentum", 0.0))

        # Price structure
        bcount = 0
        if p_meta.get("breakout_flag", False):
            bcount += 1
        if p_meta.get("breakout60_flag", False):
            bcount += 1
        sr_meta = metadata_map.get("V4SR", {})
        if sr_meta.get("breakout_above_resistance", False):
            bcount += 1
        meta.breakout_count = bcount

        # Regime context: duration + transition
        meta.regime_duration, meta.regime_transition = self._compute_regime_context(date)

        # Regime interaction features: expert_norm × trend_regime_norm
        trend_regime_norm = meta.regime_score / 4.0  # -4..+4 → -1..+1
        meta.rsi_x_regime = norms.get("V4RSI", 0.0) * trend_regime_norm
        meta.macd_x_regime = norms.get("V4MACD", 0.0) * trend_regime_norm
        meta.volume_x_regime = norms.get("V4V", 0.0) * trend_regime_norm
        meta.breadth_x_regime = norms.get("V4BR", 0.0) * trend_regime_norm
        meta.rs_x_regime = norms.get("V4RS", 0.0) * trend_regime_norm
        meta.bb_x_regime = norms.get("V4BB", 0.0) * trend_regime_norm
        meta.momentum_x_regime = meta.momentum_group_score * trend_regime_norm
        # breakout_flag from V4P metadata (0 or 1) × regime
        breakout_val = float(p_meta.get("breakout_flag", 0))
        meta.breakout_x_regime = breakout_val * trend_regime_norm

        return meta

    def build_all(
        self, date: str, symbols: list[str] | None = None
    ) -> list[MetaFeatures]:
        """Build meta features for all symbols on a date."""
        conn = self._connect_signals()
        try:
            if symbols is None:
                rows = conn.execute(
                    "SELECT DISTINCT symbol FROM expert_signals WHERE date=?",
                    (date,),
                ).fetchall()
                symbols = [r["symbol"] for r in rows]
        finally:
            conn.close()

        return [self.build(sym, date) for sym in symbols]

    def _compute_regime_context(self, date: str) -> tuple[int, float]:
        """
        Compute regime_duration and regime_transition using T-1 data (anti-leakage).
        - regime_duration: consecutive days with same regime direction
        - regime_transition: regime_score[t-1] - regime_score[t-4]
        """
        conn = self._connect_market()
        try:
            rows = conn.execute(
                """SELECT date, regime_score FROM market_regime
                   WHERE date < ? AND snapshot_time='EOD'
                   ORDER BY date DESC LIMIT 10""",
                (date,),
            ).fetchall()
        finally:
            conn.close()

        if not rows:
            return 0, 0.0

        scores = [float(r["regime_score"]) if r["regime_score"] else 0.0 for r in rows]
        # scores[0] = current, scores[1] = yesterday, etc.

        # Transition: current - 3 days ago
        transition = 0.0
        if len(scores) >= 4:
            transition = scores[0] - scores[3]

        # Duration: count consecutive days with same sign as current
        duration = 1
        if len(scores) >= 2:
            current_sign = 1 if scores[0] > 0 else (-1 if scores[0] < 0 else 0)
            for i in range(1, len(scores)):
                s = 1 if scores[i] > 0 else (-1 if scores[i] < 0 else 0)
                if s == current_sign:
                    duration += 1
                else:
                    break

        return duration, transition

    @staticmethod
    def _group_avg(norms: dict[str, float], group_name: str) -> float:
        """Average normalized score for a group."""
        group_ids = EXPERT_GROUPS.get(group_name, [])
        values = [norms[eid] for eid in group_ids if eid in norms]
        return sum(values) / len(values) if values else 0.0
