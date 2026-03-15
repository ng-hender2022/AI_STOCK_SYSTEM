"""
AI_STOCK Database Manager
Quản lý connections tới 4 SQLite databases.
Thread-safe, context manager support, WAL mode.
"""

import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Optional

from .config import MARKET_DB, SIGNALS_DB, MODELS_DB, AUDIT_DB


class DatabaseManager:
    """
    Central database manager cho AI_STOCK.

    Usage:
        db = DatabaseManager()

        # Context manager (auto-commit/rollback)
        with db.connect("market") as conn:
            conn.execute("SELECT * FROM symbols_master")

        # Quick query
        rows = db.query("market", "SELECT * FROM prices_daily WHERE symbol=?", ("VNM",))

        # Quick insert
        db.execute("signals", "INSERT INTO expert_signals ...", params)
    """

    DB_MAP = {
        "market": MARKET_DB,
        "signals": SIGNALS_DB,
        "models": MODELS_DB,
        "audit": AUDIT_DB,
    }

    def __init__(self):
        self._local = threading.local()

    def _get_path(self, db_name: str) -> Path:
        """Resolve db_name → file path."""
        if db_name not in self.DB_MAP:
            raise ValueError(
                f"Unknown database '{db_name}'. Valid: {list(self.DB_MAP.keys())}"
            )
        return self.DB_MAP[db_name]

    def _create_connection(self, db_path: Path) -> sqlite3.Connection:
        """Tạo connection mới với settings chuẩn."""
        conn = sqlite3.connect(str(db_path), timeout=30)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA busy_timeout=5000")
        conn.row_factory = sqlite3.Row
        return conn

    @contextmanager
    def connect(self, db_name: str):
        """
        Context manager trả về connection.
        Auto-commit nếu không có exception, auto-rollback nếu có.

        Usage:
            with db.connect("market") as conn:
                conn.execute(...)
        """
        db_path = self._get_path(db_name)
        conn = self._create_connection(db_path)
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def query(
        self,
        db_name: str,
        sql: str,
        params: tuple = (),
        as_dict: bool = False,
    ) -> list:
        """
        Execute SELECT query, return list of rows.

        Args:
            db_name: "market", "signals", "models", or "audit"
            sql: SQL query string
            params: Query parameters
            as_dict: If True, return list of dicts instead of sqlite3.Row
        """
        with self.connect(db_name) as conn:
            cursor = conn.execute(sql, params)
            rows = cursor.fetchall()
            if as_dict:
                return [dict(row) for row in rows]
            return rows

    def execute(
        self,
        db_name: str,
        sql: str,
        params: tuple = (),
    ) -> int:
        """
        Execute INSERT/UPDATE/DELETE, return rowcount.
        """
        with self.connect(db_name) as conn:
            cursor = conn.execute(sql, params)
            return cursor.rowcount

    def executemany(
        self,
        db_name: str,
        sql: str,
        params_list: list[tuple],
    ) -> int:
        """
        Execute batch INSERT/UPDATE/DELETE, return rowcount.
        """
        with self.connect(db_name) as conn:
            cursor = conn.executemany(sql, params_list)
            return cursor.rowcount

    def insert_or_replace(
        self,
        db_name: str,
        table: str,
        data: dict,
    ) -> int:
        """
        INSERT OR REPLACE single row from dict.

        Args:
            db_name: database name
            table: table name
            data: {column: value} dict
        """
        columns = ", ".join(data.keys())
        placeholders = ", ".join(["?"] * len(data))
        sql = f"INSERT OR REPLACE INTO {table} ({columns}) VALUES ({placeholders})"
        return self.execute(db_name, sql, tuple(data.values()))

    def insert_or_replace_many(
        self,
        db_name: str,
        table: str,
        data_list: list[dict],
    ) -> int:
        """
        INSERT OR REPLACE batch rows from list of dicts.
        All dicts must have the same keys.
        """
        if not data_list:
            return 0
        columns = ", ".join(data_list[0].keys())
        placeholders = ", ".join(["?"] * len(data_list[0]))
        sql = f"INSERT OR REPLACE INTO {table} ({columns}) VALUES ({placeholders})"
        params_list = [tuple(d.values()) for d in data_list]
        return self.executemany(db_name, sql, params_list)

    def table_exists(self, db_name: str, table: str) -> bool:
        """Check if table exists."""
        rows = self.query(
            db_name,
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
            (table,),
        )
        return len(rows) > 0

    def table_count(self, db_name: str, table: str) -> int:
        """Get row count of a table."""
        rows = self.query(db_name, f"SELECT COUNT(*) as cnt FROM [{table}]")
        return rows[0]["cnt"] if rows else 0

    def get_tables(self, db_name: str) -> list[str]:
        """List all tables in a database."""
        rows = self.query(
            db_name,
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name",
        )
        return [row["name"] for row in rows]
