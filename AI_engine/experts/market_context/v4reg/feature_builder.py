"""
V4REG Feature Builder
Tính toán tất cả features cần thiết cho regime scoring.

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
class RegimeFeatures:
    """Container cho tất cả features ngày T (tính từ data đến T-1)."""
    date: str                           # ngày T (feature date)
    data_cutoff_date: str               # T-1 (last data date used)

    # --- VNINDEX data (tại T-1) ---
    vnindex_close: float = 0.0
    vnindex_ma20: float = 0.0
    vnindex_ma50: float = 0.0
    vnindex_ma200: float = 0.0
    vnindex_ma20_slope: float = 0.0     # slope of MA20 over 5 days
    vnindex_ma50_slope: float = 0.0
    vnindex_return_1d: float = 0.0      # 1-day return tại T-1
    vnindex_return_20d: float = 0.0
    vnindex_return_60d: float = 0.0
    vnindex_drawdown: float = 0.0       # drawdown from 120-day high

    # --- Breadth (tại T-1) ---
    pct_above_ma50: float = 0.0         # % of 91 stocks above their MA50
    advance_decline_ratio: float = 1.0  # A/D ratio smoothed

    # --- Volatility (tại T-1) ---
    vnindex_atr: float = 0.0
    vnindex_atr_pct: float = 0.0        # ATR / close
    atr_pct_percentile: float = 50.0    # percentile within lookback

    # --- Liquidity (tại T-1) ---
    market_volume_ratio: float = 1.0    # total market volume / MA20 volume

    # --- Flags ---
    has_sufficient_data: bool = False


class RegimeFeatureBuilder:
    """
    Builds regime features from market.db.

    Usage:
        builder = RegimeFeatureBuilder(db_path)
        features = builder.build(target_date="2026-03-15")
    """

    def __init__(self, db_path: str | Path):
        self.db_path = str(db_path)
        self.cfg = _load_config()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=30)
        conn.row_factory = sqlite3.Row
        return conn

    def _fetch_vnindex_history(
        self, conn: sqlite3.Connection, cutoff_date: str, lookback: int = 250
    ) -> list[dict]:
        """Fetch VNINDEX daily prices up to and including cutoff_date."""
        rows = conn.execute(
            """
            SELECT date, open, high, low, close, volume, value
            FROM prices_daily
            WHERE symbol = 'VNINDEX' AND date <= ?
            ORDER BY date DESC
            LIMIT ?
            """,
            (cutoff_date, lookback),
        ).fetchall()
        return [dict(r) for r in reversed(rows)]

    def _fetch_all_stocks_closes(
        self, conn: sqlite3.Connection, cutoff_date: str, lookback: int = 60
    ) -> dict[str, list[dict]]:
        """Fetch daily close+volume for all tradable stocks, grouped by symbol."""
        rows = conn.execute(
            """
            SELECT p.symbol, p.date, p.close, p.volume
            FROM prices_daily p
            JOIN symbols_master s ON p.symbol = s.symbol
            WHERE s.is_tradable = 1
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

    def build(self, target_date: str) -> RegimeFeatures:
        """
        Build features cho ngày target_date.
        DATA LEAKAGE: chỉ dùng data đến T-1.

        Args:
            target_date: ngày T (format YYYY-MM-DD)
        """
        conn = self._connect()
        try:
            # Tìm ngày giao dịch gần nhất trước target_date (T-1)
            row = conn.execute(
                """
                SELECT date FROM prices_daily
                WHERE symbol = 'VNINDEX' AND date < ?
                ORDER BY date DESC LIMIT 1
                """,
                (target_date,),
            ).fetchone()

            if not row:
                return RegimeFeatures(
                    date=target_date, data_cutoff_date="", has_sufficient_data=False
                )
            cutoff_date = row["date"]

            features = RegimeFeatures(
                date=target_date, data_cutoff_date=cutoff_date
            )

            # Fetch data
            vn_hist = self._fetch_vnindex_history(conn, cutoff_date, lookback=250)
            if len(vn_hist) < 60:
                features.has_sufficient_data = False
                return features

            stocks_data = self._fetch_all_stocks_closes(conn, cutoff_date, lookback=60)

            # Compute features
            self._compute_vnindex_features(features, vn_hist)
            self._compute_breadth_features(features, stocks_data, cutoff_date)
            self._compute_volatility_features(features, vn_hist)
            self._compute_liquidity_features(features, vn_hist, stocks_data)

            features.has_sufficient_data = True
            return features

        finally:
            conn.close()

    def _compute_vnindex_features(
        self, features: RegimeFeatures, hist: list[dict]
    ) -> None:
        """Compute VNINDEX trend features."""
        closes = np.array([d["close"] for d in hist], dtype=float)
        n = len(closes)

        features.vnindex_close = closes[-1]

        # Moving averages
        if n >= 20:
            features.vnindex_ma20 = float(np.mean(closes[-20:]))
        if n >= 50:
            features.vnindex_ma50 = float(np.mean(closes[-50:]))
        if n >= 200:
            features.vnindex_ma200 = float(np.mean(closes[-200:]))

        # MA slopes (change over slope_window days)
        slope_w = self.cfg["trend_structure"]["slope_window"]
        if n >= 20 + slope_w:
            ma20_now = np.mean(closes[-20:])
            ma20_prev = np.mean(closes[-(20 + slope_w) : -slope_w])
            features.vnindex_ma20_slope = float(
                (ma20_now - ma20_prev) / (ma20_prev + 1e-9)
            )
        if n >= 50 + slope_w:
            ma50_now = np.mean(closes[-50:])
            ma50_prev = np.mean(closes[-(50 + slope_w) : -slope_w])
            features.vnindex_ma50_slope = float(
                (ma50_now - ma50_prev) / (ma50_prev + 1e-9)
            )

        # Returns
        if n >= 2:
            features.vnindex_return_1d = float(
                (closes[-1] - closes[-2]) / (closes[-2] + 1e-9)
            )
        if n >= 21:
            features.vnindex_return_20d = float(
                (closes[-1] - closes[-21]) / (closes[-21] + 1e-9)
            )
        if n >= 61:
            features.vnindex_return_60d = float(
                (closes[-1] - closes[-61]) / (closes[-61] + 1e-9)
            )

        # Drawdown from rolling high
        dd_lookback = self.cfg["drawdown"]["lookback"]
        if n >= dd_lookback:
            rolling_high = float(np.max(closes[-dd_lookback:]))
        else:
            rolling_high = float(np.max(closes))
        features.vnindex_drawdown = float(
            (closes[-1] - rolling_high) / (rolling_high + 1e-9)
        )

    def _compute_breadth_features(
        self,
        features: RegimeFeatures,
        stocks_data: dict[str, list[dict]],
        cutoff_date: str,
    ) -> None:
        """Compute market breadth: % above MA50, A/D ratio."""
        ma_period = self.cfg["breadth"]["ma_period"]
        above_count = 0
        advance_count = 0
        decline_count = 0
        total_count = 0

        for sym, data in stocks_data.items():
            if len(data) < 2:
                continue
            # Filter data up to cutoff_date
            closes = [d["close"] for d in data if d["close"] and d["close"] > 0]
            if len(closes) < ma_period:
                continue

            total_count += 1
            current_close = closes[-1]
            ma50 = float(np.mean(closes[-ma_period:]))

            if current_close > ma50:
                above_count += 1

            # A/D: compare last close vs previous close
            if len(closes) >= 2:
                if closes[-1] > closes[-2]:
                    advance_count += 1
                elif closes[-1] < closes[-2]:
                    decline_count += 1

        if total_count > 0:
            features.pct_above_ma50 = above_count / total_count

        if decline_count > 0:
            features.advance_decline_ratio = advance_count / decline_count
        elif advance_count > 0:
            features.advance_decline_ratio = 5.0  # cap
        else:
            features.advance_decline_ratio = 1.0

    def _compute_volatility_features(
        self, features: RegimeFeatures, hist: list[dict]
    ) -> None:
        """Compute ATR-based volatility features."""
        atr_period = self.cfg["volatility"]["atr_period"]
        if len(hist) < atr_period + 1:
            return

        # True Range
        tr_list = []
        for i in range(1, len(hist)):
            h = hist[i]["high"] or hist[i]["close"]
            l = hist[i]["low"] or hist[i]["close"]
            prev_c = hist[i - 1]["close"]
            tr = max(h - l, abs(h - prev_c), abs(l - prev_c))
            tr_list.append(tr)

        if len(tr_list) < atr_period:
            return

        # Current ATR
        atr = float(np.mean(tr_list[-atr_period:]))
        features.vnindex_atr = atr
        features.vnindex_atr_pct = atr / (features.vnindex_close + 1e-9)

        # Percentile within lookback
        lookback = min(self.cfg["volatility"]["lookback"], len(tr_list) - atr_period + 1)
        atr_history = []
        for i in range(lookback):
            idx = len(tr_list) - atr_period - i
            if idx < 0:
                break
            window = tr_list[idx : idx + atr_period]
            close_at = hist[idx + atr_period]["close"]
            atr_pct_val = np.mean(window) / (close_at + 1e-9)
            atr_history.append(atr_pct_val)

        if atr_history:
            sorted_hist = sorted(atr_history)
            rank = sum(1 for v in sorted_hist if v <= features.vnindex_atr_pct)
            features.atr_pct_percentile = 100.0 * rank / len(sorted_hist)

    def _compute_liquidity_features(
        self,
        features: RegimeFeatures,
        hist: list[dict],
        stocks_data: dict[str, list[dict]],
    ) -> None:
        """Compute market liquidity features."""
        vol_ma_period = self.cfg["liquidity"]["volume_ma_period"]

        # Use total market volume from all stocks (sum volumes on last day vs MA20)
        # Simpler approach: use VNINDEX volume as proxy
        volumes = [d["volume"] for d in hist if d["volume"] and d["volume"] > 0]
        if len(volumes) >= vol_ma_period + 1:
            current_vol = volumes[-1]
            ma_vol = float(np.mean(volumes[-(vol_ma_period + 1) : -1]))
            if ma_vol > 0:
                features.market_volume_ratio = current_vol / ma_vol
