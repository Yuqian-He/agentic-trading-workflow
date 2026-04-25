import sqlite3
from pathlib import Path
from typing import Any, Dict


class SQLiteTickRepository:
    def __init__(self, db_path: str):
        self.db_path = Path(db_path)
        if not self.db_path.is_absolute():
            backend_root = Path(__file__).resolve().parents[2]
            self.db_path = backend_root / self.db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _connect(self):
        return sqlite3.connect(self.db_path)

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS ticks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT,
                    price REAL,
                    bid REAL,
                    ask REAL,
                    volume REAL,
                    timestamp TEXT NOT NULL,
                    source TEXT
                )
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_ticks_symbol_timestamp ON ticks(symbol, timestamp)")

    def save_tick(self, tick: Dict[str, Any]) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO ticks (symbol, price, bid, ask, volume, timestamp, source)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    tick.get("symbol"),
                    tick.get("price"),
                    tick.get("bid"),
                    tick.get("ask"),
                    tick.get("volume"),
                    tick.get("timestamp"),
                    tick.get("source"),
                ),
            )
