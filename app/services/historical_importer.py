from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Optional
from zoneinfo import ZoneInfo


@dataclass
class ImportResult:
    status: str
    inserted_or_updated: int
    scanned_lines: int
    db_min_ts: Optional[str]
    db_max_ts: Optional[str]
    file_path: str


class HistoricalBarImporter:
    def __init__(self, db_path: str):
        self.db_path = Path(db_path)
        if not self.db_path.is_absolute():
            backend_root = Path(__file__).resolve().parents[2]
            self.db_path = backend_root / self.db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_schema()

    def _connect(self):
        return sqlite3.connect(self.db_path)

    def _ensure_schema(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS historical_import_state (
                    key TEXT PRIMARY KEY,
                    symbol TEXT NOT NULL,
                    interval TEXT NOT NULL,
                    file_path TEXT NOT NULL,
                    file_size INTEGER NOT NULL,
                    file_mtime REAL NOT NULL,
                    scanned_lines INTEGER NOT NULL DEFAULT 0,
                    imported_rows INTEGER NOT NULL DEFAULT 0,
                    db_min_ts TEXT,
                    db_max_ts TEXT,
                    updated_at TEXT NOT NULL
                )
                """
            )

    def _state_key(self, symbol: str, interval: str, file_path: Path) -> str:
        return f"{symbol}|{interval}|{str(file_path.resolve()).lower()}"

    def _get_db_range(self, conn: sqlite3.Connection, symbol: str, interval: str):
        row = conn.execute(
            """
            SELECT MIN(timestamp), MAX(timestamp)
            FROM bars
            WHERE symbol=? AND interval=? AND source='historical_file'
            """,
            (symbol, interval),
        ).fetchone()
        return (row[0], row[1]) if row else (None, None)

    def _load_state(self, conn: sqlite3.Connection, key: str):
        return conn.execute(
            """
            SELECT file_size, file_mtime, scanned_lines, imported_rows, db_min_ts, db_max_ts
            FROM historical_import_state
            WHERE key=?
            """,
            (key,),
        ).fetchone()

    def _upsert_state(
        self,
        conn: sqlite3.Connection,
        *,
        key: str,
        symbol: str,
        interval: str,
        file_path: str,
        file_size: int,
        file_mtime: float,
        scanned_lines: int,
        imported_rows: int,
        db_min_ts: Optional[str],
        db_max_ts: Optional[str],
    ) -> None:
        conn.execute(
            """
            INSERT INTO historical_import_state (
                key, symbol, interval, file_path, file_size, file_mtime,
                scanned_lines, imported_rows, db_min_ts, db_max_ts, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET
                file_size=excluded.file_size,
                file_mtime=excluded.file_mtime,
                scanned_lines=excluded.scanned_lines,
                imported_rows=excluded.imported_rows,
                db_min_ts=excluded.db_min_ts,
                db_max_ts=excluded.db_max_ts,
                updated_at=excluded.updated_at
            """,
            (
                key,
                symbol,
                interval,
                file_path,
                file_size,
                file_mtime,
                int(scanned_lines),
                int(imported_rows),
                db_min_ts,
                db_max_ts,
                datetime.now(timezone.utc).isoformat(),
            ),
        )

    @staticmethod
    def _to_utc_iso(raw_ts: str, input_tz: str) -> str:
        local_dt = datetime.strptime(raw_ts, "%Y-%m-%d %H:%M:%S").replace(tzinfo=ZoneInfo(input_tz))
        return local_dt.astimezone(timezone.utc).isoformat()

    def ensure_seeded(
        self,
        *,
        file_path: str,
        symbol: str = "QQQ",
        interval: str = "1m",
        input_timezone: str = "America/New_York",
        batch_size: int = 3000,
    ) -> ImportResult:
        source_path = Path(file_path)
        if not source_path.is_absolute():
            backend_root = Path(__file__).resolve().parents[2]
            source_path = backend_root / source_path

        if not source_path.exists():
            return ImportResult(
                status="file_not_found",
                inserted_or_updated=0,
                scanned_lines=0,
                db_min_ts=None,
                db_max_ts=None,
                file_path=str(source_path),
            )

        source_path = source_path.resolve()
        stat = source_path.stat()
        key = self._state_key(symbol, interval, source_path)

        with self._connect() as conn:
            state = self._load_state(conn, key)
            db_min, db_max = self._get_db_range(conn, symbol, interval)

            # Fast skip: file is unchanged and DB already has historical coverage.
            if (
                state
                and int(state[0]) == int(stat.st_size)
                and float(state[1]) == float(stat.st_mtime)
                and db_min is not None
                and db_max is not None
            ):
                return ImportResult(
                    status="up_to_date",
                    inserted_or_updated=0,
                    scanned_lines=int(state[2] or 0),
                    db_min_ts=db_min,
                    db_max_ts=db_max,
                    file_path=str(source_path),
                )

            rows = []
            scanned = 0
            imported = 0

            def flush_batch():
                nonlocal imported
                if not rows:
                    return
                conn.executemany(
                    """
                    INSERT INTO bars (symbol, interval, open, high, low, close, volume, timestamp, source)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'historical_file')
                    ON CONFLICT(symbol, interval, timestamp)
                    DO UPDATE SET
                        open=excluded.open,
                        high=excluded.high,
                        low=excluded.low,
                        close=excluded.close,
                        volume=excluded.volume,
                        source=excluded.source
                    """,
                    rows,
                )
                imported += len(rows)
                rows.clear()

            with source_path.open("r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    scanned += 1
                    parts = line.split(",")
                    if len(parts) < 6:
                        continue
                    ts_raw, o, h, l, c, v = parts[:6]
                    try:
                        ts_utc = self._to_utc_iso(ts_raw.strip(), input_timezone)
                        o_f = float(o)
                        h_f = float(h)
                        l_f = float(l)
                        c_f = float(c)
                        v_f = float(v)
                    except Exception:
                        continue

                    # If DB already has historical rows, only fill edges to avoid full re-import each start.
                    if db_min is not None and db_max is not None and (db_min <= ts_utc <= db_max):
                        continue

                    rows.append((symbol, interval, o_f, h_f, l_f, c_f, v_f, ts_utc))
                    if len(rows) >= batch_size:
                        flush_batch()

            flush_batch()
            conn.commit()
            db_min, db_max = self._get_db_range(conn, symbol, interval)
            self._upsert_state(
                conn,
                key=key,
                symbol=symbol,
                interval=interval,
                file_path=str(source_path),
                file_size=int(stat.st_size),
                file_mtime=float(stat.st_mtime),
                scanned_lines=scanned,
                imported_rows=imported,
                db_min_ts=db_min,
                db_max_ts=db_max,
            )
            conn.commit()

            return ImportResult(
                status="seeded" if imported > 0 else "no_gap_found",
                inserted_or_updated=imported,
                scanned_lines=scanned,
                db_min_ts=db_min,
                db_max_ts=db_max,
                file_path=str(source_path),
            )

