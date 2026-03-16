"""
V4CANDLE Signal Logic
Scoring (clamped -4..+4):
    Pattern score      : -3 to +3
    Volume confirmation: -0.5 to +0.5
    Context modifier   : -0.5 to +0.5
    candle_norm        : score / 4
"""

from dataclasses import dataclass
from pathlib import Path

import yaml

from .feature_builder import CandleFeatures

_CONFIG_PATH = Path(__file__).parent / "config.yaml"


def _load_config() -> dict:
    with open(_CONFIG_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


@dataclass
class CandleOutput:
    """Scoring output for V4CANDLE."""
    symbol: str
    date: str
    data_cutoff_date: str

    candle_score: float = 0.0
    candle_norm: float = 0.0

    pattern_score: float = 0.0
    volume_modifier: float = 0.0
    context_modifier: float = 0.0

    pattern_name: str = "none"
    pattern_direction: str = "neutral"  # bullish / bearish / neutral

    signal_quality: int = 0
    signal_code: str = "V4CANDLE_NEUT_NONE"
    has_sufficient_data: bool = False


class CandleSignalLogic:

    def __init__(self):
        self.cfg = _load_config()

    def compute(self, features: CandleFeatures) -> CandleOutput:
        output = CandleOutput(
            symbol=features.symbol,
            date=features.date,
            data_cutoff_date=features.data_cutoff_date,
        )

        if not features.has_sufficient_data:
            return output

        output.has_sufficient_data = True

        # --- 1. Detect patterns and assign base score ---
        pattern_name, pattern_score, pattern_dir = self._detect_pattern(features)
        output.pattern_name = pattern_name
        output.pattern_score = pattern_score
        output.pattern_direction = pattern_dir

        # --- 2. Volume confirmation modifier ---
        vol_bonus = self.cfg["scoring"]["volume"]["confirm_bonus"]
        vol_threshold = self.cfg["vol_confirm_ratio"]
        volume_confirm = features.volume_ratio >= vol_threshold

        if volume_confirm and pattern_score != 0:
            if pattern_score > 0:
                output.volume_modifier = vol_bonus
            else:
                output.volume_modifier = -vol_bonus

        # --- 3. Context modifier (swing proximity) ---
        ctx_bonus = self.cfg["scoring"]["context"]["swing_bonus"]
        at_swing = False
        if pattern_dir == "bullish" and features.at_swing_low:
            output.context_modifier = ctx_bonus
            at_swing = True
        elif pattern_dir == "bearish" and features.at_swing_high:
            output.context_modifier = -ctx_bonus
            at_swing = True

        # --- 4. Total score (clamped -4..+4) ---
        raw = output.pattern_score + output.volume_modifier + output.context_modifier
        output.candle_score = max(-4.0, min(4.0, raw))
        output.candle_norm = output.candle_score / 4.0

        # --- 5. Signal quality ---
        output.signal_quality = self._compute_quality(
            output, volume_confirm, at_swing
        )

        # --- 6. Signal code ---
        output.signal_code = self._signal_code(output)

        return output

    def _detect_pattern(self, f: CandleFeatures) -> tuple[str, float, str]:
        """
        Detect candlestick pattern from features.
        Returns (pattern_name, base_score, direction).
        Priority: triple > double > single.
        """
        scoring = self.cfg["scoring"]["pattern"]

        # Need at least 3 bars for triple patterns
        if len(f.closes) >= 3:
            result = self._detect_triple(f, scoring)
            if result is not None:
                return result

        # Need at least 2 bars for double patterns
        if len(f.closes) >= 2:
            result = self._detect_double(f, scoring)
            if result is not None:
                return result

        # Single bar patterns
        result = self._detect_single(f, scoring)
        if result is not None:
            return result

        return ("none", 0.0, "neutral")

    def _detect_triple(self, f: CandleFeatures, scoring: dict) -> tuple[str, float, str] | None:
        """Detect triple candlestick patterns."""
        o0, o1, o2 = f.opens[-3], f.opens[-2], f.opens[-1]
        c0, c1, c2 = f.closes[-3], f.closes[-2], f.closes[-1]
        h0, h1, h2 = f.highs[-3], f.highs[-2], f.highs[-1]
        l0, l1, l2 = f.lows[-3], f.lows[-2], f.lows[-1]

        body0 = c0 - o0
        body1 = c1 - o1
        body2 = c2 - o2

        range0 = h0 - l0 + 1e-9
        range1 = h1 - l1 + 1e-9
        range2 = h2 - l2 + 1e-9

        body0_pct = abs(body0) / range0
        body1_pct = abs(body1) / range1
        body2_pct = abs(body2) / range2

        small_body = self.cfg["small_body_pct"]

        # Morning Star: bearish + small body + bullish
        # Day1 large bearish, Day2 small body, Day3 large bullish closing above Day1 midpoint
        mid0 = (o0 + c0) / 2.0
        if (body0 < 0 and body0_pct > small_body and
                body1_pct < small_body and
                body2 > 0 and body2_pct > small_body and
                c2 > mid0):
            return ("morning_star", float(scoring["strong_bull"]), "bullish")

        # Evening Star: bullish + small body + bearish
        # Day1 large bullish, Day2 small body, Day3 large bearish closing below Day1 midpoint
        if (body0 > 0 and body0_pct > small_body and
                body1_pct < small_body and
                body2 < 0 and body2_pct > small_body and
                c2 < mid0):
            return ("evening_star", float(scoring["strong_bear"]), "bearish")

        # Three White Soldiers: 3 consecutive bullish, each opens within prior body,
        # each closes near its high, progressively higher
        close_near_high = 0.70
        if (body0 > 0 and body1 > 0 and body2 > 0 and
                c1 > c0 and c2 > c1 and
                o1 >= min(o0, c0) and o1 <= max(o0, c0) and
                o2 >= min(o1, c1) and o2 <= max(o1, c1) and
                (c0 - l0) / range0 >= close_near_high and
                (c1 - l1) / range1 >= close_near_high and
                (c2 - l2) / range2 >= close_near_high):
            return ("three_white_soldiers", float(scoring["strong_bull"]), "bullish")

        # Three Black Crows: 3 consecutive bearish, each opens within prior body,
        # each closes near its low, progressively lower
        if (body0 < 0 and body1 < 0 and body2 < 0 and
                c1 < c0 and c2 < c1 and
                o1 >= min(o0, c0) and o1 <= max(o0, c0) and
                o2 >= min(o1, c1) and o2 <= max(o1, c1) and
                (h0 - c0) / range0 >= close_near_high and
                (h1 - c1) / range1 >= close_near_high and
                (h2 - c2) / range2 >= close_near_high):
            return ("three_black_crows", float(scoring["strong_bear"]), "bearish")

        return None

    def _detect_double(self, f: CandleFeatures, scoring: dict) -> tuple[str, float, str] | None:
        """Detect double candlestick patterns."""
        o0, o1 = f.opens[-2], f.opens[-1]
        c0, c1 = f.closes[-2], f.closes[-1]

        body0 = c0 - o0
        body1 = c1 - o1

        # Bullish Engulfing: Day1 bearish, Day2 bullish, Day2 body engulfs Day1 body
        if (body0 < 0 and body1 > 0 and
                c1 > o0 and o1 < c0):
            # Day2 real body fully contains Day1 real body
            if (max(o1, c1) >= max(o0, c0) and min(o1, c1) <= min(o0, c0)):
                return ("bullish_engulfing", float(scoring["strong_bull"]), "bullish")

        # Bearish Engulfing: Day1 bullish, Day2 bearish, Day2 body engulfs Day1 body
        if (body0 > 0 and body1 < 0 and
                c1 < o0 and o1 > c0):
            if (max(o1, c1) >= max(o0, c0) and min(o1, c1) <= min(o0, c0)):
                return ("bearish_engulfing", float(scoring["strong_bear"]), "bearish")

        return None

    def _detect_single(self, f: CandleFeatures, scoring: dict) -> tuple[str, float, str] | None:
        """Detect single candlestick patterns."""
        doji_thresh = self.cfg["doji_body_pct"]
        marubozu_thresh = self.cfg["marubozu_body_pct"]
        shadow_ratio = self.cfg["hammer_shadow_ratio"]

        body_abs = abs(f.body)

        # Doji: body_pct < 0.10
        if f.body_pct < doji_thresh:
            return ("doji", float(scoring["neutral"]), "neutral")

        # Hammer: small body top, long lower shadow >= 2x body, upper shadow small
        if (f.lower_shadow >= shadow_ratio * body_abs and
                f.upper_shadow_pct < 0.15):
            return ("hammer", float(scoring["moderate_bull"]), "bullish")

        # Shooting Star: small body bottom, long upper shadow >= 2x body, lower shadow small
        if (f.upper_shadow >= shadow_ratio * body_abs and
                f.lower_shadow_pct < 0.15):
            return ("shooting_star", float(scoring["moderate_bear"]), "bearish")

        # Marubozu: body_pct > 0.85
        if f.body_pct > marubozu_thresh:
            if f.body > 0:
                return ("marubozu_bull", float(scoring["moderate_bull"]), "bullish")
            else:
                return ("marubozu_bear", float(scoring["moderate_bear"]), "bearish")

        return None

    def _compute_quality(
        self, o: CandleOutput, volume_confirm: bool, at_swing: bool
    ) -> int:
        """
        Quality 0-4:
            4 = strong pattern (+/-3) + vol confirm + swing context
            3 = strong pattern + (vol OR swing)
            2 = moderate pattern (+/-2)
            1 = weak pattern (+/-1) or doji
            0 = no pattern
        """
        abs_pattern = abs(o.pattern_score)

        if abs_pattern >= 3:
            if volume_confirm and at_swing:
                return 4
            if volume_confirm or at_swing:
                return 3
            return 3
        if abs_pattern >= 2:
            if volume_confirm or at_swing:
                return 3
            return 2
        if abs_pattern >= 1:
            return 1
        return 0

    def _signal_code(self, o: CandleOutput) -> str:
        """Determine signal code based on pattern."""
        name = o.pattern_name

        if name == "bullish_engulfing":
            return "V4CANDLE_BULL_ENGULF"
        if name == "bearish_engulfing":
            return "V4CANDLE_BEAR_ENGULF"
        if name == "hammer":
            return "V4CANDLE_BULL_HAMMER"
        if name == "shooting_star":
            return "V4CANDLE_BEAR_SHOOTING"
        if name == "morning_star":
            return "V4CANDLE_BULL_MORNING"
        if name == "evening_star":
            return "V4CANDLE_BEAR_EVENING"
        if name == "three_white_soldiers":
            return "V4CANDLE_BULL_THREE"
        if name == "three_black_crows":
            return "V4CANDLE_BEAR_THREE"
        if name == "doji":
            return "V4CANDLE_NEUT_DOJI"
        if name == "marubozu_bull":
            return "V4CANDLE_BULL_HAMMER"  # bullish momentum
        if name == "marubozu_bear":
            return "V4CANDLE_BEAR_SHOOTING"  # bearish momentum

        return "V4CANDLE_NEUT_NONE"
