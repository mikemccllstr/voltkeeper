# ABOUTME: Shared CLI helpers — event loop management, device resolution, daemon URL handling.

import asyncio
import sys

import click

from voltkeeper.bluetooth import ScanResult, build_device
from voltkeeper.config import ConfigError, load_config

SERVICE_UUID = "0000ff00-0000-1000-8000-00805f9b34fb"


def _close_loop(loop: asyncio.AbstractEventLoop) -> None:
    """Cancel pending tasks and cleanly close an event loop."""
    try:
        tasks = asyncio.all_tasks(loop)
        for task in tasks:
            task.cancel()
        if tasks:
            loop.run_until_complete(asyncio.gather(*tasks, return_exceptions=True))
    finally:
        loop.close()


def _device_from_scan(sr: ScanResult):
    """Build a device from a scan result, with a friendly error when the
    device advertises without its model prefix (e.g. when connected to
    the Bluetti app).
    """
    try:
        return build_device(sr.address, sr.name)
    except ValueError:
        click.secho(
            f"\nDevice at {sr.address} is advertising without a recognized "
            f"model name (received: {sr.name!r}).\n"
            "This happens when the device is already connected to the Bluetti app.\n"
            "Disconnect it from the app and try again.",
            fg="red",
        )
        sys.exit(1)


# ── Daemon-mode helpers ──


def _resolve_daemon_url(raw: str) -> str:
    raw = raw.strip()
    if raw.startswith("http://") or raw.startswith("https://"):
        return raw.rstrip("/")
    return f"http://{raw.rstrip('/')}:8080"


def _discover_api_key() -> str | None:
    try:
        config = load_config()
        return config.server.api_key
    except ConfigError:
        return None
