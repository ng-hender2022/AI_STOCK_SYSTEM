"""
V4REG Signal Logic (Phase 1 — Rulebook Only)
Tính regime scores từ features theo công thức trong R_MODEL_ARCHITECTURE Section 10.

Output:
    trend_regime_score      : -4 → +4
    vol_regime_score        :  0 → 4
    liquidity_regime_score  : -2 → +2
    regime_label            : text label
    regime_confidence       :  0 → 1
"""

from dataclasses import dataclass
from pathlib import Path

import yaml

from .feature_builder import RegimeFeatures

_CONFIG_PATH = Path(__file__).parent / "config.yaml"


def _load_config() -> dict:
    with open(_CONFIG_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


@dataclass
class RegimeOutput:
    """Kết quả scoring của V4REG cho 1 ngày."""
    date: str
    data_cutoff_date: str

    # Scores
    trend_regime_score_raw: float = 0.0
    trend_regime_score: float = 0.0         # smoothed + clamped
    vol_regime_score: float = 0.0
    liquidity_regime_score: float = 0.0

    # Sub-components (for transparency)
    trend_structure_score: float = 0.0      # -2..+2
    breadth_score: float = 0.0              # -2..+2
    momentum_score: float = 0.0             # -2..+2
    drawdown_stress_score: float = 0.0      # -2..0

    # Metadata
    regime_label: str = "NEUTRAL"
    regime_confidence: float = 0.0
    panic_triggered: bool = False
    blowoff_triggered: bool = False


class RegimeSignalLogic:
    """
    Rulebook scoring engine for V4REG.

    Usage:
        logic = RegimeSignalLogic()
        output = logic.compute(features, prev_smooth_score=None)
    """

    REGIME_LABELS = {
        4: "STRONG_BULL",
        3: "BULL",
        2: "WEAK_BULL",
        1: "WEAK_BULL",
        0: "NEUTRAL",
        -1: "WEAK_BEAR",
        -2: "BEAR",
        -3: "BEAR",
        -4: "STRONG_BEAR",
    }

    def __init__(self):
        self.cfg = _load_config()

    def compute(
        self,
        features: RegimeFeatures,
        prev_smooth_score: float | None = None,
    ) -> RegimeOutput:
        """
        Compute regime scores from features.

        Args:
            features: RegimeFeatures from feature_builder
            prev_smooth_score: previous day's smoothed trend_regime_score
                               (None if first run)
        """
        output = RegimeOutput(
            date=features.date,
            data_cutoff_date=features.data_cutoff_date,
        )

        if not features.has_sufficient_data:
            return output

        # --- Component scores ---
        output.trend_structure_score = self._score_trend_structure(features)
        output.breadth_score = self._score_breadth(features)
        output.momentum_score = self._score_momentum(features)
        output.drawdown_stress_score = self._score_drawdown(features)

        # --- Weighted combination → raw score ---
        w = self.cfg["weights"]
        core = (
            w["trend_structure"] * output.trend_structure_score
            + w["breadth"] * output.breadth_score
            + w["momentum"] * output.momentum_score
            + w["drawdown_stress"] * output.drawdown_stress_score
        )
        raw = core * self.cfg["scale_factor"]
        raw = max(-4.0, min(4.0, raw))

        # --- Vol regime ---
        output.vol_regime_score = self._score_volatility(features)

        # --- Liquidity regime ---
        output.liquidity_regime_score = self._score_liquidity(features)

        # --- Panic override ---
        panic_cfg = self.cfg["panic"]
        if (
            features.vnindex_return_1d <= panic_cfg["drop_threshold"]
            and output.breadth_score <= panic_cfg["breadth_threshold"]
            and output.vol_regime_score >= panic_cfg["vol_threshold"]
        ):
            raw = -4.0
            output.panic_triggered = True

        # --- Blowoff override ---
        blowoff_cfg = self.cfg["blowoff"]
        if (
            output.trend_structure_score >= blowoff_cfg["require_trend"]
            and output.breadth_score >= blowoff_cfg["require_breadth"]
            and output.momentum_score >= blowoff_cfg["require_momentum"]
            and output.liquidity_regime_score > 0
        ):
            raw = max(raw, 4.0)
            output.blowoff_triggered = True

        output.trend_regime_score_raw = raw

        # --- Smoothing ---
        smooth_cfg = self.cfg["smoothing"]
        alpha = smooth_cfg["alpha"]
        max_change = smooth_cfg["max_daily_change"]

        if output.panic_triggered:
            # Panic bypasses smoothing entirely
            smoothed = raw
        elif prev_smooth_score is None:
            smoothed = raw
        else:
            smoothed = alpha * raw + (1 - alpha) * prev_smooth_score

            # Clamp daily change
            delta = smoothed - prev_smooth_score
            if abs(delta) > max_change:
                smoothed = prev_smooth_score + max_change * (
                    1 if delta > 0 else -1
                )

        smoothed = max(-4.0, min(4.0, smoothed))
        output.trend_regime_score = round(smoothed * 2) / 2  # round to 0.5

        # --- Label ---
        label_key = int(round(output.trend_regime_score))
        label_key = max(-4, min(4, label_key))
        output.regime_label = self.REGIME_LABELS.get(label_key, "NEUTRAL")

        # --- Confidence ---
        output.regime_confidence = self._compute_confidence(output, features)

        return output

    # -----------------------------------------------------------------------
    # Component scoring functions
    # -----------------------------------------------------------------------

    def _score_trend_structure(self, f: RegimeFeatures) -> float:
        """
        Trend structure score: -2 to +2
        Based on VNINDEX close vs MAs and MA slopes.
        """
        score = 0.0

        # Close vs MA alignment
        above_ma20 = f.vnindex_close > f.vnindex_ma20 if f.vnindex_ma20 > 0 else False
        above_ma50 = f.vnindex_close > f.vnindex_ma50 if f.vnindex_ma50 > 0 else False
        above_ma200 = f.vnindex_close > f.vnindex_ma200 if f.vnindex_ma200 > 0 else False
        ma20_above_ma50 = f.vnindex_ma20 > f.vnindex_ma50 if f.vnindex_ma50 > 0 else False
        ma50_above_ma200 = f.vnindex_ma50 > f.vnindex_ma200 if f.vnindex_ma200 > 0 else False

        # Full alignment bullish
        if (
            above_ma20 and above_ma50 and above_ma200
            and ma20_above_ma50 and ma50_above_ma200
            and f.vnindex_ma20_slope > 0 and f.vnindex_ma50_slope > 0
        ):
            score = 2.0
        # Partial bullish
        elif above_ma20 and ma20_above_ma50 and f.vnindex_ma20_slope > 0:
            score = 1.0
        # Full alignment bearish
        elif (
            not above_ma20 and not above_ma50 and not above_ma200
            and not ma20_above_ma50 and not ma50_above_ma200
            and f.vnindex_ma20_slope < 0 and f.vnindex_ma50_slope < 0
        ):
            score = -2.0
        # Partial bearish
        elif not above_ma20 and not ma20_above_ma50 and f.vnindex_ma20_slope < 0:
            score = -1.0
        # Mixed
        else:
            score = 0.0

        return score

    def _score_breadth(self, f: RegimeFeatures) -> float:
        """
        Breadth score: -2 to +2
        Based on % stocks above MA50 and A/D ratio.
        """
        bcfg = self.cfg["breadth"]
        pct = f.pct_above_ma50
        ad = f.advance_decline_ratio

        if pct >= bcfg["strong_threshold"] and ad > 1.5:
            return 2.0
        elif pct >= 0.55 and ad > 1.0:
            return 1.0
        elif pct <= bcfg["weak_threshold"] and ad < 0.5:
            return -2.0
        elif pct <= 0.40 and ad < 0.8:
            return -1.0
        else:
            return 0.0

    def _score_momentum(self, f: RegimeFeatures) -> float:
        """
        Momentum score: -2 to +2
        Based on 20d and 60d VNINDEX returns.
        """
        mcfg = self.cfg["momentum"]
        r20 = f.vnindex_return_20d
        r60 = f.vnindex_return_60d

        if r20 >= mcfg["strong_positive"] and r60 > 0:
            return 2.0
        elif r20 >= mcfg["mild_positive"]:
            return 1.0
        elif r20 <= mcfg["strong_negative"] and r60 < 0:
            return -2.0
        elif r20 <= mcfg["mild_negative"]:
            return -1.0
        else:
            return 0.0

    def _score_drawdown(self, f: RegimeFeatures) -> float:
        """
        Drawdown stress score: -2 to 0
        Based on VNINDEX drawdown from rolling high.
        """
        dcfg = self.cfg["drawdown"]
        dd = abs(f.vnindex_drawdown)  # drawdown is negative, take abs

        if dd >= dcfg["severe_threshold"]:
            return -2.0
        elif dd >= dcfg["mild_threshold"]:
            return -1.0
        else:
            return 0.0

    def _score_volatility(self, f: RegimeFeatures) -> float:
        """
        Volatility regime score: 0 to 4
        Based on ATR percentile within lookback.
        """
        bins = self.cfg["volatility"]["percentile_bins"]
        pct = f.atr_pct_percentile

        if pct < bins[0]:
            return 0.0
        elif pct < bins[1]:
            return 1.0
        elif pct < bins[2]:
            return 2.0
        elif pct < bins[3]:
            return 3.0
        else:
            return 4.0

    def _score_liquidity(self, f: RegimeFeatures) -> float:
        """
        Liquidity regime score: -2 to +2
        Based on market volume vs MA20 volume.
        """
        lcfg = self.cfg["liquidity"]
        ratio = f.market_volume_ratio

        if ratio >= lcfg["strong_expansion"]:
            return 2.0
        elif ratio >= lcfg["mild_expansion"]:
            return 1.0
        elif ratio <= lcfg["severe_contraction"]:
            return -2.0
        elif ratio <= lcfg["mild_contraction"]:
            return -1.0
        else:
            return 0.0

    def _compute_confidence(
        self, output: RegimeOutput, features: RegimeFeatures
    ) -> float:
        """
        Confidence score: 0 to 1
        Based on component agreement and regime persistence.
        """
        # Rule consistency: do all components agree on direction?
        components = [
            output.trend_structure_score,
            output.breadth_score,
            output.momentum_score,
        ]

        # Count same-sign components
        positive = sum(1 for c in components if c > 0)
        negative = sum(1 for c in components if c < 0)
        max_agree = max(positive, negative)
        rule_consistency = max_agree / len(components)  # 0.33 to 1.0

        # Strength: how far from 0 are the component scores?
        avg_abs = sum(abs(c) for c in components) / len(components)
        strength = min(1.0, avg_abs / 2.0)  # normalize to 0..1

        # Combined
        confidence = 0.60 * rule_consistency + 0.40 * strength
        return round(min(1.0, max(0.0, confidence)), 3)
