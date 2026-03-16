"""
V4MA Feature Builder
Computes EMA10, EMA20, SMA50, SMA100, SMA200 and all derived features.

DATA LEAKAGE RULE: Day T only uses data up to close of T-1.
"""

import sqlite3
from pathlib import Path
from dataclasses import dataclass

import numpy as np
import yaml

_CONFIG_PATH = Path(__file__).parent / "config.yaml"


def _load_config() -> dict:
    with open(_CONFIG_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def _ema(data: np.ndarray, period: int) -> np.ndarray:
    """Compute EMA. Returns array same length as data (NaN-padded)."""
    result = np.full_like(data, np.nan, dtype=float)
    if len(data) < period:
        return result
    alpha = 2.0 / (period + 1)
    result[period - 1] = np.mean(data[:period])
    for i in range(period, len(data)):
        result[i] = alpha * data[i] + (1 - alpha) * result[i - 1]
    return result


def _sma(data: np.ndarray, period: int) -> np.ndarray:
    """Compute SMA. Returns array same length as data (NaN-padded)."""
    result = np.full_like(data, np.nan, dtype=float)
    if len(data) < period:
        return result
    for i in range(period - 1, len(data)):
        result[i] = np.mean(data[i - period + 1 : i + 1])
    return result


@dataclass
class MAFeatures:
    """All MA features for 1 symbol, day T."""
    symbol: str
    date: str
    data_cutoff_date: str

    close: float = 0.0

    # --- MA values at T-1 ---
    ema10: float = 0.0
    ema20: float = 0.0
    sma50: float = 0.0
    sma100: float = 0.0
    sma200: float = 0.0

    # --- Distance: (close - MA) / MA ---
    dist_ema10: float = 0.0
    dist_ema20: float = 0.0
    dist_ma50: float = 0.0
    dist_ma100: float = 0.0
    dist_ma200: float = 0.0

    # --- Slopes: (MA_now - MA_5_ago) / MA_5_ago ---
    ema10_slope: float = 0.0
    ema20_slope: float = 0.0
    ma50_slope: float = 0.0
    ma100_slope: float = 0.0
    ma200_slope: float = 0.0

    # --- Cross-over flags (at T-1) ---
    ema10_over_ema20: int = 0      # 1 if ema10 > ema20, -1 if <
    ma50_over_ma100: int = 0       # 1 if sma50 > sma100, -1 if <
    ma100_over_ma200: int = 0      # 1 if sma100 > sma200, -1 if <
    ma50_over_ma200: int = 0       # 1 if sma50 > sma200, -1 if <

    # --- Cross events (just happened at T-1) ---
    golden_cross: bool = False     # sma50 crossed above sma200
    death_cross: bool = False      # sma50 crossed below sma200
    short_cross_up: bool = False   # ema10 crossed above ema20
    short_cross_down: bool = False # ema10 crossed below ema20

    has_sufficient_data: bool = False


class MAFeatureBuilder:
    """
    Build MA features from market.db.

    Usage:
        builder = MAFeatureBuilder(db_path)
        features = builder.build("FPT", "2026-03-16")
        batch = builder.build_batch(["FPT", "VNM"], "2026-03-16")
    """

    def __init__(self, db_path: str | Path):
        self.db_path = str(db_path)
        self.cfg = _load_config()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=30)
        conn.row_factory = sqlite3.Row
        return conn

    def _fetch_history(
        self, conn: sqlite3.Connection, symbol: str, cutoff_date: str, lookback: int
    ) -> list[dict]:
        rows = conn.execute(
            "SELECT date, close FROM prices_daily WHERE symbol=? AND date<=? ORDER BY date DESC LIMIT ?",
            (symbol, cutoff_date, lookback),
        ).fetchall()
        return [dict(r) for r in reversed(rows)]

    def build(self, symbol: str, target_date: str) -> MAFeatures:
        """Build MA features. Uses only data < target_date."""
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT date FROM prices_daily WHERE symbol=? AND date<? ORDER BY date DESC LIMIT 1",
                (symbol, target_date),
            ).fetchone()

            if not row:
                return MAFeatures(symbol=symbol, date=target_date, data_cutoff_date="")

            cutoff = row["date"]
            min_hist = self.cfg["min_history_days"]
            hist = self._fetch_history(conn, symbol, cutoff, lookback=min_hist + 20)

            feat = MAFeatures(symbol=symbol, date=target_date, data_cutoff_date=cutoff)
            if len(hist) < min_hist:
                return feat

            self._compute(feat, hist)
            feat.has_sufficient_data = True
            return feat
        finally:
            conn.close()

    def build_batch(self, symbols: list[str], target_date: str) -> list[MAFeatures]:
        conn = self._connect()
        results = []
        try:
            for sym in symbols:
                row = conn.execute(
                    "SELECT date FROM prices_daily WHERE symbol=? AND date<? ORDER BY date DESC LIMIT 1",
                    (sym, target_date),
                ).fetchone()
                if not row:
                    results.append(MAFeatures(symbol=sym, date=target_date, data_cutoff_date=""))
                    continue

                cutoff = row["date"]
                min_hist = self.cfg["min_history_days"]
                hist = self._fetch_history(conn, sym, cutoff, lookback=min_hist + 20)
                feat = MAFeatures(symbol=sym, date=target_date, data_cutoff_date=cutoff)
                if len(hist) >= min_hist:
                    self._compute(feat, hist)
                    feat.has_sufficient_data = True
                results.append(feat)
        finally:
            conn.close()
        return results

    def _compute(self, feat: MAFeatures, hist: list[dict]) -> None:
        closes = np.array([d["close"] for d in hist], dtype=float)
        n = len(closes)
        last = n - 1
        slope_w = self.cfg["slope_window"]

        feat.close = float(closes[last])

        # Compute MAs
        ema10_arr = _ema(closes, 10)
        ema20_arr = _ema(closes, 20)
        sma50_arr = _sma(closes, 50)
        sma100_arr = _sma(closes, 100)
        sma200_arr = _sma(closes, 200)

        feat.ema10 = float(ema10_arr[last])
        feat.ema20 = float(ema20_arr[last])
        feat.sma50 = float(sma50_arr[last])
        feat.sma100 = float(sma100_arr[last])
        feat.sma200 = float(sma200_arr[last])

        # Distances
        c = feat.close
        feat.dist_ema10 = (c - feat.ema10) / (feat.ema10 + 1e-9)
        feat.dist_ema20 = (c - feat.ema20) / (feat.ema20 + 1e-9)
        feat.dist_ma50 = (c - feat.sma50) / (feat.sma50 + 1e-9)
        feat.dist_ma100 = (c - feat.sma100) / (feat.sma100 + 1e-9)
        feat.dist_ma200 = (c - feat.sma200) / (feat.sma200 + 1e-9)

        # Slopes
        if last >= slope_w:
            if not np.isnan(ema10_arr[last - slope_w]):
                feat.ema10_slope = float(
                    (ema10_arr[last] - ema10_arr[last - slope_w]) / (ema10_arr[last - slope_w] + 1e-9)
                )
            if not np.isnan(ema20_arr[last - slope_w]):
                feat.ema20_slope = float(
                    (ema20_arr[last] - ema20_arr[last - slope_w]) / (ema20_arr[last - slope_w] + 1e-9)
                )
            if not np.isnan(sma50_arr[last - slope_w]):
                feat.ma50_slope = float(
                    (sma50_arr[last] - sma50_arr[last - slope_w]) / (sma50_arr[last - slope_w] + 1e-9)
                )
            if not np.isnan(sma100_arr[last - slope_w]):
                feat.ma100_slope = float(
                    (sma100_arr[last] - sma100_arr[last - slope_w]) / (sma100_arr[last - slope_w] + 1e-9)
                )
            if not np.isnan(sma200_arr[last - slope_w]):
                feat.ma200_slope = float(
                    (sma200_arr[last] - sma200_arr[last - slope_w]) / (sma200_arr[last - slope_w] + 1e-9)
                )

        # Cross-over flags
        feat.ema10_over_ema20 = 1 if feat.ema10 > feat.ema20 else -1
        feat.ma50_over_ma100 = 1 if feat.sma50 > feat.sma100 else -1
        feat.ma100_over_ma200 = 1 if feat.sma100 > feat.sma200 else -1
        feat.ma50_over_ma200 = 1 if feat.sma50 > feat.sma200 else -1

        # Cross events (check if cross just happened: different sign today vs yesterday)
        if last >= 1:
            if not np.isnan(sma50_arr[last - 1]) and not np.isnan(sma200_arr[last - 1]):
                prev_diff = sma50_arr[last - 1] - sma200_arr[last - 1]
                curr_diff = sma50_arr[last] - sma200_arr[last]
                if prev_diff <= 0 < curr_diff:
                    feat.golden_cross = True
                elif prev_diff >= 0 > curr_diff:
                    feat.death_cross = True

            if not np.isnan(ema10_arr[last - 1]) and not np.isnan(ema20_arr[last - 1]):
                prev_diff = ema10_arr[last - 1] - ema20_arr[last - 1]
                curr_diff = ema10_arr[last] - ema20_arr[last]
                if prev_diff <= 0 < curr_diff:
                    feat.short_cross_up = True
                elif prev_diff >= 0 > curr_diff:
                    feat.short_cross_down = True
