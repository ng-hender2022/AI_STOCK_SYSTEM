"""
V4I Ichimoku Feature Builder
Tính toán 5 đường Ichimoku + tất cả derived features cho 1 symbol.

DATA LEAKAGE RULE: Ngày T chỉ dùng data đến close ngày T-1.
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
class IchimokuFeatures:
    """Container cho tất cả Ichimoku features của 1 symbol, ngày T."""
    symbol: str
    date: str                           # ngày T (feature date)
    data_cutoff_date: str               # T-1 (last data date used)

    # --- Core Ichimoku lines (tại T-1) ---
    tenkan: float = 0.0
    kijun: float = 0.0
    senkou_a: float = 0.0              # current cloud top/bottom (shifted 26 ago)
    senkou_b: float = 0.0
    chikou: float = 0.0                # close shifted back 26 (= close at T-1)
    price_26_ago: float = 0.0          # price 26 bars before T-1

    # --- Future cloud (projected from T-1) ---
    senkou_a_future: float = 0.0       # Senkou A computed at T-1, shown 26 bars ahead
    senkou_b_future: float = 0.0

    # --- Derived ---
    cloud_top: float = 0.0
    cloud_bottom: float = 0.0
    cloud_thickness: float = 0.0
    close: float = 0.0                 # close at T-1

    # --- Time theory ---
    days_since_pivot: int = 0
    pivot_type: str = ""               # "high" or "low"

    # --- Flags ---
    has_sufficient_data: bool = False


class IchimokuFeatureBuilder:
    """
    Builds Ichimoku features from market.db prices_daily.

    Usage:
        builder = IchimokuFeatureBuilder(db_path)
        features = builder.build("VNM", "2026-03-15")
        batch = builder.build_batch(["VNM", "FPT", ...], "2026-03-15")
    """

    def __init__(self, db_path: str | Path):
        self.db_path = str(db_path)
        self.cfg = _load_config()
        self._ichi = self.cfg["ichimoku"]

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=30)
        conn.row_factory = sqlite3.Row
        return conn

    def _fetch_history(
        self, conn: sqlite3.Connection, symbol: str, cutoff_date: str, lookback: int
    ) -> list[dict]:
        """Fetch daily OHLC up to and including cutoff_date."""
        rows = conn.execute(
            """
            SELECT date, open, high, low, close, volume
            FROM prices_daily
            WHERE symbol = ? AND date <= ?
            ORDER BY date DESC
            LIMIT ?
            """,
            (symbol, cutoff_date, lookback),
        ).fetchall()
        return [dict(r) for r in reversed(rows)]

    def _highest_high(self, highs: np.ndarray, period: int, idx: int) -> float:
        """Highest high over `period` bars ending at `idx` (inclusive)."""
        start = max(0, idx - period + 1)
        return float(np.max(highs[start : idx + 1]))

    def _lowest_low(self, lows: np.ndarray, period: int, idx: int) -> float:
        """Lowest low over `period` bars ending at `idx` (inclusive)."""
        start = max(0, idx - period + 1)
        return float(np.min(lows[start : idx + 1]))

    def _find_pivot(self, closes: np.ndarray, lookback: int) -> tuple[int, str]:
        """
        Find most recent pivot (local high or low) within lookback.
        Returns (days_since_pivot, "high" or "low").
        """
        if len(closes) < 5:
            return 0, ""

        n = len(closes)
        search_range = min(lookback, n - 2)

        # Walk backward to find first pivot
        for i in range(n - 2, n - 2 - search_range, -1):
            if i < 1:
                break
            # Local high
            if closes[i] > closes[i - 1] and closes[i] > closes[i + 1]:
                return n - 1 - i, "high"
            # Local low
            if closes[i] < closes[i - 1] and closes[i] < closes[i + 1]:
                return n - 1 - i, "low"

        return 0, ""

    def build(self, symbol: str, target_date: str) -> IchimokuFeatures:
        """
        Build Ichimoku features for 1 symbol on target_date.
        DATA LEAKAGE: only uses data with date < target_date.
        """
        conn = self._connect()
        try:
            # Find T-1 (last trading day before target_date)
            row = conn.execute(
                """
                SELECT date FROM prices_daily
                WHERE symbol = ? AND date < ?
                ORDER BY date DESC LIMIT 1
                """,
                (symbol, target_date),
            ).fetchone()

            if not row:
                return IchimokuFeatures(
                    symbol=symbol, date=target_date,
                    data_cutoff_date="", has_sufficient_data=False
                )
            cutoff_date = row["date"]

            min_hist = self.cfg["min_history_days"]
            hist = self._fetch_history(conn, symbol, cutoff_date, lookback=min_hist + 30)

            features = IchimokuFeatures(
                symbol=symbol, date=target_date, data_cutoff_date=cutoff_date
            )

            if len(hist) < min_hist:
                return features

            self._compute_ichimoku(features, hist)
            features.has_sufficient_data = True
            return features

        finally:
            conn.close()

    def build_batch(
        self, symbols: list[str], target_date: str
    ) -> list[IchimokuFeatures]:
        """Build features for multiple symbols."""
        conn = self._connect()
        results = []
        try:
            for sym in symbols:
                row = conn.execute(
                    "SELECT date FROM prices_daily WHERE symbol = ? AND date < ? ORDER BY date DESC LIMIT 1",
                    (sym, target_date),
                ).fetchone()
                if not row:
                    results.append(IchimokuFeatures(
                        symbol=sym, date=target_date,
                        data_cutoff_date="", has_sufficient_data=False
                    ))
                    continue

                cutoff_date = row["date"]
                min_hist = self.cfg["min_history_days"]
                hist = self._fetch_history(conn, sym, cutoff_date, lookback=min_hist + 30)

                feat = IchimokuFeatures(
                    symbol=sym, date=target_date, data_cutoff_date=cutoff_date
                )
                if len(hist) >= min_hist:
                    self._compute_ichimoku(feat, hist)
                    feat.has_sufficient_data = True
                results.append(feat)
        finally:
            conn.close()
        return results

    def _compute_ichimoku(self, features: IchimokuFeatures, hist: list[dict]) -> None:
        """Compute all Ichimoku lines and derived features."""
        highs = np.array([d["high"] or d["close"] for d in hist], dtype=float)
        lows = np.array([d["low"] or d["close"] for d in hist], dtype=float)
        closes = np.array([d["close"] for d in hist], dtype=float)
        n = len(hist)
        last = n - 1  # index of T-1

        tenkan_p = self._ichi["tenkan_period"]
        kijun_p = self._ichi["kijun_period"]
        senkou_b_p = self._ichi["senkou_b_period"]
        disp = self._ichi["displacement"]

        features.close = float(closes[last])

        # --- Tenkan (9-period midpoint) at T-1 ---
        features.tenkan = (
            self._highest_high(highs, tenkan_p, last)
            + self._lowest_low(lows, tenkan_p, last)
        ) / 2

        # --- Kijun (26-period midpoint) at T-1 ---
        features.kijun = (
            self._highest_high(highs, kijun_p, last)
            + self._lowest_low(lows, kijun_p, last)
        ) / 2

        # --- Current cloud (Senkou A & B shifted forward 26 from 26 bars ago) ---
        # The cloud at T-1 was computed from data 26 bars earlier
        cloud_idx = last - disp
        if cloud_idx >= senkou_b_p:
            tenkan_at = (
                self._highest_high(highs, tenkan_p, cloud_idx)
                + self._lowest_low(lows, tenkan_p, cloud_idx)
            ) / 2
            kijun_at = (
                self._highest_high(highs, kijun_p, cloud_idx)
                + self._lowest_low(lows, kijun_p, cloud_idx)
            ) / 2
            features.senkou_a = (tenkan_at + kijun_at) / 2
            features.senkou_b = (
                self._highest_high(highs, senkou_b_p, cloud_idx)
                + self._lowest_low(lows, senkou_b_p, cloud_idx)
            ) / 2
        else:
            features.senkou_a = features.tenkan
            features.senkou_b = features.kijun

        features.cloud_top = max(features.senkou_a, features.senkou_b)
        features.cloud_bottom = min(features.senkou_a, features.senkou_b)
        features.cloud_thickness = features.cloud_top - features.cloud_bottom

        # --- Chikou Span = close at T-1; compare to price 26 bars ago ---
        features.chikou = float(closes[last])
        if last >= disp:
            features.price_26_ago = float(closes[last - disp])

        # --- Future cloud (Senkou A & B computed at T-1, projected forward) ---
        features.senkou_a_future = (features.tenkan + features.kijun) / 2
        if last >= senkou_b_p:
            features.senkou_b_future = (
                self._highest_high(highs, senkou_b_p, last)
                + self._lowest_low(lows, senkou_b_p, last)
            ) / 2
        else:
            features.senkou_b_future = features.senkou_b

        # --- Time theory: find pivot ---
        pivot_lookback = self.cfg["time_theory"]["pivot_lookback"]
        days, ptype = self._find_pivot(closes, pivot_lookback)
        features.days_since_pivot = days
        features.pivot_type = ptype
