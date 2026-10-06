from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .postgres_migrations import POSTGRES_MIGRATIONS
from .postgres_schema import POSTGRES_SCHEMA_STATEMENTS, POSTGRES_SCHEMA_VERSION


@dataclass(frozen=True)
class MigrationStatus:
    current: int
    target: int
    pending: tuple[int, ...]

    @property
    def up_to_date(self) -> bool:
        return not self.pending


def _ensure_meta_table(conn: Any) -> None:
    conn.execute_raw(
        """
        CREATE TABLE IF NOT EXISTS inarena_schema_meta (
            version INTEGER NOT NULL
        )
        """
    )


def postgres_migration_status(conn: Any) -> MigrationStatus:
    _ensure_meta_table(conn)
    row = conn.execute_raw(
        "SELECT version FROM inarena_schema_meta LIMIT 1"
    ).fetchone()

    if row is None:
        return MigrationStatus(
            current=0,
            target=POSTGRES_SCHEMA_VERSION,
            pending=tuple(range(1, POSTGRES_SCHEMA_VERSION + 1)),
        )

    current = int(row["version"])
    if current > POSTGRES_SCHEMA_VERSION:
        raise RuntimeError(
            "PostgreSQL schema version "
            f"{current} is newer than supported {POSTGRES_SCHEMA_VERSION}"
        )

    return MigrationStatus(
        current=current,
        target=POSTGRES_SCHEMA_VERSION,
        pending=tuple(range(current + 1, POSTGRES_SCHEMA_VERSION + 1)),
    )


def migrate_postgres(conn: Any) -> MigrationStatus:
    status = postgres_migration_status(conn)

    if status.current == 0:
        for statement in POSTGRES_SCHEMA_STATEMENTS:
            conn.execute_raw(statement)
        conn.execute_raw(
            "INSERT INTO inarena_schema_meta(version) VALUES (%s)",
            (POSTGRES_SCHEMA_VERSION,),
        )
        return MigrationStatus(
            current=POSTGRES_SCHEMA_VERSION,
            target=POSTGRES_SCHEMA_VERSION,
            pending=(),
        )

    current = status.current
    for version in status.pending:
        statements = POSTGRES_MIGRATIONS.get(version)
        if statements is None:
            raise RuntimeError(
                f"missing PostgreSQL migration for schema version {version}"
            )
        for statement in statements:
            conn.execute_raw(statement)
        conn.execute_raw(
            "UPDATE inarena_schema_meta SET version = %s",
            (version,),
        )
        current = version

    return MigrationStatus(
        current=current,
        target=POSTGRES_SCHEMA_VERSION,
        pending=(),
    )
