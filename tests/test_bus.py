# ABOUTME: Unit tests for voltkeeper — see test class docstrings for specifics.

import asyncio

import pytest

from voltkeeper.bus import CommandMessage, EventBus, ParserMessage
from voltkeeper.core.commands import WriteSingleRegister


class TestEventBus:
    @pytest.mark.asyncio
    async def test_parser_message_dispatched(self, ac2a_device):
        bus = EventBus()
        received = []

        async def listener(msg: ParserMessage):
            received.append(msg)

        bus.add_parser_listener(listener)
        bus_task = asyncio.create_task(bus.run())
        await bus.put(ParserMessage(ac2a_device, {"test": 1}))
        await asyncio.sleep(0.05)
        bus_task.cancel()

        assert len(received) == 1
        assert received[0].device is ac2a_device
        assert received[0].parsed == {"test": 1}

    @pytest.mark.asyncio
    async def test_command_message_dispatched(self, ac2a_device):
        bus = EventBus()
        received = []

        async def listener(msg: CommandMessage):
            received.append(msg)

        cmd = WriteSingleRegister(2011, 1)
        bus.add_command_listener(listener)
        bus_task = asyncio.create_task(bus.run())
        await bus.put(CommandMessage(ac2a_device, cmd))
        await asyncio.sleep(0.05)
        bus_task.cancel()

        assert len(received) == 1
        assert received[0].device is ac2a_device
        assert received[0].command.address == 2011

    @pytest.mark.asyncio
    async def test_multiple_listeners(self, ac2a_device):
        bus = EventBus()
        results = []

        async def listener_a(msg: ParserMessage):
            results.append("a")

        async def listener_b(msg: ParserMessage):
            results.append("b")

        bus.add_parser_listener(listener_a)
        bus.add_parser_listener(listener_b)
        bus_task = asyncio.create_task(bus.run())
        await bus.put(ParserMessage(ac2a_device, {}))
        await asyncio.sleep(0.05)
        bus_task.cancel()

        assert sorted(results) == ["a", "b"]

    @pytest.mark.asyncio
    async def test_messages_put_before_run_are_not_lost(self, ac2a_device):
        """Messages enqueued before run() starts must not be dropped."""
        bus = EventBus()
        received = []

        async def listener(msg: ParserMessage):
            received.append(msg)

        bus.add_parser_listener(listener)
        # put() is called BEFORE run() — the queue must be the same object
        await bus.put(ParserMessage(ac2a_device, {"pre": True}))

        bus_task = asyncio.create_task(bus.run())
        await asyncio.sleep(0.1)
        bus_task.cancel()

        assert len(received) == 1
        assert received[0].parsed == {"pre": True}
