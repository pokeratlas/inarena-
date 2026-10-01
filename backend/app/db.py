from __future__ import annotations

import json
import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator


def _database_path() -> str:
    return os.getenv("INARENA_DB_PATH", str(Path("data") / "inarena.sqlite3"))


def connect() -> sqlite3.Connection:
    path = _database_path()
    if path != ":memory:":
        Path(path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


@contextmanager
def transaction() -> Iterator[sqlite3.Connection]:
    conn = connect()
    try:
        conn.execute("BEGIN IMMEDIATE")
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def ensure_schema() -> None:
    with transaction() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS runtime_tables (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'open',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS runtime_seats (
                table_id TEXT NOT NULL REFERENCES runtime_tables(id) ON DELETE CASCADE,
                seat_no INTEGER NOT NULL,
                player_id TEXT NOT NULL,
                stack INTEGER NOT NULL CHECK(stack >= 0),
                status TEXT NOT NULL DEFAULT 'seated',
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (table_id, seat_no),
                UNIQUE (table_id, player_id)
            );

            CREATE TABLE IF NOT EXISTS active_hands (
                table_id TEXT PRIMARY KEY REFERENCES runtime_tables(id) ON DELETE CASCADE,
                hand_id TEXT NOT NULL UNIQUE,
                street TEXT NOT NULL,
                pot INTEGER NOT NULL DEFAULT 0,
                button_seat INTEGER,
                action_seat INTEGER,
                state_json TEXT NOT NULL,
                started_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS hand_results (
                hand_id TEXT PRIMARY KEY,
                table_id TEXT NOT NULL REFERENCES runtime_tables(id) ON DELETE CASCADE,
                pot INTEGER NOT NULL CHECK(pot >= 0),
                payouts_json TEXT NOT NULL,
                stacks_json TEXT NOT NULL,
                completed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS auth_sessions (
                session_id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                provider TEXT NOT NULL,
                data_json TEXT NOT NULL DEFAULT '{}',
                expires_at TEXT,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            """
        )


def decode_json(value: str) -> dict:
    data = json.loads(value)
    return data if isinstance(data, dict) else {}
