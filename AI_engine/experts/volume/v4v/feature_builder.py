"""
V4V Feature Builder
Computes vol_ratio, vol_trend_5, vol_trend_10, climax flag, and 1-day price return.

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


def _sma(data: np.ndarray, period: int) -> np.ndarray:
    """Compute SMA. Returns array same length as data (NaN-padded)."""
    result = np.full_like(data, np.nan, dtype=float)
    if len(data) < period:
        return result
    for i in range(period - 1, len(data)):
        result[i] = np.mean(data[i - period + 1 : i + 1])
    return result


@dataclass
class VolFeatures:
    """All volume features for 1 symbol, day T."""
    symbol: str
    date: str
    data_cutoff_date: str

    close: float = 0.0
    prev_close: float = 0.0
    volume: float = 0.0
    price_return: float = 0.0        # 1-day return

    # --- Volume indicators at T-1 ---
    vol_ratio: float = 0.0           # volume / SMA(volume, 20)
    vol_trend_5: float = 0.0         # SMA(volume, 5) / SMA(volume, 20)
    vol_trend_10: float = 0.0        # SMA(volume, 10) / SMA(volume, 20)
    climax: bool = False             # volume > 3 * SMA(volume, 20)

    has_sufficient_data: bool = False


class VolFeatureBuilder:
    """
    Build volume features from market.db.

    Usage:
        builder = VolFeatureBuilder(db_path)
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
            "SELECT date, close, volume FROM prices_daily WHERE symbol=? AND date<=? ORDER BY date DESC LIMIT ?",
            (symbol, cutoff_date, lookback),
        ).fetchall()
        return [dict(r) for r in reversed(rows)]

    def build(self, symbol: str, target_date: str) -> VolFeatures:
        """Build volume features. Uses only data < target_date."""
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT date FROM prices_daily WHERE symbol=? AND date<? ORDER BY date DESC LIMIT 1",
                (symbol, target_date),
            ).fetchone()

            if not row:
                return VolFeatures(symbol=symbol, date=target_date, data_cutoff_date="")

            cutoff = row["date"]
            min_hist = self.cfg["min_history_days"]
            hist = self._fetch_history(conn, symbol, cutoff, lookback=min_hist + 10)

            feat = VolFeatures(symbol=symbol, date=target_date, data_cutoff_date=cutoff)
            if len(hist) < min_hist:
                return feat

            self._compute(feat, hist)
            feat.has_sufficient_data = True
            return feat
        finally:
            conn.close()

    def build_batch(self, symbols: list[str], target_date: str) -> list[VolFeatures]:
        conn = self._connect()
        results = []
        try:
            for sym in symbols:
                row = conn.execute(
                    "SELECT date FROM prices_daily WHERE symbol=? AND date<? ORDER BY date DESC LIMIT 1",
                    (sym, target_date),
                ).fetchone()
                if not row:
                    results.append(VolFeatures(symbol=sym, date=target_date, data_cutoff_date=""))
                    continue

                cutoff = row["date"]
                min_hist = self.cfg["min_history_days"]
                hist = self._fetch_history(conn, sym, cutoff, lookback=min_hist + 10)
                feat = VolFeatures(symbol=sym, date=target_date, data_cutoff_date=cutoff)
                if len(hist) >= min_hist:
                    self._compute(feat, hist)
                    feat.has_sufficient_data = True
                results.append(feat)
        finally:
            conn.close()
        return results

    def _compute(self, feat: VolFeatures, hist: list[dict]) -> None:
        closes = np.array([d["close"] for d in hist], dtype=float)
        volumes = np.array([d["volume"] for d in hist], dtype=float)
        n = len(closes)
        last = n - 1

        feat.close = float(closes[last])
        feat.volume = float(volumes[last])

        # 1-day price return
        if last >= 1:
            feat.prev_close = float(closes[last - 1])
            feat.price_return = (closes[last] - closes[last - 1]) / (closes[last - 1] + 1e-9)
        else:
            feat.prev_close = feat.close
            feat.price_return = 0.0

        # Volume SMAs
        sma_period = self.cfg["vol_sma_period"]
        vol_sma20 = _sma(volumes, sma_period)

        if not np.isnan(vol_sma20[last]) and vol_sma20[last] > 0:
            feat.vol_ratio = float(volumes[last] / vol_sma20[last])
            feat.climax = bool(volumes[last] > self.cfg["climax_threshold"] * vol_sma20[last])

        # vol_trend_5 = SMA(volume, 5) / SMA(volume, 20)
        trend_short = self.cfg["vol_trend_short"]
        vol_sma5 = _sma(volumes, trend_short)
        if not np.isnan(vol_sma5[last]) and not np.isnan(vol_sma20[last]) and vol_sma20[last] > 0:
            feat.vol_trend_5 = float(vol_sma5[last] / vol_sma20[last])

        # vol_trend_10 = SMA(volume, 10) / SMA(volume, 20)
        trend_long = self.cfg["vol_trend_long"]
        vol_sma10 = _sma(volumes, trend_long)
        if not np.isnan(vol_sma10[last]) and not np.isnan(vol_sma20[last]) and vol_sma20[last] > 0:
            feat.vol_trend_10 = float(vol_sma10[last] / vol_sma20[last])
