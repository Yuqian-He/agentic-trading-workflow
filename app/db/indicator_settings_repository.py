import json
import sqlite3
from pathlib import Path
from typing import Any, Dict


class SQLiteIndicatorSettingsRepository:
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
                CREATE TABLE IF NOT EXISTS indicator_settings (
                    key TEXT PRIMARY KEY,
                    value_json TEXT NOT NULL,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
                """
            )

    def save(self, key: str, value: Dict[str, Any]) -> None:
        payload = json.dumps(value or {})
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO indicator_settings (key, value_json, updated_at)
                VALUES (?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(key) DO UPDATE SET
                    value_json=excluded.value_json,
                    updated_at=CURRENT_TIMESTAMP
                """,
                (key, payload),
            )

    def load(self, key: str) -> Dict[str, Any]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT value_json FROM indicator_settings WHERE key=?",
                (key,),
            ).fetchone()
        if not row:
            return {}
        try:
            return json.loads(row[0] or "{}")
        except Exception:
            return {}
