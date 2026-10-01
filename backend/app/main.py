from __future__ import annotations

from collections import defaultdict
import os
from typing import Any

from fastapi import FastAPI, Header, HTTPException, Response, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field

from .db import ensure_schema
from .telegram_auth import TelegramAuthError, validate_init_data
from .service import (
    ConflictError,
    append_table_event,
    NotFoundError,
    complete_hand,
    create_session,
    create_table,
    delete_session,
    get_player_table_view,
    get_session,
    get_table_state,
    join_table,
    join_table_with_session,
    latest_table_seq,
    list_hand_actions,
    list_hand_history,
    list_recovery_actions,
    list_table_events_since,
    list_tables,
    set_blind_level,
    set_hand_pot,
    operator_abort_hand,
    set_operator_status,
    settle_showdown,
    stand,
    start_hand,
    submit_player_action,
    submit_player_action_with_session,
)

app = FastAPI(title="INARENA API", version="0.2.0")


class TableCreate(BaseModel):
    name: str = "INARENA Table"


class JoinRequest(BaseModel):
    player_id: str = Field(min_length=1)
    seat_no: int = Field(ge=1, le=9)
    stack: int = Field(ge=0)


class AuthJoinRequest(BaseModel):
    seat_no: int = Field(ge=1, le=9)
    stack: int = Field(ge=0)


class StandRequest(BaseModel):
    player_id: str = Field(min_length=1)


class StartHandRequest(BaseModel):
    button_seat: int | None = Field(default=None, ge=1, le=9)


class PotRequest(BaseModel):
    pot: int = Field(ge=0)


class CompleteHandRequest(BaseModel):
    payouts: dict[str, int]


class PlayerActionRequest(BaseModel):
    player_id: str = Field(min_length=1)
    action: str = Field(min_length=1)
    expected_action_no: int = Field(ge=0)
    amount: int | None = Field(default=None, ge=0)


class AuthPlayerActionRequest(BaseModel):
    action: str = Field(min_length=1)
    expected_action_no: int = Field(ge=0)
    amount: int | None = Field(default=None, ge=0)


class BlindLevelRequest(BaseModel):
    small_blind: int = Field(gt=0)
    big_blind: int = Field(gt=0)


class RecoveryRequest(BaseModel):
    reason: str = Field(min_length=1, max_length=500)


class TelegramAuthRequest(BaseModel):
    init_data: str = Field(min_length=1)


class SessionCreate(BaseModel):
    user_id: str = Field(min_length=1)
    provider: str = Field(min_length=1)
    data: dict[str, Any] = Field(default_factory=dict)
    expires_at: str | None = None


class ConnectionManager:
    def __init__(self) -> None:
        self.connections: dict[str, set[WebSocket]] = defaultdict(set)

    async def connect(self, table_id: str, websocket: WebSocket) -> None:
        await websocket.accept()
        self.connections[table_id].add(websocket)

    def disconnect(self, table_id: str, websocket: WebSocket) -> None:
        self.connections[table_id].discard(websocket)
        if not self.connections[table_id]:
            self.connections.pop(table_id, None)

    async def broadcast_state(self, table_id: str, event_type: str = "table_state") -> None:
        state = get_table_state(table_id)
        event = append_table_event(table_id, event_type, state)
        dead: list[WebSocket] = []
        for socket in self.connections.get(table_id, set()):
            try:
                await socket.send_json(
                    {
                        "type": "table_event",
                        "seq": event["seq"],
                        "event_type": event["event_type"],
                        "data": state,
                    }
                )
            except Exception:
                dead.append(socket)
        for socket in dead:
            self.disconnect(table_id, socket)


manager = ConnectionManager()


@app.on_event("startup")
def startup() -> None:
    ensure_schema()


def _require_legacy_api() -> None:
    if os.getenv("INARENA_ENABLE_LEGACY_API") != "1":
        raise HTTPException(status_code=404, detail="not found")


def _require_operator(x_operator_key: str | None) -> None:
    expected = os.getenv("INARENA_OPERATOR_KEY")
    if not expected:
        raise HTTPException(status_code=503, detail="operator access is not configured")
    if x_operator_key != expected:
        raise HTTPException(status_code=401, detail="invalid operator key")


def _http_error(exc: Exception) -> HTTPException:
    if isinstance(exc, NotFoundError):
        return HTTPException(status_code=404, detail=str(exc))
    if isinstance(exc, ConflictError):
        return HTTPException(status_code=409, detail=str(exc))
    return HTTPException(status_code=500, detail="internal error")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/v1/tables")
def api_list_tables() -> list[dict[str, Any]]:
    return list_tables()


@app.post("/api/v1/tables", status_code=201)
def api_create_table(payload: TableCreate) -> dict[str, Any]:
    return create_table(payload.name)


@app.get("/api/v1/tables/{table_id}")
def api_get_table(table_id: str) -> dict[str, Any]:
    try:
        return get_table_state(table_id)
    except Exception as exc:
        raise _http_error(exc) from exc


@app.post("/api/v1/tables/{table_id}/join-auth")
async def api_join_authenticated(
    table_id: str,
    payload: AuthJoinRequest,
    x_session_id: str | None = Header(default=None, alias="X-Session-ID"),
) -> dict[str, Any]:
    if not x_session_id:
        raise HTTPException(status_code=401, detail="session is required")
    try:
        state = join_table_with_session(
            table_id,
            x_session_id,
            payload.seat_no,
            payload.stack,
        )
        await manager.broadcast_state(table_id, "player_joined")
        return state
    except Exception as exc:
        raise _http_error(exc) from exc


@app.get("/api/v1/tables/{table_id}/view")
def api_player_table_view(
    table_id: str,
    x_session_id: str | None = Header(default=None, alias="X-Session-ID"),
) -> dict[str, Any]:
    if not x_session_id:
        raise HTTPException(status_code=401, detail="session is required")
    try:
        return get_player_table_view(table_id, x_session_id)
    except Exception as exc:
        raise _http_error(exc) from exc


@app.post("/api/v1/tables/{table_id}/join")
async def api_join(table_id: str, payload: JoinRequest) -> dict[str, Any]:
    _require_legacy_api()
    try:
        state = join_table(table_id, payload.player_id, payload.seat_no, payload.stack)
        await manager.broadcast_state(table_id, "player_joined")
        return state
    except Exception as exc:
        raise _http_error(exc) from exc


@app.post("/api/v1/tables/{table_id}/stand")
async def api_stand(table_id: str, payload: StandRequest) -> dict[str, Any]:
    try:
        state = stand(table_id, payload.player_id)
        await manager.broadcast_state(table_id, "player_stood")
        return state
    except Exception as exc:
        raise _http_error(exc) from exc


@app.post("/api/v1/tables/{table_id}/start-hand")
async def api_start_hand(table_id: str, payload: StartHandRequest) -> dict[str, Any]:
    try:
        state = start_hand(table_id, payload.button_seat)
        await manager.broadcast_state(table_id, "hand_started")
        return state
    except Exception as exc:
        raise _http_error(exc) from exc


@app.post("/api/v1/tables/{table_id}/action-auth")
async def api_authenticated_player_action(
    table_id: str,
    payload: AuthPlayerActionRequest,
    x_session_id: str | None = Header(default=None, alias="X-Session-ID"),
) -> dict[str, Any]:
    if not x_session_id:
        raise HTTPException(status_code=401, detail="session is required")
    try:
        state = submit_player_action_with_session(
            table_id,
            x_session_id,
            payload.action,
            payload.expected_action_no,
            payload.amount,
        )
        await manager.broadcast_state(table_id, "player_action")
        return state
    except Exception as exc:
        raise _http_error(exc) from exc


@app.post("/api/v1/tables/{table_id}/action")
async def api_player_action(
    table_id: str, payload: PlayerActionRequest
) -> dict[str, Any]:
    _require_legacy_api()
    try:
        state = submit_player_action(
            table_id,
            payload.player_id,
            payload.action,
            payload.expected_action_no,
            payload.amount,
        )
        await manager.broadcast_state(table_id, "player_action")
        return state
    except Exception as exc:
        raise _http_error(exc) from exc


@app.post("/api/v1/tables/{table_id}/pot")
async def api_set_pot(table_id: str, payload: PotRequest) -> dict[str, Any]:
    _require_legacy_api()
    try:
        state = set_hand_pot(table_id, payload.pot)
        await manager.broadcast_state(table_id, "pot_updated")
        return state
    except Exception as exc:
        raise _http_error(exc) from exc


@app.post("/api/v1/tables/{table_id}/complete-hand")
async def api_complete_hand(
    table_id: str, payload: CompleteHandRequest
) -> dict[str, Any]:
    _require_legacy_api()
    try:
        state = complete_hand(table_id, payload.payouts)
        await manager.broadcast_state(table_id, "hand_completed")
        return state
    except Exception as exc:
        raise _http_error(exc) from exc


@app.post("/api/v1/auth/telegram", status_code=201)
def api_auth_telegram(payload: TelegramAuthRequest) -> dict[str, Any]:
    try:
        verified = validate_init_data(payload.init_data)
    except TelegramAuthError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc

    user = verified["user"]
    return create_session(
        user_id=f"tg:{user['id']}",
        provider="telegram",
        data={
            "telegram_user": user,
            "query_id": verified.get("query_id"),
            "start_param": verified.get("start_param"),
        },
    )


@app.post("/api/v1/sessions", status_code=201)
def api_create_session(payload: SessionCreate) -> dict[str, Any]:
    _require_legacy_api()
    return create_session(
        payload.user_id,
        payload.provider,
        payload.data,
        payload.expires_at,
    )


@app.get("/api/v1/sessions/{session_id}")
def api_get_session(session_id: str) -> dict[str, Any]:
    try:
        return get_session(session_id)
    except Exception as exc:
        raise _http_error(exc) from exc


@app.delete("/api/v1/sessions/{session_id}", status_code=204)
def api_delete_session(session_id: str) -> Response:
    try:
        delete_session(session_id)
        return Response(status_code=204)
    except Exception as exc:
        raise _http_error(exc) from exc


@app.get("/api/v1/operator/tables")
def operator_tables(
    x_operator_key: str | None = Header(default=None, alias="X-Operator-Key"),
) -> list[dict[str, Any]]:
    _require_operator(x_operator_key)
    return list_tables()


@app.post("/api/v1/operator/tables/{table_id}/blinds")
async def operator_set_blinds(
    table_id: str,
    payload: BlindLevelRequest,
    x_operator_key: str | None = Header(default=None, alias="X-Operator-Key"),
) -> dict[str, Any]:
    _require_operator(x_operator_key)
    try:
        state = set_blind_level(
            table_id,
            payload.small_blind,
            payload.big_blind,
        )
        await manager.broadcast_state(table_id, "blind_level_changed")
        return state
    except Exception as exc:
        raise _http_error(exc) from exc


@app.post("/api/v1/operator/tables/{table_id}/pause")
async def operator_pause_table(
    table_id: str,
    x_operator_key: str | None = Header(default=None, alias="X-Operator-Key"),
) -> dict[str, Any]:
    _require_operator(x_operator_key)
    try:
        state = set_operator_status(table_id, "paused")
        await manager.broadcast_state(table_id, "table_paused")
        return state
    except Exception as exc:
        raise _http_error(exc) from exc


@app.post("/api/v1/operator/tables/{table_id}/resume")
async def operator_resume_table(
    table_id: str,
    x_operator_key: str | None = Header(default=None, alias="X-Operator-Key"),
) -> dict[str, Any]:
    _require_operator(x_operator_key)
    try:
        state = set_operator_status(table_id, "open")
        await manager.broadcast_state(table_id, "table_resumed")
        return state
    except Exception as exc:
        raise _http_error(exc) from exc


@app.post("/api/v1/operator/tables/{table_id}/settle-showdown")
async def operator_settle_showdown(
    table_id: str,
    x_operator_key: str | None = Header(default=None, alias="X-Operator-Key"),
) -> dict[str, Any]:
    _require_operator(x_operator_key)
    try:
        state = settle_showdown(table_id)
        await manager.broadcast_state(table_id, "showdown_settled")
        return state
    except Exception as exc:
        raise _http_error(exc) from exc


@app.get("/api/v1/operator/tables/{table_id}/recovery-actions")
def operator_recovery_actions(
    table_id: str,
    limit: int = 100,
    x_operator_key: str | None = Header(default=None, alias="X-Operator-Key"),
) -> list[dict[str, Any]]:
    _require_operator(x_operator_key)
    try:
        return list_recovery_actions(table_id, limit)
    except Exception as exc:
        raise _http_error(exc) from exc


@app.post("/api/v1/operator/tables/{table_id}/abort-hand")
async def operator_abort_active_hand(
    table_id: str,
    payload: RecoveryRequest,
    x_operator_key: str | None = Header(default=None, alias="X-Operator-Key"),
) -> dict[str, Any]:
    _require_operator(x_operator_key)
    try:
        state = operator_abort_hand(table_id, payload.reason)
        await manager.broadcast_state(table_id, "hand_recovered")
        return state
    except Exception as exc:
        raise _http_error(exc) from exc


@app.get("/api/v1/tables/{table_id}/hands")
def api_hand_history(
    table_id: str,
    limit: int = 50,
) -> list[dict[str, Any]]:
    try:
        return list_hand_history(table_id, limit)
    except Exception as exc:
        raise _http_error(exc) from exc


@app.get("/api/v1/tables/{table_id}/hands/{hand_id}/actions")
def api_hand_actions(
    table_id: str,
    hand_id: str,
) -> list[dict[str, Any]]:
    try:
        return list_hand_actions(table_id, hand_id)
    except Exception as exc:
        raise _http_error(exc) from exc


@app.get("/api/v1/tables/{table_id}/events")
def api_table_events(
    table_id: str,
    after_seq: int = 0,
    limit: int = 100,
) -> list[dict[str, Any]]:
    try:
        return list_table_events_since(table_id, after_seq, limit)
    except Exception as exc:
        raise _http_error(exc) from exc


@app.websocket("/ws/tables/{table_id}")
async def table_socket(websocket: WebSocket, table_id: str) -> None:
    try:
        get_table_state(table_id)
    except NotFoundError:
        await websocket.close(code=4404)
        return

    await manager.connect(table_id, websocket)
    try:
        await websocket.send_json(
            {
                "type": "table_snapshot",
                "seq": latest_table_seq(table_id),
                "data": get_table_state(table_id),
            }
        )
        while True:
            message = await websocket.receive_json()
            if message.get("type") == "sync":
                after_seq = int(message.get("after_seq", 0) or 0)
                events = list_table_events_since(table_id, after_seq, 500)
                if events:
                    await websocket.send_json(
                        {"type": "table_replay", "events": events}
                    )
                else:
                    await websocket.send_json(
                        {
                            "type": "table_snapshot",
                            "seq": latest_table_seq(table_id),
                            "data": get_table_state(table_id),
                        }
                    )
    except WebSocketDisconnect:
        manager.disconnect(table_id, websocket)
