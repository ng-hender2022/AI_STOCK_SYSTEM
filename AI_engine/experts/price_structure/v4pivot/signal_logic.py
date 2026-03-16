"""
V4PIVOT Signal Logic
Scoring (3 components, clamped -4..+4):
    Position score    : -2 to +2  (where close sits vs pivot levels)
    Confluence score  : -1 to +1  (multi-timeframe agreement)
    Alignment score   : -1 to +1  (pivot trend direction)
    pivot_norm        : score / 4
"""

from dataclasses import dataclass
from pathlib import Path

import yaml

from .feature_builder import PivotFeatures

_CONFIG_PATH = Path(__file__).parent / "config.yaml"


def _load_config() -> dict:
    with open(_CONFIG_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


@dataclass
class PivotOutput:
    """Scoring output for V4PIVOT."""
    symbol: str
    date: str
    data_cutoff_date: str

    pivot_score: float = 0.0
    pivot_norm: float = 0.0

    position_score: float = 0.0
    confluence_score: float = 0.0
    alignment_score: float = 0.0

    signal_quality: int = 0
    signal_code: str = ""
    has_sufficient_data: bool = False


class PivotSignalLogic:

    def __init__(self):
        self.cfg = _load_config()

    def compute(self, features: PivotFeatures) -> PivotOutput:
        output = PivotOutput(
            symbol=features.symbol,
            date=features.date,
            data_cutoff_date=features.data_cutoff_date,
        )

        if not features.has_sufficient_data:
            return output

        output.has_sufficient_data = True
        scoring = self.cfg["scoring"]
        neutral_pct = self.cfg.get("neutral_pct", 0.002)

        close = features.close

        # --- 1. Position score (-2..+2) ---
        # Neutral zone: within 0.2% of pivot
        if features.pivot > 0 and abs(close - features.pivot) / features.pivot <= neutral_pct:
            output.position_score = float(scoring["position"]["at_pivot"])
        elif close > features.r2:
            output.position_score = float(scoring["position"]["above_r2"])
        elif close > features.r1:
            output.position_score = float(scoring["position"]["r1_to_r2"])
        elif close > features.pivot:
            output.position_score = float(scoring["position"]["p_to_r1"])
        elif close > features.s1:
            output.position_score = float(scoring["position"]["s1_to_p"])
        elif close > features.s2:
            output.position_score = float(scoring["position"]["s2_to_s1"])
        else:
            output.position_score = float(scoring["position"]["below_s2"])

        # --- 2. Confluence score (-1..+1) ---
        bullish_count = 0
        bearish_count = 0
        tf_count = 0

        # Daily
        if features.pivot > 0:
            tf_count += 1
            if close > features.pivot:
                bullish_count += 1
            else:
                bearish_count += 1

        # Weekly
        if features.weekly_pivot > 0:
            tf_count += 1
            if close > features.weekly_pivot:
                bullish_count += 1
            else:
                bearish_count += 1

        # Monthly
        if features.monthly_pivot > 0:
            tf_count += 1
            if close > features.monthly_pivot:
                bullish_count += 1
            else:
                bearish_count += 1

        if tf_count >= 3:
            if bullish_count == 3:
                output.confluence_score = float(scoring["confluence"]["all_bullish"])
            elif bullish_count == 2:
                output.confluence_score = float(scoring["confluence"]["two_bullish"])
            elif bearish_count == 3:
                output.confluence_score = float(scoring["confluence"]["all_bearish"])
            elif bearish_count == 2:
                output.confluence_score = float(scoring["confluence"]["two_bearish"])
            else:
                output.confluence_score = float(scoring["confluence"]["mixed"])
        else:
            output.confluence_score = float(scoring["confluence"]["mixed"])

        # --- 3. Alignment score (-1..+1) ---
        daily_rising = features.pivot > features.prev_pivot if features.prev_pivot > 0 else None
        weekly_rising = features.weekly_pivot > features.prev_weekly_pivot if features.prev_weekly_pivot > 0 else None
        monthly_rising = features.monthly_pivot > features.prev_monthly_pivot if features.prev_monthly_pivot > 0 else None

        rising_flags = [f for f in [daily_rising, weekly_rising, monthly_rising] if f is not None]

        if len(rising_flags) >= 2:
            if all(rising_flags):
                output.alignment_score = float(scoring["alignment"]["all_rising"])
            elif not any(rising_flags):
                output.alignment_score = float(scoring["alignment"]["all_falling"])
            else:
                output.alignment_score = float(scoring["alignment"]["mixed"])
        else:
            output.alignment_score = float(scoring["alignment"]["mixed"])

        # --- Total score (clamped -4..+4) ---
        raw = output.position_score + output.confluence_score + output.alignment_score
        output.pivot_score = max(-4.0, min(4.0, raw))
        output.pivot_norm = output.pivot_score / 4.0

        # --- Signal quality ---
        output.signal_quality = self._compute_quality(output, features)

        # --- Signal code ---
        output.signal_code = self._signal_code(output, features)

        return output

    def _compute_quality(self, o: PivotOutput, f: PivotFeatures) -> int:
        """
        Quality 0-4:
            4 = 3-timeframe confluence + close beyond R2/S2
            3 = 2-timeframe confluence + close beyond R1/S1
            2 = single timeframe signal + clear direction
            1 = close near pivot, no confluence
            0 = insufficient data
        """
        close = f.close
        beyond_r2 = close > f.r2 if f.r2 > 0 else False
        beyond_s2 = close < f.s2 if f.s2 > 0 else False
        beyond_r1 = close > f.r1 if f.r1 > 0 else False
        beyond_s1 = close < f.s1 if f.s1 > 0 else False

        confluence_3 = abs(o.confluence_score) >= 0.99  # all 3 agree
        confluence_2 = abs(o.confluence_score) >= 0.49  # 2 of 3 agree

        if confluence_3 and (beyond_r2 or beyond_s2):
            return 4
        if confluence_2 and (beyond_r1 or beyond_s1):
            return 3
        if abs(o.position_score) >= 1.0:
            return 2
        if abs(o.pivot_score) > 0:
            return 1
        return 0

    def _signal_code(self, o: PivotOutput, f: PivotFeatures) -> str:
        """Determine signal code based on output."""
        close = f.close
        neutral_pct = self.cfg.get("neutral_pct", 0.002)

        # Neutral at pivot
        if f.pivot > 0 and abs(close - f.pivot) / f.pivot <= neutral_pct:
            return "V4PIVOT_NEUT_AT_PIVOT"

        # Bounce / Reject signals (close near S1 or R1 and returning toward pivot)
        # Bounce from S1: close is between S1 and P, close is closer to S1
        if f.s1 > 0 and f.pivot > 0 and f.s1 < close <= f.pivot:
            dist_to_s1 = close - f.s1
            dist_to_p = f.pivot - close
            if dist_to_s1 < dist_to_p:
                return "V4PIVOT_BULL_BOUNCE_S1"

        # Reject from R1: close is between P and R1, close is closer to R1
        if f.r1 > 0 and f.pivot > 0 and f.pivot <= close < f.r1:
            dist_to_r1 = f.r1 - close
            dist_to_p = close - f.pivot
            if dist_to_r1 < dist_to_p:
                return "V4PIVOT_BEAR_REJECT_R1"

        # Confluence signals
        if o.confluence_score >= 0.99:
            return "V4PIVOT_BULL_CONFLUENCE"
        if o.confluence_score <= -0.99:
            return "V4PIVOT_BEAR_CONFLUENCE"

        # Position-based signals
        if close > f.r2:
            return "V4PIVOT_BULL_ABOVE_R2"
        if close > f.r1:
            return "V4PIVOT_BULL_ABOVE_R1"
        if close < f.s2:
            return "V4PIVOT_BEAR_BELOW_S2"
        if close < f.s1:
            return "V4PIVOT_BEAR_BELOW_S1"

        # Fallback confluence
        if o.confluence_score >= 0.49:
            return "V4PIVOT_BULL_CONFLUENCE"
        if o.confluence_score <= -0.49:
            return "V4PIVOT_BEAR_CONFLUENCE"

        return "V4PIVOT_NEUT_AT_PIVOT"
