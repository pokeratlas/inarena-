from __future__ import annotations

# Ordered PostgreSQL upgrades for already-initialized databases.
# Fresh databases are created from postgres_schema.py at the current baseline.

POSTGRES_MIGRATIONS: dict[int, list[str]] = {
    14: [
        """
        CREATE TABLE IF NOT EXISTS mutation_receipts (
            user_id TEXT NOT NULL,
            operation TEXT NOT NULL,
            idempotency_key TEXT NOT NULL,
            request_fingerprint TEXT NOT NULL,
            response_json TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT (CURRENT_TIMESTAMP::text),
            PRIMARY KEY (user_id, operation, idempotency_key)
        )
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_mutation_receipts_created_at
        ON mutation_receipts(created_at)
        """,
    ],
}


def migration_versions() -> list[int]:
    return sorted(POSTGRES_MIGRATIONS)
