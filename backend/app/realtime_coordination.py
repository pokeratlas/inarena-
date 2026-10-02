from __future__ import annotations

import asyncio
import json
import os
import uuid
from collections.abc import Awaitable, Callable
from typing import Any


RemoteEventHandler = Callable[[dict[str, Any]], Awaitable[None]]


class RedisRealtimeCoordinator:
    CHANNEL = "inarena:realtime:v1"

    def __init__(self) -> None:
        self.url = (os.getenv("INARENA_REDIS_URL") or "").strip()
        self.instance_id = uuid.uuid4().hex
        self._client = None
        self._pubsub = None
        self._listener_task: asyncio.Task | None = None
        self._handler: RemoteEventHandler | None = None
        self.connected = False
        self.last_error: str | None = None

    @property
    def configured(self) -> bool:
        return bool(self.url)

    async def start(self, handler: RemoteEventHandler) -> None:
        self._handler = handler
        if not self.configured or self.connected:
            return
        try:
            import redis.asyncio as redis
        except ImportError as exc:
            self.last_error = "redis runtime dependency is not installed"
            raise RuntimeError(self.last_error) from exc

        try:
            self._client = redis.from_url(
                self.url,
                encoding="utf-8",
                decode_responses=True,
            )
            await self._client.ping()
            self._pubsub = self._client.pubsub(
                ignore_subscribe_messages=True
            )
            await self._pubsub.subscribe(self.CHANNEL)
            self.connected = True
            self.last_error = None
            self._listener_task = asyncio.create_task(
                self._listen(),
                name="inarena-redis-realtime-listener",
            )
        except Exception as exc:
            self.connected = False
            self.last_error = str(exc)
            await self.stop()
            raise

    async def stop(self) -> None:
        task = self._listener_task
        self._listener_task = None
        if task is not None:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

        if self._pubsub is not None:
            try:
                await self._pubsub.aclose()
            finally:
                self._pubsub = None

        if self._client is not None:
            try:
                await self._client.aclose()
            finally:
                self._client = None

        self.connected = False

    async def publish(self, event: dict[str, Any]) -> None:
        if not self.connected or self._client is None:
            return
        envelope = {
            "source_instance": self.instance_id,
            "event": event,
        }
        try:
            await self._client.publish(
                self.CHANNEL,
                json.dumps(envelope, separators=(",", ":")),
            )
        except Exception as exc:
            self.connected = False
            self.last_error = str(exc)

    async def _listen(self) -> None:
        if self._pubsub is None:
            return
        try:
            async for message in self._pubsub.listen():
                if message.get("type") != "message":
                    continue
                try:
                    envelope = json.loads(message["data"])
                    if envelope.get("source_instance") == self.instance_id:
                        continue
                    event = envelope.get("event")
                    if not isinstance(event, dict):
                        continue
                    if self._handler is not None:
                        await self._handler(event)
                except asyncio.CancelledError:
                    raise
                except Exception as exc:
                    self.last_error = str(exc)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            self.connected = False
            self.last_error = str(exc)

    def diagnostics(self) -> dict[str, Any]:
        return {
            "configured": self.configured,
            "connected": self.connected,
            "instance_id": self.instance_id,
            "last_error": self.last_error,
        }
