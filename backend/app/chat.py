"""Private, bounded table chat; game state and public sockets stay independent."""
from __future__ import annotations

import time
from datetime import datetime, timezone

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field, field_validator

from .db import connect, transaction
from . import service

router = APIRouter()


class ChatMessage(BaseModel):
    text: str = Field(min_length=1, max_length=500)
    client_message_id: str = Field(min_length=1, max_length=80, pattern=r"^[a-zA-Z0-9_-]+$")

    @field_validator("text")
    @classmethod
    def printable_text(cls, value: str) -> str:
        if any(ord(char) < 32 and char not in "\n\t" for char in value):
            raise ValueError("Message contains control characters")
        return value


def _session(session_id: str) -> dict:
    try:
        return service.get_session(session_id)
    except (service.NotFoundError, service.AuthenticationError) as exc:
        raise HTTPException(401, "Chat authentication required") from exc


def _membership(conn, table_id: str, user_id: str) -> None:
    table = conn.execute("SELECT status FROM runtime_tables WHERE id = ?", (table_id,)).fetchone()
    if table is None:
        raise HTTPException(404, "Table not found")
    seat = conn.execute("SELECT 1 FROM runtime_seats WHERE table_id = ? AND player_id = ?", (table_id, user_id)).fetchone()
    if seat is None:
        raise HTTPException(403, "Chat is available to seated players")
    if table["status"] == "closed":
        raise HTTPException(409, "Table is closed")


@router.get("/api/v1/tables/{table_id}/chat")
def history(table_id: str, x_session_id: str = Header(default="")) -> list[dict]:
    session = _session(x_session_id)
    conn = connect()
    try:
        _membership(conn, table_id, session["user_id"])
        rows = conn.execute(
            "SELECT sequence, player_id, display_name, text, created_at FROM table_chat "
            "WHERE table_id = ? ORDER BY sequence DESC LIMIT 50", (table_id,),
        ).fetchall()
        return [dict(row) for row in reversed(rows)]
    finally:
        conn.close()


@router.post("/api/v1/tables/{table_id}/chat", status_code=201)
def send(table_id: str, message: ChatMessage, x_session_id: str = Header(default="")) -> dict:
    session = _session(x_session_id)
    text = message.text.strip()
    if not text:
        raise HTTPException(422, "Message is empty")
    user_id = session["user_id"]
    with transaction() as conn:
        _membership(conn, table_id, user_id)
        existing = conn.execute(
            "SELECT sequence, player_id, display_name, text, created_at FROM table_chat "
            "WHERE table_id = ? AND player_id = ? AND client_message_id = ?",
            (table_id, user_id, message.client_message_id),
        ).fetchone()
        if existing:
            if existing["text"] != text:
                raise HTTPException(409, "Message ID already used")
            return dict(existing)
        conn.execute("INSERT INTO chat_senders (player_id, last_sent) VALUES (?, 0) ON CONFLICT (player_id) DO NOTHING", (user_id,))
        now = time.time()
        updated = conn.execute(
            "UPDATE chat_senders SET last_sent = ? WHERE player_id = ? AND last_sent <= ? RETURNING player_id",
            (now, user_id, now - 2),
        ).fetchone()
        if updated is None:
            raise HTTPException(429, "Wait two seconds between messages", headers={"Retry-After": "2"})
        profile = session["data"].get("telegram_user") or {}
        if not isinstance(profile, dict):
            profile = {}
        name = " ".join(str(profile.get(key) or "").strip() for key in ("first_name", "last_name")).strip()
        name = (name or ("@" + str(profile["username"]) if profile.get("username") else user_id))[:100]
        row = conn.execute(
            "INSERT INTO table_chat (table_id, player_id, display_name, text, client_message_id, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?) RETURNING sequence, player_id, display_name, text, created_at",
            (table_id, user_id, name, text, message.client_message_id, datetime.now(timezone.utc).isoformat()),
        ).fetchone()
        # Keep a bounded history per table; the UI shows the latest 50 messages.
        conn.execute(
            "DELETE FROM table_chat WHERE table_id = ? AND sequence NOT IN "
            "(SELECT sequence FROM table_chat WHERE table_id = ? ORDER BY sequence DESC LIMIT 200)",
            (table_id, table_id),
        )
        return dict(row)
