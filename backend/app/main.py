from __future__ import annotations

from collections import defaultdict
from typing import Any

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field

from .db import ensure_schema
from .service import (
    ConflictError,
    NotFoundError,
    complete_hand,
    create_table,
    get_table_state,
    join_table,
    list_tables,
    stand,
    start_hand,
)

app = FastAPI(title="INARENA API", version="0.1.0")


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

    async def broadcast_state(self, table_id: str) -> None:
        state = get_table_state(table_id)
        dead: list[WebSocket] = []
        for socket in self.connections.get(table_id, set()):
            try:
                await socket.send_json({"type": "table_state", "data": state})
            except Exception:
                dead.append(socket)
        for socket in dead:
            self.disconnect(table_id, socket)


manager = ConnectionManager()


@app.on_event("startup")
def startup() -> None:
    ensure_schema()


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
        await manager.broadcast_state(table_id)
        return state
    except Exception as exc:
        raise _http_error(exc) from exc


@app.post("/api/v1/tables/{table_id}/stand")
async def api_stand(table_id: str, payload: StandRequest) -> dict[str, Any]:
    try:
        state = stand(table_id, payload.player_id)
        await manager.broadcast_state(table_id)
        return state
    except Exception as exc:
        raise _http_error(exc) from exc


@app.post("/api/v1/tables/{table_id}/start-hand")
async def api_start_hand(table_id: str, payload: StartHandRequest) -> dict[str, Any]:
    try:
        state = start_hand(table_id, payload.button_seat)
        await manager.broadcast_state(table_id)
        return state
    except Exception as exc:
        raise _http_error(exc) from exc


@app.post("/api/v1/tables/{table_id}/complete-hand")
async def api_complete_hand(table_id: str) -> dict[str, Any]:
    try:
        state = complete_hand(table_id)
        await manager.broadcast_state(table_id)
        return state
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
            {"type": "table_state", "data": get_table_state(table_id)}
        )
        while True:
            message = await websocket.receive_json()
            if message.get("type") == "sync":
                await websocket.send_json(
                    {"type": "table_state", "data": get_table_state(table_id)}
                )
    except WebSocketDisconnect:
        manager.disconnect(table_id, websocket)
