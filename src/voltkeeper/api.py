# ABOUTME: HTTP API server — aiohttp Application with REST endpoints, WebSocket, auth/ACL middleware.
# ABOUTME: Serves device state, accepts commands, pushes real-time updates via WebSocket.

from __future__ import annotations

import ipaddress
import json
import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from aiohttp import web

from .bus import CommandMessage, EventBus
from .config import Config
from .core.commands import WriteSingleRegister
from .device_manager import DeviceManager
from .state_store import StateStore

logger = logging.getLogger(__name__)

CONFIG_KEY: Any = web.AppKey("config", dict)
BUS_KEY: Any = web.AppKey("bus", EventBus)
STORE_KEY: Any = web.AppKey("store", StateStore)
DEVICE_MANAGER_KEY: Any = web.AppKey("device_manager", DeviceManager)


def create_app(config: Config, bus: EventBus, store: StateStore, device_manager: DeviceManager) -> web.Application:
    app = web.Application(middlewares=[_acl_middleware, _auth_middleware])
    app[CONFIG_KEY] = config
    app[BUS_KEY] = bus
    app[STORE_KEY] = store
    app[DEVICE_MANAGER_KEY] = device_manager

    app.router.add_get("/api/devices", _handle_devices)
    app.router.add_get("/api/device/{address}", _handle_device)
    app.router.add_post("/api/device/{address}/command", _handle_command)
    app.router.add_get("/ws", _handle_websocket)
    app.router.add_get("/", _handle_index)

    return app


# ── Middleware ───────────────────────────────────────────────────────────


@web.middleware
async def _acl_middleware(request: web.Request, handler) -> web.StreamResponse:
    config: Config = request.app[CONFIG_KEY]
    if not config.server.allowed_networks:
        return await handler(request)

    remote = request.remote
    if remote is None:
        return await handler(request)

    client_ip = ipaddress.ip_address(remote)

    for cidr in config.server.allowed_networks:
        net = ipaddress.ip_network(cidr, strict=False)
        if client_ip in net:
            return await handler(request)

    logger.warning(f"ACL denied {request.remote} for {request.path}")
    return web.json_response({"error": "Forbidden"}, status=403)


@web.middleware
async def _auth_middleware(request: web.Request, handler) -> web.StreamResponse:
    if request.path in ("/", "/ws"):
        return await handler(request)

    config: Config = request.app[CONFIG_KEY]
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        token = auth[7:]
    else:
        token = auth

    if token != config.server.api_key:
        return web.json_response({"error": "Unauthorized"}, status=401)

    return await handler(request)


# ── REST Handlers ────────────────────────────────────────────────────────


async def _handle_devices(request: web.Request) -> web.Response:
    store: StateStore = request.app[STORE_KEY]
    device_manager: DeviceManager = request.app[DEVICE_MANAGER_KEY]

    devices = []
    timestamps = store.get_all_timestamps()
    for ds in device_manager.get_statuses():
        state = store.get(ds.address)
        summary = _summarize_state(state)
        last_heard = _format_last_heard(timestamps.get(ds.address))
        devices.append(
            {
                "address": ds.address,
                "name": ds.name,
                "type": ds.device_type,
                "status": ds.status,
                "encrypted": ds.encrypted,
                "sn": ds.sn,
                "summary": summary,
                "last_heard": last_heard,
            }
        )

    return web.json_response(_to_serializable(devices))


async def _handle_device(request: web.Request) -> web.Response:
    address = request.match_info["address"].upper()
    store: StateStore = request.app[STORE_KEY]
    device_manager: DeviceManager = request.app[DEVICE_MANAGER_KEY]

    ds = device_manager.get_status(address)
    if ds is None:
        return web.json_response({"error": "Device not found"}, status=404)

    state = store.get(address)
    ts = store.get_timestamp(address)
    result: dict = {
        "address": ds.address,
        "name": ds.name,
        "type": ds.device_type,
        "status": ds.status,
        "_status": ds.status,
        "last_heard": _format_last_heard(ts),
    }

    if state:
        result.update(state)
    else:
        result["_status"] = ds.status

    return web.json_response(_to_serializable(result))


async def _handle_command(request: web.Request) -> web.Response:
    address = request.match_info["address"].upper()
    bus: EventBus = request.app[BUS_KEY]
    device_manager: DeviceManager = request.app[DEVICE_MANAGER_KEY]

    ds = device_manager.get_status(address)
    if ds is None:
        return web.json_response({"error": "Device not found"}, status=404)

    if ds.status != "online":
        return web.json_response({"error": f"Device is {ds.status}, cannot send command"}, status=503)

    try:
        body = await request.json()
    except json.JSONDecodeError:
        return web.json_response({"error": "Invalid JSON body"}, status=400)

    field = body.get("field")
    value = body.get("value")
    if not field or value is None:
        return web.json_response({"error": "Missing 'field' or 'value' in request body"}, status=400)

    device = device_manager.get_device(address)
    if device is None or not device.has_field_setter(field):
        return web.json_response({"error": f"Device does not support writing field '{field}'"}, status=400)

    try:
        command = device.build_setter_command(field, value)
    except (ValueError, TypeError) as e:
        return web.json_response({"error": str(e)}, status=400)

    if not isinstance(command, WriteSingleRegister):
        command = WriteSingleRegister(command.address, command.value)

    await bus.put(CommandMessage(device, command))
    return web.json_response({"accepted": True})


# ── WebSocket Handler ────────────────────────────────────────────────────


async def _handle_websocket(request: web.Request) -> web.WebSocketResponse:
    store: StateStore = request.app[STORE_KEY]
    device_manager: DeviceManager = request.app[DEVICE_MANAGER_KEY]
    bus: EventBus = request.app[BUS_KEY]

    ws = web.WebSocketResponse()
    await ws.prepare(request)

    for ds in device_manager.get_statuses():
        state = store.get(ds.address)
        await ws.send_json(
            _to_serializable(
                {
                    "type": "device_status",
                    "device": ds.address,
                    "status": ds.status,
                    "name": ds.name,
                    "device_type": ds.device_type,
                }
            )
        )
        if state:
            await ws.send_json(_to_serializable({"type": "state_update", "device": ds.address, "state": state}))

    async def on_parser_message(msg):
        if ws.closed:
            return
        try:
            payload = {"type": "state_update", "device": msg.device.address, "state": msg.parsed}
            await ws.send_json(_to_serializable(payload))
        except Exception:
            pass

    bus.add_parser_listener(on_parser_message)

    try:
        async for _msg in ws:
            pass
    finally:
        pass
    return ws


# ── Index Handler ────────────────────────────────────────────────────────


async def _handle_index(request: web.Request) -> web.StreamResponse:
    return web.FileResponse(_webui_path())


def _webui_path() -> str:
    from pathlib import Path

    candidate = Path(__file__).parent / "webui" / "index.html"
    if candidate.exists():
        return str(candidate)
    return str(Path(__file__).parent / "index.html")


# ── Helpers ──────────────────────────────────────────────────────────────


def _to_serializable(obj: Any) -> Any:
    if isinstance(obj, Decimal):
        return float(obj)
    if isinstance(obj, dict):
        return {k: _to_serializable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_to_serializable(v) for v in obj]
    return obj


def _format_last_heard(ts: float | None) -> str | None:
    if ts is None:
        return None
    return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()


def _summarize_state(state: dict) -> dict:
    summary: dict = {}
    if "packTotalSoc" in state:
        summary["soc"] = state["packTotalSoc"]
    if "packTotalVoltage" in state:
        summary["voltage"] = state["packTotalVoltage"]
    if "acOutputPower" in state:
        summary["ac_output_power"] = state["acOutputPower"]
    if "dcOutputPower" in state:
        summary["dc_output_power"] = state["dcOutputPower"]
    if "packTotalCurrent" in state:
        summary["current"] = state["packTotalCurrent"]
    return summary
