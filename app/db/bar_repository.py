import sqlite3
from pathlib import Path
from typing import Any, Dict, List


class SQLiteBarRepository:
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
                CREATE TABLE IF NOT EXISTS bars (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT,
                    interval TEXT,
                    open REAL,
                    high REAL,
                    low REAL,
                    close REAL,
                    volume REAL,
                    timestamp TEXT NOT NULL,
                    source TEXT
                )
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_bars_symbol_interval_timestamp ON bars(symbol, interval, timestamp)")

    def save_bar(self, bar: Dict[str, Any], interval: str) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO bars (symbol, interval, open, high, low, close, volume, timestamp, source)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    bar.get("symbol"),
                    interval,
                    bar.get("open"),
                    bar.get("high"),
                    bar.get("low"),
                    bar.get("close"),
                    bar.get("volume"),
                    bar.get("timestamp"),
                    bar.get("source"),
                ),
            )

    def fetch_recent_bars(self, symbol: str, interval: str, limit: int) -> List[Dict[str, Any]]:
        safe_limit = max(1, int(limit))
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT symbol, open, high, low, close, volume, timestamp, source
                FROM bars
                WHERE symbol = ? AND interval = ?
                ORDER BY timestamp DESC
                LIMIT ?
                """,
                (symbol, interval, safe_limit),
            ).fetchall()
        rows = list(reversed(rows))
        result: List[Dict[str, Any]] = []
        for row in rows:
            result.append(
                {
                    "symbol": row[0],
                    "open": row[1],
                    "high": row[2],
                    "low": row[3],
                    "close": row[4],
                    "volume": row[5],
                    "timestamp": row[6],
                    "source": row[7],
                }
            )
        return result

