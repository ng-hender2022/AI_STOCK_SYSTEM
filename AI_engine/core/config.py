"""
AI_STOCK Central Configuration
Tất cả paths, constants, và settings cho toàn hệ thống.
"""

from pathlib import Path

# ---------------------------------------------------------------------------
# ROOT PATHS
# ---------------------------------------------------------------------------

AI_ROOT = Path(r"D:\AI")
BRAIN_ROOT = AI_ROOT / "AI_brain"
DATA_ROOT = AI_ROOT / "AI_data"
ENGINE_ROOT = AI_ROOT / "AI_engine"

# ---------------------------------------------------------------------------
# DATABASE PATHS
# ---------------------------------------------------------------------------

MARKET_DB = DATA_ROOT / "market.db"
SIGNALS_DB = DATA_ROOT / "signals.db"
MODELS_DB = DATA_ROOT / "models.db"
AUDIT_DB = DATA_ROOT / "audit.db"

# ---------------------------------------------------------------------------
# UNIVERSE
# ---------------------------------------------------------------------------

UNIVERSE_SIZE = 92  # 91 stocks + VNINDEX
VNINDEX_SYMBOL = "VNINDEX"

# ---------------------------------------------------------------------------
# EXPERT IDs
# ---------------------------------------------------------------------------

EXPERT_IDS = [
    "V4I",      # Ichimoku
    "V4MA",     # Moving Average
    "V4ADX",    # Trend Strength (ADX)
    "V4MACD",   # MACD
    "V4RSI",    # RSI
    "V4STO",    # Stochastic
    "V4V",      # Volume Behavior
    "V4OBV",    # OBV
    "V4ATR",    # ATR
    "V4BB",     # Bollinger Bands
    "V4P",      # Price Action
    "V4CANDLE", # Candlestick
    "V4BR",     # Breadth
    "V4RS",     # Relative Strength
    "V4REG",    # Market Regime
    "V4S",      # Sector Strength
    "V4LIQ",    # Liquidity
]

EXPERT_GROUPS = {
    "TREND":       ["V4I", "V4MA", "V4ADX"],
    "MOMENTUM":    ["V4MACD", "V4RSI", "V4STO"],
    "VOLUME":      ["V4V", "V4OBV"],
    "VOLATILITY":  ["V4ATR", "V4BB"],
    "STRUCTURE":   ["V4P", "V4CANDLE"],
    "CONTEXT":     ["V4BR", "V4RS", "V4REG", "V4S", "V4LIQ"],
}

# ---------------------------------------------------------------------------
# R LAYER
# ---------------------------------------------------------------------------

R_MODEL_IDS = ["R1", "R2", "R3", "R4", "R5"]

R_SCORE_MIN = -4.0
R_SCORE_MAX = 4.0

R_ENSEMBLE_WEIGHTS = {
    "R1": 0.2,
    "R2": 0.2,
    "R3": 0.2,
    "R4": 0.2,
    "R5": 0.2,
}

ENSEMBLE_DIRECTION_THRESHOLD = 0.5  # |score| > threshold → bull/bear

# ---------------------------------------------------------------------------
# SIGNAL QUALITY
# ---------------------------------------------------------------------------

SIGNAL_QUALITY_MIN = 0
SIGNAL_QUALITY_MAX = 4

# ---------------------------------------------------------------------------
# DATA PIPELINE
# ---------------------------------------------------------------------------

SNAPSHOT_EOD = "EOD"
MARKET_CLOSE_HOUR = 15  # 15:00 VN time
TIMEZONE = "Asia/Ho_Chi_Minh"

API_RETRY_COUNT = 3
API_RETRY_INTERVAL = 30  # seconds

# ---------------------------------------------------------------------------
# LOGGING
# ---------------------------------------------------------------------------

LOG_DIR = AI_ROOT / "logs"
LOG_FORMAT = "[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s"
LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
LOG_LEVEL = "INFO"


class Config:
    """Accessor class cho toàn bộ config. Dùng khi cần pass config as object."""

    # Paths
    AI_ROOT = AI_ROOT
    BRAIN_ROOT = BRAIN_ROOT
    DATA_ROOT = DATA_ROOT
    ENGINE_ROOT = ENGINE_ROOT

    # DBs
    MARKET_DB = MARKET_DB
    SIGNALS_DB = SIGNALS_DB
    MODELS_DB = MODELS_DB
    AUDIT_DB = AUDIT_DB

    # Universe
    UNIVERSE_SIZE = UNIVERSE_SIZE
    VNINDEX_SYMBOL = VNINDEX_SYMBOL

    # Experts
    EXPERT_IDS = EXPERT_IDS
    EXPERT_GROUPS = EXPERT_GROUPS

    # R Layer
    R_MODEL_IDS = R_MODEL_IDS
    R_SCORE_MIN = R_SCORE_MIN
    R_SCORE_MAX = R_SCORE_MAX
    R_ENSEMBLE_WEIGHTS = R_ENSEMBLE_WEIGHTS
    ENSEMBLE_DIRECTION_THRESHOLD = ENSEMBLE_DIRECTION_THRESHOLD

    # Pipeline
    SNAPSHOT_EOD = SNAPSHOT_EOD
    TIMEZONE = TIMEZONE
    API_RETRY_COUNT = API_RETRY_COUNT
    API_RETRY_INTERVAL = API_RETRY_INTERVAL

    # Logging
    LOG_DIR = LOG_DIR
    LOG_FORMAT = LOG_FORMAT
    LOG_DATE_FORMAT = LOG_DATE_FORMAT
    LOG_LEVEL = LOG_LEVEL
