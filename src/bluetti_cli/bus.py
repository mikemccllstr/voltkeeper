# ABOUTME: EventBus — internal async pub/sub for parsed device data and commands.

import asyncio
from dataclasses import dataclass
import logging
from typing import Callable, List, Union

from .core.devices.bluetti_device import BluettiDevice
from .core.commands import DeviceCommand


@dataclass(frozen=True)
class ParserMessage:
    device: BluettiDevice
    parsed: dict


@dataclass(frozen=True)
class CommandMessage:
    device: BluettiDevice
    command: DeviceCommand


class EventBus:
    def __init__(self):
        self.parser_listeners: List[Callable] = []
        self.command_listeners: List[Callable] = []
        self.queue: asyncio.Queue = None

    def add_parser_listener(self, cb: Callable):
        self.parser_listeners.append(cb)

    def add_command_listener(self, cb: Callable):
        self.command_listeners.append(cb)

    async def put(self, msg: Union[ParserMessage, CommandMessage]):
        if not self.queue:
            self.queue = asyncio.Queue()
        await self.queue.put(msg)

    async def run(self):
        if not self.queue:
            self.queue = asyncio.Queue()

        try:
            while True:
                msg = await self.queue.get()
                logging.debug(f"bus queue size: {self.queue.qsize()}")
                if isinstance(msg, ParserMessage):
                    await asyncio.gather(*[pl(msg) for pl in self.parser_listeners])
                elif isinstance(msg, CommandMessage):
                    await asyncio.gather(*[cl(msg) for cl in self.command_listeners])
                self.queue.task_done()
        except asyncio.CancelledError:
            logging.info("EventBus shutting down...")
            raise
