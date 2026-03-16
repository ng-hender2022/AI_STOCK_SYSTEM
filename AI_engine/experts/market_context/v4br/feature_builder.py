"""
V4BR Feature Builder
Computes breadth indicators across the entire 91-stock universe.

DATA LEAKAGE RULE: target_date T uses only data with date < T.
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
class BreadthFeatures:
    """Container for all breadth features on date T (computed from data < T)."""
    date: str                            # target date T
    data_cutoff_date: str                # last data date used (T-1)

    # --- Core breadth indicators ---
    pct_above_sma50: float = 0.0         # % of stocks with close > SMA(50)
    ad_ratio: float = 1.0                # advancing / declining stocks (1-day)
    net_new_highs: float = 0.0           # count(new 20d highs) - count(new 20d lows)
    breadth_momentum: float = 0.0        # 5-day change in pct_above_sma50 (in pp)

    # --- Sub-scores (each -4..+4) ---
    score_pct_above_sma50: float = 0.0
    score_ad_ratio: float = 0.0
    score_net_new_highs: float = 0.0
    score_breadth_momentum: float = 0.0

    # --- Divergence detection data ---
    vnindex_at_20d_high: bool = False
    vnindex_at_20d_low: bool = False
    pct_above_sma50_declining_days: int = 0
    pct_above_sma50_rising_days: int = 0

    # --- Counts ---
    total_stocks_with_data: int = 0
    advancing_count: int = 0
    declining_count: int = 0
    new_high_count: int = 0
    new_low_count: int = 0

    # --- Flags ---
    has_sufficient_data: bool = False


class BreadthFeatureBuilder:
    """
    Builds breadth features from market.db using all tradable stocks.

    Usage:
        builder = BreadthFeatureBuilder(db_path)
        features = builder.build(target_date="2026-03-15")
    """

    def __init__(self, db_path: str | Path):
        self.db_path = str(db_path)
        self.cfg = _load_config()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=30)
        conn.row_factory = sqlite3.Row
        return conn

    def _get_cutoff_date(self, conn: sqlite3.Connection, target_date: str) -> str | None:
        """Find the most recent trading date strictly before target_date."""
        row = conn.execute(
            """
            SELECT date FROM prices_daily
            WHERE symbol = 'VNINDEX' AND date < ?
            ORDER BY date DESC LIMIT 1
            """,
            (target_date,),
        ).fetchone()
        return row["date"] if row else None

    def _fetch_all_stocks_history(
        self, conn: sqlite3.Connection, cutoff_date: str, lookback: int
    ) -> dict[str, list[dict]]:
        """Fetch daily OHLCV for all tradable stocks, up to cutoff_date."""
        rows = conn.execute(
            """
            SELECT p.symbol, p.date, p.open, p.high, p.low, p.close, p.volume
            FROM prices_daily p
            JOIN symbols_master s ON p.symbol = s.symbol
            WHERE s.is_tradable = 1
              AND p.symbol != 'VNINDEX'
              AND p.date <= ?
              AND p.date >= date(?, '-' || ? || ' days')
            ORDER BY p.symbol, p.date
            """,
            (cutoff_date, cutoff_date, lookback * 2),
        ).fetchall()

        result: dict[str, list[dict]] = {}
        for r in rows:
            sym = r["symbol"]
            if sym not in result:
                result[sym] = []
            result[sym].append(dict(r))
        return result

    def _fetch_vnindex_history(
        self, conn: sqlite3.Connection, cutoff_date: str, lookback: int = 30
    ) -> list[dict]:
        """Fetch VNINDEX history up to cutoff_date."""
        rows = conn.execute(
            """
            SELECT date, close FROM prices_daily
            WHERE symbol = 'VNINDEX' AND date <= ?
            ORDER BY date DESC LIMIT ?
            """,
            (cutoff_date, lookback),
        ).fetchall()
        return [dict(r) for r in reversed(rows)]

    def build(self, target_date: str) -> BreadthFeatures:
        """
        Build breadth features for target_date.
        DATA LEAKAGE: only uses data with date < target_date.
        """
        conn = self._connect()
        try:
            cutoff_date = self._get_cutoff_date(conn, target_date)
            if not cutoff_date:
                return BreadthFeatures(
                    date=target_date, data_cutoff_date="",
                    has_sufficient_data=False,
                )

            features = BreadthFeatures(
                date=target_date, data_cutoff_date=cutoff_date,
            )

            sma_period = self.cfg["indicators"]["sma_period"]
            hi_lo_lookback = self.cfg["indicators"]["new_high_low_lookback"]
            momentum_period = self.cfg["indicators"]["breadth_momentum_period"]
            min_history = self.cfg["data"]["min_history_days"]
            min_stocks = self.cfg["data"]["min_stocks_with_data"]

            # Need enough lookback for SMA50 + momentum (5 extra days for historical pct)
            total_lookback = max(sma_period + momentum_period + 10, min_history)
            stocks_data = self._fetch_all_stocks_history(
                conn, cutoff_date, total_lookback,
            )

            # --- Compute per-stock metrics at cutoff_date ---
            above_sma50_count = 0
            advancing = 0
            declining = 0
            new_highs = 0
            new_lows = 0
            valid_stocks = 0

            for sym, data in stocks_data.items():
                closes = [d["close"] for d in data if d["close"] and d["close"] > 0]
                if len(closes) < sma_period:
                    continue

                valid_stocks += 1
                current_close = closes[-1]

                # pct_above_sma50
                sma50 = float(np.mean(closes[-sma_period:]))
                if current_close > sma50:
                    above_sma50_count += 1

                # A/D ratio (1-day)
                if len(closes) >= 2:
                    if closes[-1] > closes[-2]:
                        advancing += 1
                    elif closes[-1] < closes[-2]:
                        declining += 1

                # New 20-day highs/lows
                if len(closes) >= hi_lo_lookback:
                    lookback_window = closes[-hi_lo_lookback:]
                    if current_close >= max(lookback_window):
                        new_highs += 1
                    if current_close <= min(lookback_window):
                        new_lows += 1

            if valid_stocks < min_stocks:
                features.has_sufficient_data = False
                return features

            # --- Set indicator values ---
            features.total_stocks_with_data = valid_stocks
            features.advancing_count = advancing
            features.declining_count = declining
            features.new_high_count = new_highs
            features.new_low_count = new_lows

            features.pct_above_sma50 = (above_sma50_count / valid_stocks) * 100.0
            features.net_new_highs = float(new_highs - new_lows)

            # A/D ratio
            if declining > 0:
                features.ad_ratio = advancing / declining
            elif advancing > 0:
                features.ad_ratio = 5.0  # cap when no decliners
            else:
                features.ad_ratio = 1.0

            # --- Breadth momentum: need historical pct_above_sma50 ---
            features.breadth_momentum = self._compute_breadth_momentum(
                stocks_data, sma_period, momentum_period, cutoff_date,
            )

            # --- Divergence detection ---
            vnindex_hist = self._fetch_vnindex_history(conn, cutoff_date, 30)
            self._compute_divergence_data(
                features, vnindex_hist, stocks_data,
                sma_period, momentum_period, cutoff_date,
            )

            # --- Compute sub-scores ---
            features.score_pct_above_sma50 = self._score_pct_above_sma50(
                features.pct_above_sma50
            )
            features.score_ad_ratio = self._score_ad_ratio(features.ad_ratio)
            features.score_net_new_highs = self._score_net_new_highs(
                features.net_new_highs
            )
            features.score_breadth_momentum = self._score_breadth_momentum(
                features.breadth_momentum
            )

            features.has_sufficient_data = True
            return features

        finally:
            conn.close()

    def _compute_breadth_momentum(
        self,
        stocks_data: dict[str, list[dict]],
        sma_period: int,
        momentum_period: int,
        cutoff_date: str,
    ) -> float:
        """
        Compute 5-day change in pct_above_sma50 (in percentage points).
        We need pct_above_sma50 at cutoff_date and at cutoff_date - momentum_period days.
        """
        # Get all unique dates across all stocks, sorted
        all_dates: set[str] = set()
        for sym, data in stocks_data.items():
            for d in data:
                all_dates.add(d["date"])
        sorted_dates = sorted(all_dates)

        if cutoff_date not in sorted_dates:
            return 0.0

        cutoff_idx = sorted_dates.index(cutoff_date)
        if cutoff_idx < momentum_period:
            return 0.0

        past_date = sorted_dates[cutoff_idx - momentum_period]

        # Compute pct_above_sma50 at past_date
        above_count_past = 0
        valid_past = 0
        for sym, data in stocks_data.items():
            # Get closes up to past_date
            closes_past = [
                d["close"] for d in data
                if d["date"] <= past_date and d["close"] and d["close"] > 0
            ]
            if len(closes_past) < sma_period:
                continue
            valid_past += 1
            sma50_past = float(np.mean(closes_past[-sma_period:]))
            if closes_past[-1] > sma50_past:
                above_count_past += 1

        if valid_past == 0:
            return 0.0

        pct_past = (above_count_past / valid_past) * 100.0

        # Current pct is already computed in the caller; recompute here for isolation
        above_count_now = 0
        valid_now = 0
        for sym, data in stocks_data.items():
            closes_now = [
                d["close"] for d in data
                if d["date"] <= cutoff_date and d["close"] and d["close"] > 0
            ]
            if len(closes_now) < sma_period:
                continue
            valid_now += 1
            sma50_now = float(np.mean(closes_now[-sma_period:]))
            if closes_now[-1] > sma50_now:
                above_count_now += 1

        if valid_now == 0:
            return 0.0

        pct_now = (above_count_now / valid_now) * 100.0
        return pct_now - pct_past

    def _compute_divergence_data(
        self,
        features: BreadthFeatures,
        vnindex_hist: list[dict],
        stocks_data: dict[str, list[dict]],
        sma_period: int,
        momentum_period: int,
        cutoff_date: str,
    ) -> None:
        """Detect VNINDEX vs breadth divergence conditions."""
        hi_lo_lookback = self.cfg["divergence"]["vnindex_high_lookback"]
        decline_threshold = self.cfg["divergence"]["breadth_decline_days"]

        if len(vnindex_hist) < hi_lo_lookback:
            return

        vn_closes = [d["close"] for d in vnindex_hist]

        # VNINDEX at 20-day high/low
        recent_window = vn_closes[-hi_lo_lookback:]
        features.vnindex_at_20d_high = bool(vn_closes[-1] >= max(recent_window))
        features.vnindex_at_20d_low = bool(vn_closes[-1] <= min(recent_window))

        # Check if pct_above_sma50 has been declining for N consecutive days
        # Compute daily pct_above_sma50 for last (decline_threshold + 1) days
        all_dates: set[str] = set()
        for sym, data in stocks_data.items():
            for d in data:
                all_dates.add(d["date"])
        sorted_dates = sorted(all_dates)

        if cutoff_date not in sorted_dates:
            return

        cutoff_idx = sorted_dates.index(cutoff_date)
        check_days = decline_threshold + 1
        if cutoff_idx < check_days:
            return

        daily_pct = []
        for offset in range(check_days):
            check_date = sorted_dates[cutoff_idx - (check_days - 1 - offset)]
            above = 0
            valid = 0
            for sym, data in stocks_data.items():
                closes = [
                    d["close"] for d in data
                    if d["date"] <= check_date and d["close"] and d["close"] > 0
                ]
                if len(closes) < sma_period:
                    continue
                valid += 1
                if closes[-1] > float(np.mean(closes[-sma_period:])):
                    above += 1
            if valid > 0:
                daily_pct.append(above / valid * 100.0)
            else:
                daily_pct.append(0.0)

        # Count consecutive declining days (from most recent backwards)
        declining_days = 0
        for i in range(len(daily_pct) - 1, 0, -1):
            if daily_pct[i] < daily_pct[i - 1]:
                declining_days += 1
            else:
                break
        features.pct_above_sma50_declining_days = declining_days

        # Count consecutive rising days
        rising_days = 0
        for i in range(len(daily_pct) - 1, 0, -1):
            if daily_pct[i] > daily_pct[i - 1]:
                rising_days += 1
            else:
                break
        features.pct_above_sma50_rising_days = rising_days

    # -------------------------------------------------------------------
    # Sub-score functions (each returns -4..+4 per rulebook table)
    # -------------------------------------------------------------------

    @staticmethod
    def _score_pct_above_sma50(pct: float) -> float:
        """Score pct_above_sma50 (in %, 0-100 scale)."""
        if pct > 80:
            return 4.0
        elif pct > 65:
            return 3.0
        elif pct > 55:
            return 2.0
        elif pct > 50:
            return 1.0
        elif pct > 45:
            return 0.0
        elif pct > 40:
            return -1.0
        elif pct > 30:
            return -2.0
        elif pct > 20:
            return -3.0
        else:
            return -4.0

    @staticmethod
    def _score_ad_ratio(ratio: float) -> float:
        """Score advance/decline ratio."""
        if ratio > 3.0:
            return 4.0
        elif ratio > 2.0:
            return 3.0
        elif ratio > 1.5:
            return 2.0
        elif ratio > 1.1:
            return 1.0
        elif ratio > 0.8:
            return 0.0
        elif ratio > 0.67:
            return -1.0
        elif ratio > 0.5:
            return -2.0
        elif ratio > 0.33:
            return -3.0
        else:
            return -4.0

    @staticmethod
    def _score_net_new_highs(net: float) -> float:
        """Score net new highs (highs - lows count)."""
        if net > 15:
            return 4.0
        elif net > 8:
            return 3.0
        elif net > 3:
            return 2.0
        elif net > 1:
            return 1.0
        elif net >= -1:
            return 0.0
        elif net >= -3:
            return -1.0
        elif net >= -8:
            return -2.0
        elif net >= -15:
            return -3.0
        else:
            return -4.0

    @staticmethod
    def _score_breadth_momentum(momentum_pp: float) -> float:
        """Score breadth momentum (5-day change in pct_above_sma50, in pp)."""
        if momentum_pp > 20:
            return 4.0
        elif momentum_pp > 10:
            return 3.0
        elif momentum_pp > 5:
            return 2.0
        elif momentum_pp > 2:
            return 1.0
        elif momentum_pp >= -2:
            return 0.0
        elif momentum_pp >= -5:
            return -1.0
        elif momentum_pp >= -10:
            return -2.0
        elif momentum_pp >= -20:
            return -3.0
        else:
            return -4.0
