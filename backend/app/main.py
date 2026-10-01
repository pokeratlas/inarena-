from __future__ import annotations

from collections import defaultdict
import os
from typing import Any

from fastapi import FastAPI, Header, HTTPException, Response, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field

from .db import ensure_schema
from .service import (
    ConflictError,
    append_table_event,
    NotFoundError,
    complete_hand,
    create_session,
    create_table,
    delete_session,
    get_session,
    get_table_state,
    join_table,
    latest_table_seq,
    list_table_events_since,
    list_tables,
    set_hand_pot,
    set_operator_status,
    stand,
    start_hand,
)

app = FastAPI(title="INARENA API", version="0.2.0")


class TableCreate(BaseModel):
    name: str = "INARENA Table"


class JoinRequest(BaseModel):
    player_id: str = Field(min_length=1)
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


@app.post("/api/v1/tables/{table_id}/join")
async def api_join(table_id: str, payload: JoinRequest) -> dict[str, Any]:
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


@app.post("/api/v1/tables/{table_id}/pot")
async def api_set_pot(table_id: str, payload: PotRequest) -> dict[str, Any]:
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
    try:
        state = complete_hand(table_id, payload.payouts)
        await manager.broadcast_state(table_id, "hand_completed")
        return state
    except Exception as exc:
        raise _http_error(exc) from exc


@app.post("/api/v1/sessions", status_code=201)
def api_create_session(payload: SessionCreate) -> dict[str, Any]:
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
