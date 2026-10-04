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
    15: [
        """
        CREATE TABLE IF NOT EXISTS operator_sessions (
            token_hash TEXT PRIMARY KEY,
            scopes_json TEXT NOT NULL,
            expires_at_epoch BIGINT NOT NULL,
            revoked_at TEXT,
            created_at TEXT NOT NULL DEFAULT (CURRENT_TIMESTAMP::text),
            updated_at TEXT NOT NULL DEFAULT (CURRENT_TIMESTAMP::text)
        )
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_operator_sessions_expiry
        ON operator_sessions(expires_at_epoch)
        """,
    ],
    16: [
        """
        CREATE TABLE IF NOT EXISTS cash_pending_topups (
            table_id TEXT NOT NULL REFERENCES runtime_tables(id) ON DELETE CASCADE,
            player_id TEXT NOT NULL,
            amount INTEGER NOT NULL CHECK(amount > 0),
            created_at TEXT NOT NULL DEFAULT (CURRENT_TIMESTAMP::text),
            updated_at TEXT NOT NULL DEFAULT (CURRENT_TIMESTAMP::text),
            PRIMARY KEY (table_id, player_id)
        )
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_cash_pending_topups_table
        ON cash_pending_topups(table_id)
        """,
    ],
}


def migration_versions() -> list[int]:
    return sorted(POSTGRES_MIGRATIONS)
