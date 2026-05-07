# ABOUTME: Shutdown watchdog — MQTT subscriber that watches battery SOC and triggers shutdown.

import asyncio
import logging
import subprocess
import time

from aiomqtt import Client, MqttError


class ShutdownWatch:
    """Watch battery SOC via MQTT and trigger a system shutdown.

    Latch behaviour: once SOC drops below *threshold*, the shutdown
    countdown starts and cannot be cancelled by SOC recovery.  Only
    a manual ``systemctl stop`` before the grace period expires can
    prevent it.
    """

    def __init__(self, threshold: int, grace: int):
        self.threshold = threshold
        self.grace = grace
        self._latched = False
        self._fire_at: float | None = None

    @property
    def latched(self) -> bool:
        return self._latched

    @property
    def fire_at(self) -> float | None:
        return self._fire_at

    @property
    def time_remaining(self) -> float:
        if self._fire_at is None:
            return 0.0
        return max(0.0, self._fire_at - time.monotonic())

    def handle_soc(self, soc: int) -> str | None:
        """Process an SOC reading.

        Returns a shutdown command string when it is time to fire,
        or ``None`` otherwise.
        """
        if soc < self.threshold and not self._latched:
            self._latched = True
            self._fire_at = time.monotonic() + self.grace
            logging.warning(
                "SOC %d%% below %d%% — shutdown in %ds "
                "(systemctl stop to abort)",
                soc, self.threshold, self.grace,
            )
        elif self._latched and soc >= self.threshold:
            remaining = max(0.0, self._fire_at - time.monotonic())
            logging.info(
                "SOC recovered to %d%% but shutdown already triggered — "
                "%.0fs remaining",
                soc, remaining,
            )

        if self._fire_at and time.monotonic() >= self._fire_at:
            return "sudo shutdown -h now"

        return None

    def execute_shutdown(self):
        """Run the shutdown command.  Logs result; does not raise."""
        logging.warning("Initiating system shutdown")
        try:
            subprocess.run(
                ["sudo", "shutdown", "-h", "now"], check=False, timeout=30,
            )
        except Exception as exc:
            logging.error("Shutdown command failed: %s", exc)


async def run_shutdown_listener(
    topic: str,
    broker: str,
    port: int,
    username: str | None,
    password: str | None,
    threshold: int,
    grace: int,
):
    """Connect to MQTT, subscribe to *topic*, and run the watch loop."""
    watch = ShutdownWatch(threshold, grace)

    while True:
        try:
            async with Client(
                hostname=broker, port=port,
                username=username, password=password,
            ) as client:
                await client.subscribe(topic)
                logging.info("Listening on %s (threshold %d%%)", topic, threshold)
                async for message in client.messages:
                    try:
                        soc = int(message.payload.decode().strip())
                    except (ValueError, UnicodeDecodeError):
                        logging.debug("Unparseable SOC: %r", message.payload)
                        continue

                    cmd = watch.handle_soc(soc)
                    if cmd:
                        watch.execute_shutdown()
                        return

        except MqttError as exc:
            logging.warning("MQTT connection lost: %s — reconnecting in 5s", exc)
            await asyncio.sleep(5)
