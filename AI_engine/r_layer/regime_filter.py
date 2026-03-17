"""
RegimeFilter - Shared regime-aware filtering for ALL R Layer models.

Provides:
- Regime context (current + historical trajectory)
- Dynamic BUY thresholds based on regime path
- SELL enhancement triggers
- Sell trigger detection from features

Usage:
    rf = RegimeFilter(market_db)
    ctx = rf.get_regime_context(date)
    threshold = rf.get_buy_threshold(ctx, base_threshold=0.55)
    sell = rf.get_sell_strength(ctx)
    triggers = rf.check_sell_triggers(features_dict)
"""

import sqlite3
from pathlib import Path
from dataclasses import dataclass


@dataclass
class RegimeContext:
    """Regime state at a given date."""
    date: str
    raw_regime: float = 0.0      # regime_score at T (raw -4..+4)
    regime_t5: float = 0.0       # regime_score at T-5
    regime_t10: float = 0.0      # regime_score at T-10
    regime_delta: float = 0.0    # raw_regime - regime_t5 (direction of change)
    has_data: bool = False


class RegimeFilter:
    """
    Shared regime filter for all R Layer models.
    Uses market_regime table (anti-leakage: reads date < T).
    """

    def __init__(self, market_db: str | Path):
        self.market_db = str(market_db)

    def get_regime_context(self, date: str) -> RegimeContext:
        """
        Get regime context using T-1 data (anti-leakage).
        Returns regime at T-1, T-6, T-11 (shifted by 1 for leakage prevention).
        """
        conn = sqlite3.connect(self.market_db, timeout=30)
        conn.row_factory = sqlite3.Row
        try:
            rows = conn.execute(
                """SELECT date, regime_score FROM market_regime
                   WHERE date < ? AND snapshot_time='EOD'
                   ORDER BY date DESC LIMIT 15""",
                (date,),
            ).fetchall()
        finally:
            conn.close()

        ctx = RegimeContext(date=date)
        if not rows:
            return ctx

        scores = []
        for r in rows:
            s = float(r["regime_score"]) if r["regime_score"] is not None else 0.0
            scores.append(s)

        # scores[0] = T-1, scores[4] = T-5, scores[9] = T-10
        ctx.raw_regime = scores[0]
        ctx.regime_t5 = scores[4] if len(scores) > 4 else scores[-1]
        ctx.regime_t10 = scores[9] if len(scores) > 9 else scores[-1]
        ctx.regime_delta = ctx.raw_regime - ctx.regime_t5
        ctx.has_data = True

        return ctx

    def get_buy_threshold(
        self, ctx: RegimeContext, base_threshold: float = 0.55
    ) -> float | None:
        """
        Get dynamic BUY threshold based on regime path.

        Returns:
            float: threshold (higher = more selective)
            None: BLOCK all BUY signals
        """
        if not ctx.has_data:
            return base_threshold

        r = ctx.raw_regime
        delta = ctx.regime_delta
        r10 = ctx.regime_t10

        if r >= 2.0:
            # Strong Bull — most permissive
            return 0.55
        elif r >= 1.0:
            # Bull
            return 0.60
        elif r >= 0.0:
            # Neutral — depends on trajectory
            if r10 >= 1.0 and delta < -0.3:
                return 0.70  # Neutral coming DOWN from bull — be cautious
            elif r10 <= -1.0:
                return 0.60  # Neutral recovering FROM bear — allow entries
            else:
                return 0.65  # Neutral sideways
        elif r >= -1.0:
            # Weak Bear — very selective or block
            if r10 <= -2.0:
                return 0.70  # Weak bear recovering from deep bear
            elif delta > 0.3:
                return 0.60  # Weak bear but improving
            else:
                return None  # BLOCK — no recovery signal
        else:
            # Bear (< -1) — BLOCK completely
            return None

    def get_sell_strength(self, ctx: RegimeContext) -> str | None:
        """
        Get sell signal enhancement based on regime.

        Returns:
            "STRONG": aggressive sell (regime deteriorating)
            "NORMAL": standard sell
            "WEAK": mild sell
            None: no sell enhancement (bull regime)
        """
        if not ctx.has_data:
            return None

        if ctx.raw_regime > 0:
            return None  # No sell enhancement in bull

        delta = ctx.regime_delta
        if delta < -0.3:
            return "STRONG"   # Regime deteriorating fast
        elif abs(delta) <= 0.3:
            return "NORMAL"   # Stable bear/neutral
        else:
            return "WEAK"     # Bear but improving

    def check_sell_triggers(self, features: dict) -> list[str]:
        """
        Check for sell trigger conditions from feature values.

        Args:
            features: dict of feature values (from feature matrix row)

        Returns:
            list of triggered conditions
        """
        triggers = []

        # 1. MA20 break: price below MA20
        if features.get("v4ma_dist_ma20", 0) < 0:
            triggers.append("MA20_BREAK")

        # 2. Support break: pivot S1 broken
        if features.get("v4pivot_position_score", 0) < -1.0:
            triggers.append("SUPPORT_BREAK")

        # 3. Volume spike bearish: high volume + negative return
        vol_ratio = features.get("v4v_volume_ratio_20", 0)
        ret_1d = features.get("v4p_ret_1d", 0)
        if vol_ratio > 2.0 and ret_1d < 0:
            triggers.append("VOLUME_SPIKE_BEAR")

        return triggers

    def apply_filter(
        self, score: float, p_up: float, ctx: RegimeContext,
        base_threshold: float = 0.55,
    ) -> float:
        """
        Apply regime filter to a model's raw score.

        Args:
            score: raw model score
            p_up: probability of UP class (for threshold models)
            ctx: RegimeContext
            base_threshold: model's base threshold

        Returns:
            filtered score (0.0 if blocked)
        """
        if score <= 0:
            return score  # Don't filter sell/neutral signals

        threshold = self.get_buy_threshold(ctx, base_threshold)
        if threshold is None:
            return 0.0  # BLOCKED

        if p_up < threshold:
            return 0.0  # Below threshold

        return score
