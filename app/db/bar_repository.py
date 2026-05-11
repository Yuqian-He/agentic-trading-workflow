import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


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
            # Clean historical duplicates before enforcing uniqueness.
            conn.execute(
                """
                DELETE FROM bars
                WHERE id NOT IN (
                    SELECT MAX(id)
                    FROM bars
                    GROUP BY symbol, interval, timestamp
                )
                """
            )
            conn.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS uq_bars_symbol_interval_timestamp ON bars(symbol, interval, timestamp)"
            )

    def save_bar(self, bar: Dict[str, Any], interval: str) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO bars (symbol, interval, open, high, low, close, volume, timestamp, source)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(symbol, interval, timestamp)
                DO UPDATE SET
                    open=excluded.open,
                    high=excluded.high,
                    low=excluded.low,
                    close=excluded.close,
                    volume=excluded.volume,
                    source=excluded.source
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

    def upsert_bars(self, bars: List[Dict[str, Any]], interval: str, batch_size: int = 1000) -> int:
        if not bars:
            return 0
        safe_batch = max(1, int(batch_size))
        rows = []
        for bar in bars:
            rows.append(
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
                )
            )
        inserted = 0
        with self._connect() as conn:
            for i in range(0, len(rows), safe_batch):
                chunk = rows[i : i + safe_batch]
                conn.executemany(
                    """
                    INSERT INTO bars (symbol, interval, open, high, low, close, volume, timestamp, source)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(symbol, interval, timestamp)
                    DO UPDATE SET
                        open=excluded.open,
                        high=excluded.high,
                        low=excluded.low,
                        close=excluded.close,
                        volume=excluded.volume,
                        source=excluded.source
                    """,
                    chunk,
                )
                inserted += len(chunk)
        return inserted

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

    def fetch_latest_timestamp(self, symbol: str, interval: str, source: Optional[str] = None) -> Optional[str]:
        with self._connect() as conn:
            if source:
                row = conn.execute(
                    """
                    SELECT MAX(timestamp)
                    FROM bars
                    WHERE symbol = ? AND interval = ? AND source = ?
                    """,
                    (symbol, interval, source),
                ).fetchone()
            else:
                row = conn.execute(
                    """
                    SELECT MAX(timestamp)
                    FROM bars
                    WHERE symbol = ? AND interval = ?
                    """,
                    (symbol, interval),
                ).fetchone()
        return row[0] if row and row[0] else None

    @staticmethod
    def _to_iso_utc(value: str) -> Optional[str]:
        try:
            dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc).isoformat()
        except Exception:
            return None

