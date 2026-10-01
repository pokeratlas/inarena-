from __future__ import annotations

from collections import defaultdict
import asyncio
import os
from typing import Any

from fastapi import FastAPI, Header, HTTPException, Response, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field

from .db import ensure_schema
from .telegram_auth import TelegramAuthError, validate_init_data
from .service import (
    AuthenticationError,
    ConflictError,
    append_table_event,
    NotFoundError,
    complete_hand,
    configure_table,
    create_session,
    create_table,
    delete_session,
    dispatch_table_outbox,
    get_cash_waitlist_status,
    get_idempotent_result,
    reserve_idempotency_command,
    get_player_balance,
    get_player_table_view,
    get_tournament_registration,
    get_session,
    get_table_state,
    join_cash_waitlist,
    join_table,
    join_table_with_session,
    latest_table_seq,
    list_hand_actions,
    list_hand_history,
    list_player_hand_history,
    list_operator_audit,
    list_recovery_actions,
    list_table_events_since,
    list_tables,
    leave_cash_waitlist,
    claim_seat_reservation,
    refresh_cash_waitlist,
    set_blind_level,
    set_hand_pot,
    close_table,
    operator_abort_hand,
    operator_adjust_balance,
    operator_dashboard,
    register_tournament,
    refresh_session,
    set_blind_schedule_status,
    resolve_expired_action,
    set_operator_status,
    set_tournament_status,
    set_tournament_window,
    settle_showdown,
    store_idempotent_result,
    stand,
    stand_with_session,
    start_hand,
    submit_player_action,
    submit_player_action_with_session,
    tournament_addon,
    tournament_rebuy,
    unregister_tournament,
    configure_tournament_lifecycle,
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


class ReservationClaimRequest(BaseModel):
    reservation_id: str = Field(min_length=1)
    stack: int = Field(gt=0)


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


class BlindScheduleLevel(BaseModel):
    small_blind: int = Field(gt=0)
    big_blind: int = Field(gt=0)
    duration_seconds: int = Field(gt=0)


class TableConfigRequest(BaseModel):
    table_mode: str
    starting_stack: int = Field(gt=0)
    small_blind: int = Field(gt=0)
    big_blind: int = Field(gt=0)
    blind_schedule: list[BlindScheduleLevel] = Field(default_factory=list)
    cash_buyin_min: int = Field(default=1000, gt=0)
    cash_buyin_max: int = Field(default=100000, gt=0)
    rebuy_enabled: bool = False
    rebuy_stack: int = Field(default=0, ge=0)
    rebuy_max_per_player: int = Field(default=0, ge=0)
    addon_enabled: bool = False
    addon_stack: int = Field(default=0, ge=0)


class BalanceAdjustRequest(BaseModel):
    user_id: str = Field(min_length=1)
    delta: int


class WindowControlRequest(BaseModel):
    open: bool


class TournamentLifecycleRequest(BaseModel):
    scheduled_start_at: int | None = Field(default=None, ge=0)
    registration_open_at: int | None = Field(default=None, ge=0)
    registration_close_at: int | None = Field(default=None, ge=0)
    late_registration_close_at: int | None = Field(default=None, ge=0)


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
        events = dispatch_table_outbox(table_id)
        if not events:
            state = get_table_state(table_id)
            events = [append_table_event(table_id, event_type, state)]

        dead: list[WebSocket] = []
        for event in events:
            state = event["payload"]
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


def _idempotent_replay(
    session_id: str,
    operation: str,
    idempotency_key: str | None,
    payload: dict[str, Any],
) -> dict[str, Any] | None:
    if not idempotency_key:
        return None
    user_id = get_session(session_id)["user_id"]
    command = reserve_idempotency_command(
        user_id,
        operation,
        idempotency_key,
        payload,
    )
    if command["state"] == "replay":
        return command["response"]
    if command["state"] == "in_progress":
        raise ConflictError(
            "idempotent command is already in progress or outcome is pending"
        )
    return None


def _idempotent_store(
    session_id: str,
    operation: str,
    idempotency_key: str | None,
    payload: dict[str, Any],
    response: dict[str, Any],
) -> None:
    if not idempotency_key:
        return
    user_id = get_session(session_id)["user_id"]
    store_idempotent_result(
        user_id,
        operation,
        idempotency_key,
        payload,
        response,
    )


def _http_error(exc: Exception) -> HTTPException:
    if isinstance(exc, AuthenticationError):
        return HTTPException(status_code=401, detail=str(exc))
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
    _require_legacy_api()
    return create_table(payload.name)


@app.get("/api/v1/tables/{table_id}")
def api_get_table(table_id: str) -> dict[str, Any]:
    try:
        return get_table_state(table_id)
    except Exception as exc:
        raise _http_error(exc) from exc


@app.get("/api/v1/tables/{table_id}/waitlist")
def api_waitlist_status(
    table_id: str,
    x_session_id: str | None = Header(default=None, alias="X-Session-ID"),
) -> dict[str, Any]:
    if not x_session_id:
        raise HTTPException(status_code=401, detail="session is required")
    try:
        return get_cash_waitlist_status(table_id, x_session_id)
    except Exception as exc:
        raise _http_error(exc) from exc


@app.post("/api/v1/tables/{table_id}/waitlist")
async def api_waitlist_join(
    table_id: str,
    x_session_id: str | None = Header(default=None, alias="X-Session-ID"),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> dict[str, Any]:
    if not x_session_id:
        raise HTTPException(status_code=401, detail="session is required")
    try:
        payload = {"table_id": table_id}
        replay = _idempotent_replay(
            x_session_id, "waitlist-join", idempotency_key, payload
        )
        if replay is not None:
            return replay
        result = join_cash_waitlist(table_id, x_session_id)
        _idempotent_store(
            x_session_id, "waitlist-join", idempotency_key, payload, result
        )
        await manager.broadcast_state(table_id, "waitlist_joined")
        return result
    except Exception as exc:
        raise _http_error(exc) from exc


@app.delete("/api/v1/tables/{table_id}/waitlist")
async def api_waitlist_leave(
    table_id: str,
    x_session_id: str | None = Header(default=None, alias="X-Session-ID"),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> dict[str, Any]:
    if not x_session_id:
        raise HTTPException(status_code=401, detail="session is required")
    try:
        payload = {"table_id": table_id}
        replay = _idempotent_replay(
            x_session_id, "waitlist-leave", idempotency_key, payload
        )
        if replay is not None:
            return replay
        result = leave_cash_waitlist(table_id, x_session_id)
        _idempotent_store(
            x_session_id, "waitlist-leave", idempotency_key, payload, result
        )
        await manager.broadcast_state(table_id, "waitlist_left")
        return result
    except Exception as exc:
        raise _http_error(exc) from exc


@app.post("/api/v1/tables/{table_id}/reservations/claim")
async def api_claim_reservation(
    table_id: str,
    payload: ReservationClaimRequest,
    x_session_id: str | None = Header(default=None, alias="X-Session-ID"),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> dict[str, Any]:
    if not x_session_id:
        raise HTTPException(status_code=401, detail="session is required")
    try:
        request_payload = {
            "table_id": table_id,
            "reservation_id": payload.reservation_id,
            "stack": payload.stack,
        }
        replay = _idempotent_replay(
            x_session_id,
            "reservation-claim",
            idempotency_key,
            request_payload,
        )
        if replay is not None:
            return replay
        state = claim_seat_reservation(
            table_id,
            x_session_id,
            payload.reservation_id,
            payload.stack,
        )
        _idempotent_store(
            x_session_id,
            "reservation-claim",
            idempotency_key,
            request_payload,
            state,
        )
        await manager.broadcast_state(table_id, "seat_reservation_claimed")
        return state
    except Exception as exc:
        raise _http_error(exc) from exc


@app.post("/api/v1/tables/{table_id}/join-auth")
async def api_join_authenticated(
    table_id: str,
    payload: AuthJoinRequest,
    x_session_id: str | None = Header(default=None, alias="X-Session-ID"),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> dict[str, Any]:
    if not x_session_id:
        raise HTTPException(status_code=401, detail="session is required")
    try:
        request_payload = {
            "table_id": table_id,
            "seat_no": payload.seat_no,
            "stack": payload.stack,
        }
        replay = _idempotent_replay(
            x_session_id,
            "join-auth",
            idempotency_key,
            request_payload,
        )
        if replay is not None:
            return replay
        state = join_table_with_session(
            table_id,
            x_session_id,
            payload.seat_no,
            payload.stack,
        )
        _idempotent_store(
            x_session_id,
            "join-auth",
            idempotency_key,
            request_payload,
            state,
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


@app.post("/api/v1/tables/{table_id}/stand-auth")
async def api_stand_authenticated(
    table_id: str,
    x_session_id: str | None = Header(default=None, alias="X-Session-ID"),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> dict[str, Any]:
    if not x_session_id:
        raise HTTPException(status_code=401, detail="session is required")
    try:
        request_payload = {"table_id": table_id}
        replay = _idempotent_replay(
            x_session_id,
            "stand-auth",
            idempotency_key,
            request_payload,
        )
        if replay is not None:
            return replay
        state = stand_with_session(table_id, x_session_id)
        _idempotent_store(
            x_session_id,
            "stand-auth",
            idempotency_key,
            request_payload,
            state,
        )
        await manager.broadcast_state(table_id, "player_stood")
        return state
    except Exception as exc:
        raise _http_error(exc) from exc


@app.post("/api/v1/tables/{table_id}/stand")
async def api_stand(table_id: str, payload: StandRequest) -> dict[str, Any]:
    _require_legacy_api()
    try:
        state = stand(table_id, payload.player_id)
        await manager.broadcast_state(table_id, "player_stood")
        return state
    except Exception as exc:
        raise _http_error(exc) from exc


@app.post("/api/v1/tables/{table_id}/start-hand")
async def api_start_hand(table_id: str, payload: StartHandRequest) -> dict[str, Any]:
    _require_legacy_api()
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
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> dict[str, Any]:
    if not x_session_id:
        raise HTTPException(status_code=401, detail="session is required")
    try:
        request_payload = {
            "table_id": table_id,
            "action": payload.action,
            "expected_action_no": payload.expected_action_no,
            "amount": payload.amount,
        }
        replay = _idempotent_replay(
            x_session_id,
            "action-auth",
            idempotency_key,
            request_payload,
        )
        if replay is not None:
            return replay
        state = submit_player_action_with_session(
            table_id,
            x_session_id,
            payload.action,
            payload.expected_action_no,
            payload.amount,
        )
        _idempotent_store(
            x_session_id,
            "action-auth",
            idempotency_key,
            request_payload,
            state,
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


@app.get("/api/v1/auth/session")
def api_current_session(
    x_session_id: str | None = Header(default=None, alias="X-Session-ID"),
) -> dict[str, Any]:
    if not x_session_id:
        raise HTTPException(status_code=401, detail="session is required")
    try:
        return get_session(x_session_id)
    except Exception as exc:
        raise _http_error(exc) from exc


@app.post("/api/v1/auth/refresh")
def api_refresh_session(
    x_session_id: str | None = Header(default=None, alias="X-Session-ID"),
) -> dict[str, Any]:
    if not x_session_id:
        raise HTTPException(status_code=401, detail="session is required")
    try:
        return refresh_session(x_session_id)
    except Exception as exc:
        raise _http_error(exc) from exc


@app.get("/api/v1/sessions/{session_id}")
def api_get_session(session_id: str) -> dict[str, Any]:
    _require_legacy_api()
    try:
        return get_session(session_id)
    except Exception as exc:
        raise _http_error(exc) from exc


@app.delete("/api/v1/sessions/{session_id}", status_code=204)
def api_delete_session(session_id: str) -> Response:
    _require_legacy_api()
    try:
        delete_session(session_id)
        return Response(status_code=204)
    except Exception as exc:
        raise _http_error(exc) from exc


@app.post("/api/v1/operator/tables", status_code=201)
def operator_create_table(
    payload: TableCreate,
    x_operator_key: str | None = Header(default=None, alias="X-Operator-Key"),
) -> dict[str, Any]:
    _require_operator(x_operator_key)
    return create_table(payload.name)


@app.post("/api/v1/operator/tables/{table_id}/start-hand")
async def operator_start_hand(
    table_id: str,
    payload: StartHandRequest,
    x_operator_key: str | None = Header(default=None, alias="X-Operator-Key"),
) -> dict[str, Any]:
    _require_operator(x_operator_key)
    try:
        state = start_hand(table_id, payload.button_seat)
        await manager.broadcast_state(table_id, "hand_started")
        return state
    except Exception as exc:
        raise _http_error(exc) from exc


@app.post("/api/v1/operator/balance")
def operator_balance_adjustment(
    payload: BalanceAdjustRequest,
    x_operator_key: str | None = Header(default=None, alias="X-Operator-Key"),
) -> dict[str, Any]:
    _require_operator(x_operator_key)
    try:
        return operator_adjust_balance(payload.user_id, payload.delta)
    except Exception as exc:
        raise _http_error(exc) from exc


@app.get("/api/v1/operator/audit")
def operator_audit_log(
    table_id: str | None = None,
    limit: int = 100,
    x_operator_key: str | None = Header(default=None, alias="X-Operator-Key"),
) -> list[dict[str, Any]]:
    _require_operator(x_operator_key)
    try:
        return list_operator_audit(table_id, limit)
    except Exception as exc:
        raise _http_error(exc) from exc


@app.get("/api/v1/operator/dashboard")
def operator_dashboard_view(
    x_operator_key: str | None = Header(default=None, alias="X-Operator-Key"),
) -> dict[str, Any]:
    _require_operator(x_operator_key)
    return operator_dashboard()


@app.post("/api/v1/operator/tables/{table_id}/tournament/lifecycle")
async def operator_tournament_lifecycle(
    table_id: str,
    payload: TournamentLifecycleRequest,
    x_operator_key: str | None = Header(default=None, alias="X-Operator-Key"),
) -> dict[str, Any]:
    _require_operator(x_operator_key)
    try:
        state = configure_tournament_lifecycle(
            table_id,
            payload.scheduled_start_at,
            payload.registration_open_at,
            payload.registration_close_at,
            payload.late_registration_close_at,
        )
        await manager.broadcast_state(table_id, "tournament_lifecycle_configured")
        return state
    except Exception as exc:
        raise _http_error(exc) from exc


@app.post("/api/v1/operator/tables/{table_id}/tournament/{command}")
async def operator_tournament_command(
    table_id: str,
    command: str,
    x_operator_key: str | None = Header(default=None, alias="X-Operator-Key"),
) -> dict[str, Any]:
    _require_operator(x_operator_key)
    try:
        state = set_tournament_status(table_id, command)
        await manager.broadcast_state(table_id, f"tournament_{command}")
        return state
    except Exception as exc:
        raise _http_error(exc) from exc


@app.post("/api/v1/operator/tables/{table_id}/configure")
async def operator_configure_table(
    table_id: str,
    payload: TableConfigRequest,
    x_operator_key: str | None = Header(default=None, alias="X-Operator-Key"),
) -> dict[str, Any]:
    _require_operator(x_operator_key)
    try:
        state = configure_table(
            table_id,
            payload.table_mode,
            payload.starting_stack,
            payload.small_blind,
            payload.big_blind,
            [level.model_dump() for level in payload.blind_schedule],
            payload.cash_buyin_min,
            payload.cash_buyin_max,
            payload.rebuy_enabled,
            payload.rebuy_stack,
            payload.rebuy_max_per_player,
            payload.addon_enabled,
            payload.addon_stack,
        )
        await manager.broadcast_state(table_id, "table_configured")
        return state
    except Exception as exc:
        raise _http_error(exc) from exc


@app.post("/api/v1/operator/tables/{table_id}/waitlist/refresh")
async def operator_refresh_waitlist(
    table_id: str,
    x_operator_key: str | None = Header(default=None, alias="X-Operator-Key"),
) -> dict[str, Any]:
    _require_operator(x_operator_key)
    try:
        state = refresh_cash_waitlist(table_id)
        await manager.broadcast_state(table_id, "waitlist_refreshed")
        return state
    except Exception as exc:
        raise _http_error(exc) from exc


@app.post("/api/v1/operator/tables/{table_id}/resolve-timeout")
async def operator_resolve_timeout(
    table_id: str,
    x_operator_key: str | None = Header(default=None, alias="X-Operator-Key"),
) -> dict[str, Any]:
    _require_operator(x_operator_key)
    try:
        state = resolve_expired_action(table_id)
        await manager.broadcast_state(table_id, "action_timeout_resolved")
        return state
    except Exception as exc:
        raise _http_error(exc) from exc


@app.get("/api/v1/operator/tables")
def operator_tables(
    x_operator_key: str | None = Header(default=None, alias="X-Operator-Key"),
) -> list[dict[str, Any]]:
    _require_operator(x_operator_key)
    return list_tables()


@app.post("/api/v1/operator/tables/{table_id}/window/{window}")
async def operator_window_control(
    table_id: str,
    window: str,
    payload: WindowControlRequest,
    x_operator_key: str | None = Header(default=None, alias="X-Operator-Key"),
) -> dict[str, Any]:
    _require_operator(x_operator_key)
    try:
        state = set_tournament_window(table_id, window, payload.open)
        await manager.broadcast_state(
            table_id,
            f"{window}_window_{'opened' if payload.open else 'closed'}",
        )
        return state
    except Exception as exc:
        raise _http_error(exc) from exc


@app.post("/api/v1/operator/tables/{table_id}/close")
async def operator_close_table(
    table_id: str,
    x_operator_key: str | None = Header(default=None, alias="X-Operator-Key"),
) -> dict[str, Any]:
    _require_operator(x_operator_key)
    try:
        state = close_table(table_id)
        await manager.broadcast_state(table_id, "table_closed")
        return state
    except Exception as exc:
        raise _http_error(exc) from exc


@app.post("/api/v1/operator/tables/{table_id}/blind-schedule/{command}")
async def operator_blind_schedule_command(
    table_id: str,
    command: str,
    x_operator_key: str | None = Header(default=None, alias="X-Operator-Key"),
) -> dict[str, Any]:
    _require_operator(x_operator_key)
    try:
        state = set_blind_schedule_status(table_id, command)
        await manager.broadcast_state(
            table_id,
            f"blind_schedule_{command}",
        )
        return state
    except Exception as exc:
        raise _http_error(exc) from exc


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


@app.post("/api/v1/tournaments/{table_id}/register")
async def api_tournament_register(
    table_id: str,
    x_session_id: str | None = Header(default=None, alias="X-Session-ID"),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> dict[str, Any]:
    if not x_session_id:
        raise HTTPException(status_code=401, detail="session is required")
    try:
        payload = {"table_id": table_id}
        replay = _idempotent_replay(
            x_session_id, "tournament-register", idempotency_key, payload
        )
        if replay is not None:
            return replay
        result = register_tournament(table_id, x_session_id)
        _idempotent_store(
            x_session_id, "tournament-register", idempotency_key, payload, result
        )
        await manager.broadcast_state(table_id, "tournament_registered")
        return result
    except Exception as exc:
        raise _http_error(exc) from exc


@app.delete("/api/v1/tournaments/{table_id}/register")
async def api_tournament_unregister(
    table_id: str,
    x_session_id: str | None = Header(default=None, alias="X-Session-ID"),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> dict[str, Any]:
    if not x_session_id:
        raise HTTPException(status_code=401, detail="session is required")
    try:
        payload = {"table_id": table_id}
        replay = _idempotent_replay(
            x_session_id, "tournament-unregister", idempotency_key, payload
        )
        if replay is not None:
            return replay
        result = unregister_tournament(table_id, x_session_id)
        _idempotent_store(
            x_session_id, "tournament-unregister", idempotency_key, payload, result
        )
        await manager.broadcast_state(table_id, "tournament_unregistered")
        return result
    except Exception as exc:
        raise _http_error(exc) from exc


@app.get("/api/v1/tournaments/{table_id}/registration")
def api_tournament_registration(
    table_id: str,
    x_session_id: str | None = Header(default=None, alias="X-Session-ID"),
) -> dict[str, Any]:
    if not x_session_id:
        raise HTTPException(status_code=401, detail="session is required")
    try:
        return get_tournament_registration(table_id, x_session_id)
    except Exception as exc:
        raise _http_error(exc) from exc


@app.post("/api/v1/tables/{table_id}/rebuy")
async def api_tournament_rebuy(
    table_id: str,
    x_session_id: str | None = Header(default=None, alias="X-Session-ID"),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> dict[str, Any]:
    if not x_session_id:
        raise HTTPException(status_code=401, detail="session is required")
    try:
        payload = {"table_id": table_id}
        replay = _idempotent_replay(
            x_session_id, "tournament-rebuy", idempotency_key, payload
        )
        if replay is not None:
            return replay
        state = tournament_rebuy(table_id, x_session_id)
        _idempotent_store(
            x_session_id, "tournament-rebuy", idempotency_key, payload, state
        )
        await manager.broadcast_state(table_id, "player_rebuy")
        return state
    except Exception as exc:
        raise _http_error(exc) from exc


@app.post("/api/v1/tables/{table_id}/addon")
async def api_tournament_addon(
    table_id: str,
    x_session_id: str | None = Header(default=None, alias="X-Session-ID"),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> dict[str, Any]:
    if not x_session_id:
        raise HTTPException(status_code=401, detail="session is required")
    try:
        payload = {"table_id": table_id}
        replay = _idempotent_replay(
            x_session_id, "tournament-addon", idempotency_key, payload
        )
        if replay is not None:
            return replay
        state = tournament_addon(table_id, x_session_id)
        _idempotent_store(
            x_session_id, "tournament-addon", idempotency_key, payload, state
        )
        await manager.broadcast_state(table_id, "player_addon")
        return state
    except Exception as exc:
        raise _http_error(exc) from exc


@app.get("/api/v1/me/balance")
def api_my_balance(
    x_session_id: str | None = Header(default=None, alias="X-Session-ID"),
) -> dict[str, Any]:
    if not x_session_id:
        raise HTTPException(status_code=401, detail="session is required")
    try:
        return get_player_balance(x_session_id)
    except Exception as exc:
        raise _http_error(exc) from exc


@app.get("/api/v1/me/hands")
def api_my_hand_history(
    limit: int = 50,
    x_session_id: str | None = Header(default=None, alias="X-Session-ID"),
) -> list[dict[str, Any]]:
    if not x_session_id:
        raise HTTPException(status_code=401, detail="session is required")
    try:
        return list_player_hand_history(x_session_id, limit)
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
            try:
                message = await asyncio.wait_for(
                    websocket.receive_json(),
                    timeout=1.0,
                )
            except asyncio.TimeoutError:
                try:
                    resolved = resolve_expired_action(table_id)
                    await manager.broadcast_state(
                        table_id,
                        "action_timeout_resolved",
                    )
                    if resolved.get("active_hand") is None:
                        continue
                except (ConflictError, NotFoundError):
                    pass
                continue

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
