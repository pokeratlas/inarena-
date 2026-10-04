from __future__ import annotations

POSTGRES_SCHEMA_VERSION = 17

POSTGRES_SCHEMA_STATEMENTS = [
    """
    CREATE TABLE IF NOT EXISTS inarena_schema_meta (
        version INTEGER NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS runtime_tables (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'open',
        small_blind INTEGER NOT NULL DEFAULT 50,
        big_blind INTEGER NOT NULL DEFAULT 100,
        last_button_seat INTEGER,
        table_mode TEXT NOT NULL DEFAULT 'cash',
        starting_stack INTEGER NOT NULL DEFAULT 10000,
        blind_schedule_json TEXT NOT NULL DEFAULT '[]',
        blind_level_index INTEGER NOT NULL DEFAULT 0,
        blind_level_started_at BIGINT,
        cash_buyin_min INTEGER NOT NULL DEFAULT 1000,
        cash_buyin_max INTEGER NOT NULL DEFAULT 100000,
        rebuy_enabled INTEGER NOT NULL DEFAULT 0,
        rebuy_stack INTEGER NOT NULL DEFAULT 0,
        rebuy_max_per_player INTEGER NOT NULL DEFAULT 0,
        addon_enabled INTEGER NOT NULL DEFAULT 0,
        addon_stack INTEGER NOT NULL DEFAULT 0,
        blind_schedule_status TEXT NOT NULL DEFAULT 'running',
        blind_schedule_paused_at BIGINT,
        rebuy_window_open INTEGER NOT NULL DEFAULT 1,
        addon_window_open INTEGER NOT NULL DEFAULT 1,
        winner_player_id TEXT,
        finished_at TEXT,
        tournament_status TEXT NOT NULL DEFAULT 'scheduled',
        scheduled_start_at BIGINT,
        registration_open_at BIGINT,
        registration_close_at BIGINT,
        late_registration_close_at BIGINT,
        created_at TEXT NOT NULL DEFAULT (CURRENT_TIMESTAMP::text),
        updated_at TEXT NOT NULL DEFAULT (CURRENT_TIMESTAMP::text)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS runtime_seats (
        table_id TEXT NOT NULL REFERENCES runtime_tables(id) ON DELETE CASCADE,
        seat_no INTEGER NOT NULL,
        player_id TEXT NOT NULL,
        stack INTEGER NOT NULL CHECK(stack >= 0),
        status TEXT NOT NULL DEFAULT 'seated',
        rebuy_count INTEGER NOT NULL DEFAULT 0,
        eliminated_at TEXT,
        addon_used INTEGER NOT NULL DEFAULT 0,
        finish_place INTEGER,
        updated_at TEXT NOT NULL DEFAULT (CURRENT_TIMESTAMP::text),
        PRIMARY KEY (table_id, seat_no),
        UNIQUE (table_id, player_id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS active_hands (
        table_id TEXT PRIMARY KEY REFERENCES runtime_tables(id) ON DELETE CASCADE,
        hand_id TEXT NOT NULL UNIQUE,
        street TEXT NOT NULL,
        pot INTEGER NOT NULL DEFAULT 0,
        button_seat INTEGER,
        action_seat INTEGER,
        state_json TEXT NOT NULL,
        started_at TEXT NOT NULL DEFAULT (CURRENT_TIMESTAMP::text),
        updated_at TEXT NOT NULL DEFAULT (CURRENT_TIMESTAMP::text)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS hand_results (
        hand_id TEXT PRIMARY KEY,
        table_id TEXT NOT NULL REFERENCES runtime_tables(id) ON DELETE CASCADE,
        pot INTEGER NOT NULL CHECK(pot >= 0),
        payouts_json TEXT NOT NULL,
        stacks_json TEXT NOT NULL,
        completed_at TEXT NOT NULL DEFAULT (CURRENT_TIMESTAMP::text)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS auth_sessions (
        session_id TEXT PRIMARY KEY,
        user_id TEXT NOT NULL,
        provider TEXT NOT NULL,
        data_json TEXT NOT NULL DEFAULT '{}',
        expires_at TEXT,
        updated_at TEXT NOT NULL DEFAULT (CURRENT_TIMESTAMP::text)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS realtime_events (
        seq BIGSERIAL PRIMARY KEY,
        table_id TEXT NOT NULL REFERENCES runtime_tables(id) ON DELETE CASCADE,
        event_type TEXT NOT NULL,
        payload_json TEXT NOT NULL,
        created_at TEXT NOT NULL DEFAULT (CURRENT_TIMESTAMP::text),
        outbox_id BIGINT
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_realtime_events_table_seq
    ON realtime_events(table_id, seq)
    """,
    """
    CREATE UNIQUE INDEX IF NOT EXISTS idx_realtime_events_outbox_id
    ON realtime_events(outbox_id)
    WHERE outbox_id IS NOT NULL
    """,
    """
    CREATE TABLE IF NOT EXISTS recovery_actions (
        id BIGSERIAL PRIMARY KEY,
        table_id TEXT NOT NULL REFERENCES runtime_tables(id) ON DELETE CASCADE,
        hand_id TEXT,
        action TEXT NOT NULL,
        reason TEXT NOT NULL,
        details_json TEXT NOT NULL DEFAULT '{}',
        created_at TEXT NOT NULL DEFAULT (CURRENT_TIMESTAMP::text)
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_recovery_actions_table_id
    ON recovery_actions(table_id, id)
    """,
    """
    CREATE TABLE IF NOT EXISTS hand_actions (
        id BIGSERIAL PRIMARY KEY,
        hand_id TEXT NOT NULL,
        table_id TEXT NOT NULL REFERENCES runtime_tables(id) ON DELETE CASCADE,
        action_no INTEGER NOT NULL,
        player_id TEXT NOT NULL,
        seat_no INTEGER NOT NULL,
        action TEXT NOT NULL,
        amount INTEGER,
        state_json TEXT NOT NULL,
        created_at TEXT NOT NULL DEFAULT (CURRENT_TIMESTAMP::text),
        UNIQUE(hand_id, action_no)
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_hand_actions_table_hand
    ON hand_actions(table_id, hand_id, action_no)
    """,
    """
    CREATE TABLE IF NOT EXISTS hand_secrets (
        hand_id TEXT PRIMARY KEY,
        table_id TEXT NOT NULL REFERENCES runtime_tables(id) ON DELETE CASCADE,
        deck_json TEXT NOT NULL,
        created_at TEXT NOT NULL DEFAULT (CURRENT_TIMESTAMP::text)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS hand_private_cards (
        hand_id TEXT NOT NULL,
        table_id TEXT NOT NULL REFERENCES runtime_tables(id) ON DELETE CASCADE,
        player_id TEXT NOT NULL,
        cards_json TEXT NOT NULL,
        PRIMARY KEY (hand_id, player_id)
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_hand_private_cards_table_player
    ON hand_private_cards(table_id, player_id)
    """,
    """
    CREATE TABLE IF NOT EXISTS table_ledger (
        id BIGSERIAL PRIMARY KEY,
        table_id TEXT NOT NULL REFERENCES runtime_tables(id) ON DELETE CASCADE,
        player_id TEXT NOT NULL,
        entry_type TEXT NOT NULL,
        amount INTEGER NOT NULL,
        details_json TEXT NOT NULL DEFAULT '{}',
        created_at TEXT NOT NULL DEFAULT (CURRENT_TIMESTAMP::text)
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_table_ledger_table_player
    ON table_ledger(table_id, player_id, id)
    """,
    """
    CREATE TABLE IF NOT EXISTS player_balances (
        user_id TEXT PRIMARY KEY,
        balance INTEGER NOT NULL DEFAULT 0 CHECK(balance >= 0),
        updated_at TEXT NOT NULL DEFAULT (CURRENT_TIMESTAMP::text)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS operator_audit (
        id BIGSERIAL PRIMARY KEY,
        table_id TEXT REFERENCES runtime_tables(id) ON DELETE CASCADE,
        action TEXT NOT NULL,
        details_json TEXT NOT NULL DEFAULT '{}',
        created_at TEXT NOT NULL DEFAULT (CURRENT_TIMESTAMP::text)
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_operator_audit_table_id
    ON operator_audit(table_id, id)
    """,
    """
    CREATE TABLE IF NOT EXISTS tournament_registrations (
        table_id TEXT NOT NULL REFERENCES runtime_tables(id) ON DELETE CASCADE,
        user_id TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'registered',
        registered_at TEXT NOT NULL DEFAULT (CURRENT_TIMESTAMP::text),
        withdrawn_at TEXT,
        PRIMARY KEY (table_id, user_id)
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_tournament_registrations_table_status
    ON tournament_registrations(table_id, status)
    """,
    """
    CREATE TABLE IF NOT EXISTS cash_waitlist (
        id BIGSERIAL PRIMARY KEY,
        table_id TEXT NOT NULL REFERENCES runtime_tables(id) ON DELETE CASCADE,
        user_id TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'waiting',
        created_at TEXT NOT NULL DEFAULT (CURRENT_TIMESTAMP::text),
        updated_at TEXT NOT NULL DEFAULT (CURRENT_TIMESTAMP::text),
        UNIQUE(table_id, user_id)
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_cash_waitlist_table_status_id
    ON cash_waitlist(table_id, status, id)
    """,
    """
    CREATE TABLE IF NOT EXISTS seat_reservations (
        id TEXT PRIMARY KEY,
        table_id TEXT NOT NULL REFERENCES runtime_tables(id) ON DELETE CASCADE,
        seat_no INTEGER NOT NULL,
        user_id TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'active',
        expires_at_epoch BIGINT NOT NULL,
        created_at TEXT NOT NULL DEFAULT (CURRENT_TIMESTAMP::text),
        updated_at TEXT NOT NULL DEFAULT (CURRENT_TIMESTAMP::text)
    )
    """,
    """
    CREATE UNIQUE INDEX IF NOT EXISTS idx_active_reservation_seat
    ON seat_reservations(table_id, seat_no)
    WHERE status = 'active'
    """,
    """
    CREATE UNIQUE INDEX IF NOT EXISTS idx_active_reservation_user
    ON seat_reservations(table_id, user_id)
    WHERE status = 'active'
    """,
    """
    CREATE TABLE IF NOT EXISTS idempotency_records (
        user_id TEXT NOT NULL,
        operation TEXT NOT NULL,
        idempotency_key TEXT NOT NULL,
        request_fingerprint TEXT NOT NULL,
        response_json TEXT NOT NULL,
        status_code INTEGER NOT NULL DEFAULT 200,
        command_status TEXT NOT NULL DEFAULT 'completed',
        created_at TEXT NOT NULL DEFAULT (CURRENT_TIMESTAMP::text),
        updated_at TEXT NOT NULL DEFAULT (CURRENT_TIMESTAMP::text),
        PRIMARY KEY (user_id, operation, idempotency_key)
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_idempotency_records_created_at
    ON idempotency_records(created_at)
    """,
    """
    CREATE TABLE IF NOT EXISTS realtime_outbox (
        id BIGSERIAL PRIMARY KEY,
        table_id TEXT NOT NULL REFERENCES runtime_tables(id) ON DELETE CASCADE,
        event_type TEXT NOT NULL,
        payload_json TEXT NOT NULL,
        created_at TEXT NOT NULL DEFAULT (CURRENT_TIMESTAMP::text),
        dispatched_at TEXT
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_realtime_outbox_pending
    ON realtime_outbox(table_id, dispatched_at, id)
    """,
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
]

POSTGRES_SCHEMA_STATEMENTS.extend([
    """
CREATE TABLE IF NOT EXISTS table_chat (
    sequence BIGSERIAL PRIMARY KEY,
    table_id TEXT NOT NULL REFERENCES runtime_tables(id) ON DELETE CASCADE,
    player_id TEXT NOT NULL,
    display_name TEXT NOT NULL,
    text TEXT NOT NULL CHECK(length(text) BETWEEN 1 AND 500),
    client_message_id TEXT NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE(table_id, player_id, client_message_id)
)
    """,
    """
CREATE INDEX IF NOT EXISTS idx_table_chat_history ON table_chat(table_id, sequence)
    """,
    """
CREATE TABLE IF NOT EXISTS chat_senders (player_id TEXT PRIMARY KEY, last_sent DOUBLE PRECISION NOT NULL)
    """,
])
