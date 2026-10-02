from __future__ import annotations

import asyncio
import os

import pytest

from app.realtime_coordination import RedisRealtimeCoordinator


REDIS_URL = os.getenv("INARENA_TEST_REDIS_URL")


def test_unconfigured_coordinator_is_noop(monkeypatch):
    monkeypatch.delenv("INARENA_REDIS_URL", raising=False)
    coordinator = RedisRealtimeCoordinator()
    assert coordinator.configured is False
    assert coordinator.diagnostics()["connected"] is False

    async def run():
        received = []

        async def handler(event):
            received.append(event)

        await coordinator.start(handler)
        await coordinator.publish(
            {
                "seq": 1,
                "table_id": "table",
                "event_type": "test",
                "payload": {},
            }
        )
        await coordinator.stop()
        assert received == []

    asyncio.run(run())


@pytest.mark.skipif(
    not REDIS_URL,
    reason="INARENA_TEST_REDIS_URL is not configured",
)
def test_redis_fans_out_to_other_instance_without_self_duplicate(monkeypatch):
    monkeypatch.setenv("INARENA_REDIS_URL", REDIS_URL)

    async def run():
        first = RedisRealtimeCoordinator()
        second = RedisRealtimeCoordinator()
        first_received = []
        second_received = []
        delivered = asyncio.Event()

        async def first_handler(event):
            first_received.append(event)

        async def second_handler(event):
            second_received.append(event)
            delivered.set()

        await first.start(first_handler)
        await second.start(second_handler)
        try:
            event = {
                "seq": 42,
                "table_id": "table-1",
                "event_type": "player_action",
                "payload": {"status": "playing"},
            }
            await first.publish(event)
            await asyncio.wait_for(delivered.wait(), timeout=2.0)

            assert first_received == []
            assert second_received == [event]
            assert first.diagnostics()["connected"] is True
            assert second.diagnostics()["connected"] is True
        finally:
            await first.stop()
            await second.stop()

    asyncio.run(run())
