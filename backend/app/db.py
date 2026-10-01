from __future__ import annotations

import json
import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

from .postgres_schema import POSTGRES_SCHEMA_STATEMENTS, POSTGRES_SCHEMA_VERSION


SCHEMA_VERSION = 13


def _database_path() -> str:
    return os.getenv("INARENA_DB_PATH", str(Path("data") / "inarena.sqlite3"))


def _database_url() -> str | None:
    value = os.getenv("INARENA_DATABASE_URL")
    return value.strip() if value and value.strip() else None


def database_backend() -> str:
    url = _database_url()
    if url and url.startswith(("postgresql://", "postgres://")):
        return "postgresql"
    return "sqlite"


def _translate_postgres_sql(sql: str) -> str:
    translated = sql.replace("?", "%s")
    translated = translated.replace(
        "CURRENT_TIMESTAMP",
        "(CURRENT_TIMESTAMP::text)",
    )
    return translated


class PostgresConnection:
    def __init__(self, raw: Any):
        self.raw = raw

    def execute(self, sql: str, params: tuple | list = ()):
        return self.raw.execute(_translate_postgres_sql(sql), params)

    def execute_raw(self, sql: str, params: tuple | list = ()):
        return self.raw.execute(sql, params)

    def commit(self) -> None:
        self.raw.commit()

    def rollback(self) -> None:
        self.raw.rollback()

    def close(self) -> None:
        self.raw.close()


def _connect_postgres() -> PostgresConnection:
    try:
        import psycopg
        from psycopg.rows import dict_row
    except ImportError as exc:
        raise RuntimeError(
            "PostgreSQL backend requires the 'postgres' project extra"
        ) from exc

    url = _database_url()
    if not url:
        raise RuntimeError("INARENA_DATABASE_URL is required for PostgreSQL")
    raw = psycopg.connect(url, row_factory=dict_row)
    return PostgresConnection(raw)


def _connect_sqlite() -> sqlite3.Connection:
    path = _database_path()
    if path != ":memory:":
        Path(path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


def connect():
    if database_backend() == "postgresql":
        return _connect_postgres()
    return _connect_sqlite()


@contextmanager
def transaction() -> Iterator[Any]:
    conn = connect()
    try:
        if database_backend() == "sqlite":
            conn.execute("BEGIN IMMEDIATE")
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _migration_1(conn: sqlite3.Connection) -> None:
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


def _migration_2(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS realtime_events (
            seq INTEGER PRIMARY KEY AUTOINCREMENT,
            table_id TEXT NOT NULL REFERENCES runtime_tables(id) ON DELETE CASCADE,
            event_type TEXT NOT NULL,
            payload_json TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE INDEX IF NOT EXISTS idx_realtime_events_table_seq
        ON realtime_events(table_id, seq);
        """
    )


def _migration_3(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS recovery_actions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            table_id TEXT NOT NULL REFERENCES runtime_tables(id) ON DELETE CASCADE,
            hand_id TEXT,
            action TEXT NOT NULL,
            reason TEXT NOT NULL,
            details_json TEXT NOT NULL DEFAULT '{}',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE INDEX IF NOT EXISTS idx_recovery_actions_table_id
        ON recovery_actions(table_id, id);
        """
    )


def _migration_4(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS hand_actions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            hand_id TEXT NOT NULL,
            table_id TEXT NOT NULL REFERENCES runtime_tables(id) ON DELETE CASCADE,
            action_no INTEGER NOT NULL,
            player_id TEXT NOT NULL,
            seat_no INTEGER NOT NULL,
            action TEXT NOT NULL,
            amount INTEGER,
            state_json TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(hand_id, action_no)
        );

        CREATE INDEX IF NOT EXISTS idx_hand_actions_table_hand
        ON hand_actions(table_id, hand_id, action_no);
        """
    )


def _migration_5(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS hand_secrets (
            hand_id TEXT PRIMARY KEY,
            table_id TEXT NOT NULL REFERENCES runtime_tables(id) ON DELETE CASCADE,
            deck_json TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS hand_private_cards (
            hand_id TEXT NOT NULL,
            table_id TEXT NOT NULL REFERENCES runtime_tables(id) ON DELETE CASCADE,
            player_id TEXT NOT NULL,
            cards_json TEXT NOT NULL,
            PRIMARY KEY (hand_id, player_id)
        );

        CREATE INDEX IF NOT EXISTS idx_hand_private_cards_table_player
        ON hand_private_cards(table_id, player_id);
        """
    )


def _migration_6(conn: sqlite3.Connection) -> None:
    existing = {
        row["name"]
        for row in conn.execute("PRAGMA table_info(runtime_tables)").fetchall()
    }
    if "small_blind" not in existing:
        conn.execute(
            "ALTER TABLE runtime_tables ADD COLUMN small_blind INTEGER NOT NULL DEFAULT 50"
        )
    if "big_blind" not in existing:
        conn.execute(
            "ALTER TABLE runtime_tables ADD COLUMN big_blind INTEGER NOT NULL DEFAULT 100"
        )
    if "last_button_seat" not in existing:
        conn.execute(
            "ALTER TABLE runtime_tables ADD COLUMN last_button_seat INTEGER"
        )


def _migration_7(conn: sqlite3.Connection) -> None:
    existing = {
        row["name"]
        for row in conn.execute("PRAGMA table_info(runtime_tables)").fetchall()
    }
    if "table_mode" not in existing:
        conn.execute(
            "ALTER TABLE runtime_tables ADD COLUMN table_mode TEXT NOT NULL DEFAULT 'cash'"
        )
    if "starting_stack" not in existing:
        conn.execute(
            "ALTER TABLE runtime_tables ADD COLUMN starting_stack INTEGER NOT NULL DEFAULT 10000"
        )
    if "blind_schedule_json" not in existing:
        conn.execute(
            "ALTER TABLE runtime_tables ADD COLUMN blind_schedule_json TEXT NOT NULL DEFAULT '[]'"
        )
    if "blind_level_index" not in existing:
        conn.execute(
            "ALTER TABLE runtime_tables ADD COLUMN blind_level_index INTEGER NOT NULL DEFAULT 0"
        )
    if "blind_level_started_at" not in existing:
        conn.execute(
            "ALTER TABLE runtime_tables ADD COLUMN blind_level_started_at INTEGER"
        )


def _migration_8(conn: sqlite3.Connection) -> None:
    table_cols = {
        row["name"]
        for row in conn.execute("PRAGMA table_info(runtime_tables)").fetchall()
    }
    additions = {
        "cash_buyin_min": "INTEGER NOT NULL DEFAULT 1000",
        "cash_buyin_max": "INTEGER NOT NULL DEFAULT 100000",
        "rebuy_enabled": "INTEGER NOT NULL DEFAULT 0",
        "rebuy_stack": "INTEGER NOT NULL DEFAULT 0",
        "rebuy_max_per_player": "INTEGER NOT NULL DEFAULT 0",
        "addon_enabled": "INTEGER NOT NULL DEFAULT 0",
        "addon_stack": "INTEGER NOT NULL DEFAULT 0",
        "blind_schedule_status": "TEXT NOT NULL DEFAULT 'running'",
        "blind_schedule_paused_at": "INTEGER",
    }
    for name, ddl in additions.items():
        if name not in table_cols:
            conn.execute(
                f"ALTER TABLE runtime_tables ADD COLUMN {name} {ddl}"
            )

    seat_cols = {
        row["name"]
        for row in conn.execute("PRAGMA table_info(runtime_seats)").fetchall()
    }
    if "rebuy_count" not in seat_cols:
        conn.execute(
            "ALTER TABLE runtime_seats ADD COLUMN rebuy_count INTEGER NOT NULL DEFAULT 0"
        )
    if "eliminated_at" not in seat_cols:
        conn.execute(
            "ALTER TABLE runtime_seats ADD COLUMN eliminated_at TEXT"
        )

    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS table_ledger (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            table_id TEXT NOT NULL REFERENCES runtime_tables(id) ON DELETE CASCADE,
            player_id TEXT NOT NULL,
            entry_type TEXT NOT NULL,
            amount INTEGER NOT NULL,
            details_json TEXT NOT NULL DEFAULT '{}',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE INDEX IF NOT EXISTS idx_table_ledger_table_player
        ON table_ledger(table_id, player_id, id);
        """
    )


def _migration_9(conn: sqlite3.Connection) -> None:
    table_cols = {
        row["name"]
        for row in conn.execute("PRAGMA table_info(runtime_tables)").fetchall()
    }
    additions = {
        "rebuy_window_open": "INTEGER NOT NULL DEFAULT 1",
        "addon_window_open": "INTEGER NOT NULL DEFAULT 1",
        "winner_player_id": "TEXT",
        "finished_at": "TEXT",
    }
    for name, ddl in additions.items():
        if name not in table_cols:
            conn.execute(
                f"ALTER TABLE runtime_tables ADD COLUMN {name} {ddl}"
            )

    seat_cols = {
        row["name"]
        for row in conn.execute("PRAGMA table_info(runtime_seats)").fetchall()
    }
    if "addon_used" not in seat_cols:
        conn.execute(
            "ALTER TABLE runtime_seats ADD COLUMN addon_used INTEGER NOT NULL DEFAULT 0"
        )
    if "finish_place" not in seat_cols:
        conn.execute(
            "ALTER TABLE runtime_seats ADD COLUMN finish_place INTEGER"
        )

    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS player_balances (
            user_id TEXT PRIMARY KEY,
            balance INTEGER NOT NULL DEFAULT 0 CHECK(balance >= 0),
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS operator_audit (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            table_id TEXT REFERENCES runtime_tables(id) ON DELETE CASCADE,
            action TEXT NOT NULL,
            details_json TEXT NOT NULL DEFAULT '{}',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE INDEX IF NOT EXISTS idx_operator_audit_table_id
        ON operator_audit(table_id, id);
        """
    )


def _migration_10(conn: sqlite3.Connection) -> None:
    table_cols = {
        row["name"]
        for row in conn.execute("PRAGMA table_info(runtime_tables)").fetchall()
    }
    additions = {
        "tournament_status": "TEXT NOT NULL DEFAULT 'scheduled'",
        "scheduled_start_at": "INTEGER",
        "registration_open_at": "INTEGER",
        "registration_close_at": "INTEGER",
        "late_registration_close_at": "INTEGER",
    }
    for name, ddl in additions.items():
        if name not in table_cols:
            conn.execute(
                f"ALTER TABLE runtime_tables ADD COLUMN {name} {ddl}"
            )

    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS tournament_registrations (
            table_id TEXT NOT NULL REFERENCES runtime_tables(id) ON DELETE CASCADE,
            user_id TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'registered',
            registered_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            withdrawn_at TEXT,
            PRIMARY KEY (table_id, user_id)
        );

        CREATE INDEX IF NOT EXISTS idx_tournament_registrations_table_status
        ON tournament_registrations(table_id, status);
        """
    )


def _migration_11(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS cash_waitlist (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            table_id TEXT NOT NULL REFERENCES runtime_tables(id) ON DELETE CASCADE,
            user_id TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'waiting',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(table_id, user_id)
        );

        CREATE INDEX IF NOT EXISTS idx_cash_waitlist_table_status_id
        ON cash_waitlist(table_id, status, id);

        CREATE TABLE IF NOT EXISTS seat_reservations (
            id TEXT PRIMARY KEY,
            table_id TEXT NOT NULL REFERENCES runtime_tables(id) ON DELETE CASCADE,
            seat_no INTEGER NOT NULL,
            user_id TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'active',
            expires_at_epoch INTEGER NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE UNIQUE INDEX IF NOT EXISTS idx_active_reservation_seat
        ON seat_reservations(table_id, seat_no)
        WHERE status = 'active';

        CREATE UNIQUE INDEX IF NOT EXISTS idx_active_reservation_user
        ON seat_reservations(table_id, user_id)
        WHERE status = 'active';

        CREATE TABLE IF NOT EXISTS idempotency_records (
            user_id TEXT NOT NULL,
            operation TEXT NOT NULL,
            idempotency_key TEXT NOT NULL,
            request_fingerprint TEXT NOT NULL,
            response_json TEXT NOT NULL,
            status_code INTEGER NOT NULL DEFAULT 200,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (user_id, operation, idempotency_key)
        );

        CREATE INDEX IF NOT EXISTS idx_idempotency_records_created_at
        ON idempotency_records(created_at);
        """
    )


def _migration_12(conn: sqlite3.Connection) -> None:
    cols = {
        row["name"]
        for row in conn.execute("PRAGMA table_info(idempotency_records)").fetchall()
    }
    if "command_status" not in cols:
        conn.execute(
            """
            ALTER TABLE idempotency_records
            ADD COLUMN command_status TEXT NOT NULL DEFAULT 'completed'
            """
        )
    if "updated_at" not in cols:
        conn.execute(
            """
            ALTER TABLE idempotency_records
            ADD COLUMN updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            """
        )


def _migration_13(conn: sqlite3.Connection) -> None:
    event_cols = {
        row["name"]
        for row in conn.execute("PRAGMA table_info(realtime_events)").fetchall()
    }
    if "outbox_id" not in event_cols:
        conn.execute(
            "ALTER TABLE realtime_events ADD COLUMN outbox_id INTEGER"
        )
    conn.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS idx_realtime_events_outbox_id
        ON realtime_events(outbox_id)
        WHERE outbox_id IS NOT NULL
        """
    )

    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS realtime_outbox (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            table_id TEXT NOT NULL REFERENCES runtime_tables(id) ON DELETE CASCADE,
            event_type TEXT NOT NULL,
            payload_json TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            dispatched_at TEXT
        );

        CREATE INDEX IF NOT EXISTS idx_realtime_outbox_pending
        ON realtime_outbox(table_id, dispatched_at, id);
        """
    )


MIGRATIONS = {
    1: _migration_1,
    2: _migration_2,
    3: _migration_3,
    4: _migration_4,
    5: _migration_5,
    6: _migration_6,
    7: _migration_7,
    8: _migration_8,
    9: _migration_9,
    10: _migration_10,
    11: _migration_11,
    12: _migration_12,
    13: _migration_13,
}


def _ensure_postgres_schema() -> None:
    conn = _connect_postgres()
    try:
        for statement in POSTGRES_SCHEMA_STATEMENTS:
            conn.execute_raw(statement)

        row = conn.execute_raw(
            "SELECT version FROM inarena_schema_meta LIMIT 1"
        ).fetchone()
        if row is None:
            conn.execute_raw(
                "INSERT INTO inarena_schema_meta(version) VALUES (%s)",
                (POSTGRES_SCHEMA_VERSION,),
            )
        elif int(row["version"]) != POSTGRES_SCHEMA_VERSION:
            raise RuntimeError(
                "PostgreSQL schema version "
                f"{row['version']} does not match supported "
                f"{POSTGRES_SCHEMA_VERSION}"
            )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _ensure_sqlite_schema() -> None:
    with transaction() as conn:
        current = int(conn.execute("PRAGMA user_version").fetchone()[0])
        if current > SCHEMA_VERSION:
            raise RuntimeError(
                f"database schema {current} is newer than supported {SCHEMA_VERSION}"
            )

        for version in range(current + 1, SCHEMA_VERSION + 1):
            MIGRATIONS[version](conn)
            conn.execute(f"PRAGMA user_version = {version}")


def ensure_schema() -> None:
    if database_backend() == "postgresql":
        _ensure_postgres_schema()
        return
    _ensure_sqlite_schema()


def schema_version() -> int:
    if database_backend() == "postgresql":
        conn = _connect_postgres()
        try:
            row = conn.execute_raw(
                "SELECT version FROM inarena_schema_meta LIMIT 1"
            ).fetchone()
            return int(row["version"]) if row is not None else 0
        finally:
            conn.close()

    conn = connect()
    try:
        return int(conn.execute("PRAGMA user_version").fetchone()[0])
    finally:
        conn.close()


def decode_json(value: str) -> dict:
    data = json.loads(value)
    return data if isinstance(data, dict) else {}
