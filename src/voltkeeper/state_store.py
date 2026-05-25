# ABOUTME: StateStore — in-memory latest parsed state per device, updated via EventBus listener.

from __future__ import annotations

import time
from threading import Lock
from typing import Any

from .bus import EventBus, ParserMessage


class StateStore:
    def __init__(self, bus: EventBus):
        self._bus = bus
        self._states: dict[str, dict[str, Any]] = {}
        self._timestamps: dict[str, float] = {}
        self._lock = Lock()
        self._bus.add_parser_listener(self._on_parser_message)

    async def _on_parser_message(self, msg: ParserMessage) -> None:
        with self._lock:
            self._states[msg.device.address] = dict(msg.parsed)
            self._timestamps[msg.device.address] = time.time()

    def get(self, address: str) -> dict[str, Any]:
        with self._lock:
            return dict(self._states.get(address, {}))

    def get_timestamp(self, address: str) -> float | None:
        with self._lock:
            return self._timestamps.get(address)

    def get_all(self) -> dict[str, dict[str, Any]]:
        with self._lock:
            return {addr: dict(state) for addr, state in self._states.items()}

    def get_all_timestamps(self) -> dict[str, float]:
        with self._lock:
            return dict(self._timestamps)
