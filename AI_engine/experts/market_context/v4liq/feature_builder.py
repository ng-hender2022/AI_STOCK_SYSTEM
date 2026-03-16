"""
V4LIQ Feature Builder
Computes liquidity features: ADTV_20d, ADTV_60d, volume_CV, zero_volume_days,
HL_Spread_20d_avg, ADTV_ratio, pct_days_above_1b, recent breakout/drought flags.

DATA LEAKAGE RULE: Day T only uses data up to close of T-1.
VN MARKET: Volume in prices_daily is share count. Value = volume * close / 1e9 for billion VND.
           If 'value' column exists, use it directly (already in VND, divide by 1e9).
"""

import sqlite3
from pathlib import Path
from dataclasses import dataclass, field

import numpy as np
import yaml

_CONFIG_PATH = Path(__file__).parent / "config.yaml"


def _load_config() -> dict:
    with open(_CONFIG_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


@dataclass
class LiqFeatures:
    """All liquidity features for 1 symbol, day T."""
    symbol: str
    date: str
    data_cutoff_date: str

    # ADTV metrics (billion VND)
    adtv_20d: float = 0.0
    adtv_60d: float = 0.0
    adtv_ratio: float = 0.0       # ADTV_20d / ADTV_60d

    # Volume consistency
    volume_cv: float = 0.0        # coefficient of variation (std/mean) of 20d volume
    zero_volume_days: int = 0     # days with volume < threshold in last 20d
    pct_days_above_1b: float = 0.0  # % of last 20d with value > 1B VND

    # Spread proxy
    hl_spread_avg: float = 0.0    # 20d average of (H-L)/C in %

    # Trend flags
    has_recent_breakout: bool = False   # any day in last 5 with value > 3x ADTV_20d
    has_recent_drought: bool = False    # any day in last 3 with value < 0.3x ADTV_20d

    # Today's value (billion VND) — the most recent day in cutoff
    today_value: float = 0.0
    today_vs_avg: float = 0.0     # today_value / adtv_20d

    has_sufficient_data: bool = False


class LiqFeatureBuilder:
    """
    Build liquidity features from market.db.

    Usage:
        builder = LiqFeatureBuilder(db_path)
        features = builder.build("FPT", "2026-03-16")
        batch = builder.build_batch(["FPT", "VNM"], "2026-03-16")
    """

    def __init__(self, db_path: str | Path):
        self.db_path = str(db_path)
        self.cfg = _load_config()
        self._has_value_col: bool | None = None

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=30)
        conn.row_factory = sqlite3.Row
        return conn

    def _check_value_column(self, conn: sqlite3.Connection) -> bool:
        """Check if prices_daily has a 'value' column."""
        if self._has_value_col is not None:
            return self._has_value_col
        cursor = conn.execute("PRAGMA table_info(prices_daily)")
        cols = {row["name"] for row in cursor.fetchall()}
        self._has_value_col = "value" in cols
        return self._has_value_col

    def _fetch_history(
        self, conn: sqlite3.Connection, symbol: str, cutoff_date: str, lookback: int
    ) -> list[dict]:
        has_value = self._check_value_column(conn)
        if has_value:
            query = (
                "SELECT date, open, high, low, close, volume, value "
                "FROM prices_daily WHERE symbol=? AND date<=? ORDER BY date DESC LIMIT ?"
            )
        else:
            query = (
                "SELECT date, open, high, low, close, volume "
                "FROM prices_daily WHERE symbol=? AND date<=? ORDER BY date DESC LIMIT ?"
            )
        rows = conn.execute(query, (symbol, cutoff_date, lookback)).fetchall()
        return [dict(r) for r in reversed(rows)]

    def build(self, symbol: str, target_date: str) -> LiqFeatures:
        """Build liquidity features. Uses only data < target_date."""
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT date FROM prices_daily WHERE symbol=? AND date<? ORDER BY date DESC LIMIT 1",
                (symbol, target_date),
            ).fetchone()

            if not row:
                return LiqFeatures(symbol=symbol, date=target_date, data_cutoff_date="")

            cutoff = row["date"]
            min_hist = self.cfg["min_history_days"]
            hist = self._fetch_history(conn, symbol, cutoff, lookback=min_hist + 10)

            feat = LiqFeatures(symbol=symbol, date=target_date, data_cutoff_date=cutoff)
            if len(hist) < min_hist:
                return feat

            self._compute(feat, hist, conn)
            feat.has_sufficient_data = True
            return feat
        finally:
            conn.close()

    def build_batch(self, symbols: list[str], target_date: str) -> list[LiqFeatures]:
        conn = self._connect()
        results = []
        try:
            for sym in symbols:
                row = conn.execute(
                    "SELECT date FROM prices_daily WHERE symbol=? AND date<? ORDER BY date DESC LIMIT 1",
                    (sym, target_date),
                ).fetchone()
                if not row:
                    results.append(LiqFeatures(symbol=sym, date=target_date, data_cutoff_date=""))
                    continue

                cutoff = row["date"]
                min_hist = self.cfg["min_history_days"]
                hist = self._fetch_history(conn, sym, cutoff, lookback=min_hist + 10)
                feat = LiqFeatures(symbol=sym, date=target_date, data_cutoff_date=cutoff)
                if len(hist) >= min_hist:
                    self._compute(feat, hist, conn)
                    feat.has_sufficient_data = True
                results.append(feat)
        finally:
            conn.close()
        return results

    def _day_value_billions(self, day: dict) -> float:
        """Compute daily traded value in billion VND.

        If 'value' column exists and is not None, use it directly (assumed VND, divide by 1e9).
        Otherwise approximate as volume * close / 1e9.
        """
        if "value" in day and day["value"] is not None:
            return day["value"] / 1e9
        return (day["volume"] * day["close"]) / 1e9

    def _compute(self, feat: LiqFeatures, hist: list[dict], conn: sqlite3.Connection) -> None:
        n = len(hist)
        short_period = self.cfg["adtv_short_period"]  # 20
        long_period = self.cfg["adtv_long_period"]     # 60
        spread_period = self.cfg["spread_period"]       # 20

        # Compute daily values in billions
        values = np.array([self._day_value_billions(d) for d in hist], dtype=float)
        volumes = np.array([d["volume"] for d in hist], dtype=float)
        closes = np.array([d["close"] for d in hist], dtype=float)
        highs = np.array([d["high"] for d in hist], dtype=float)
        lows = np.array([d["low"] for d in hist], dtype=float)

        # --- ADTV_20d and ADTV_60d ---
        last_20_values = values[-short_period:]
        feat.adtv_20d = float(np.mean(last_20_values))

        if n >= long_period:
            last_60_values = values[-long_period:]
            feat.adtv_60d = float(np.mean(last_60_values))
        else:
            feat.adtv_60d = feat.adtv_20d  # fallback

        # ADTV ratio
        if feat.adtv_60d > 1e-12:
            feat.adtv_ratio = feat.adtv_20d / feat.adtv_60d
        else:
            feat.adtv_ratio = 1.0

        # --- Volume consistency (last 20 days) ---
        last_20_volumes = volumes[-short_period:]
        mean_vol = np.mean(last_20_volumes)
        std_vol = np.std(last_20_volumes, ddof=0)
        if mean_vol > 1e-12:
            feat.volume_cv = float(std_vol / mean_vol)
        else:
            feat.volume_cv = 99.0  # essentially no volume

        zero_thresh = self.cfg["zero_volume_threshold"]
        feat.zero_volume_days = int(np.sum(last_20_volumes < zero_thresh))

        # Pct days above 1B VND
        val_thresh = self.cfg["value_1b_threshold"]
        feat.pct_days_above_1b = float(np.mean(last_20_values >= val_thresh) * 100.0)

        # --- Spread proxy ---
        # HL_Spread = (H - L) / C * 100 (%)
        last_20_idx = slice(n - spread_period, n)
        hl_spread = (highs[last_20_idx] - lows[last_20_idx]) / (closes[last_20_idx] + 1e-12) * 100.0
        feat.hl_spread_avg = float(np.mean(hl_spread))

        # --- Today's value and vs avg ---
        feat.today_value = float(values[-1])
        if feat.adtv_20d > 1e-12:
            feat.today_vs_avg = feat.today_value / feat.adtv_20d
        else:
            feat.today_vs_avg = 0.0

        # --- Recent breakout/drought ---
        breakout_thresh = self.cfg["volume_breakout_threshold"]
        drought_thresh = self.cfg["volume_drought_threshold"]
        breakout_lookback = self.cfg["breakout_lookback_days"]
        drought_lookback = self.cfg["drought_lookback_days"]

        if feat.adtv_20d > 1e-12:
            recent_ratios_breakout = values[-breakout_lookback:] / feat.adtv_20d
            feat.has_recent_breakout = bool(np.any(recent_ratios_breakout > breakout_thresh))

            recent_ratios_drought = values[-drought_lookback:] / feat.adtv_20d
            feat.has_recent_drought = bool(np.any(recent_ratios_drought < drought_thresh))
