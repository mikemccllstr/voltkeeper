# ABOUTME: mDNS service advertiser for voltkeeperd using python-zeroconf.
# ABOUTME: Advertises voltkeeper-{hostname}._http._tcp.local. on the LAN.

from __future__ import annotations

import socket

from zeroconf import ServiceInfo, Zeroconf


class MdnsAdvertiser:
    def __init__(self, host: str, port: int) -> None:
        hostname = socket.gethostname()
        self.service_name = f"voltkeeper-{hostname}._http._tcp.local."
        self._host = host
        self._port = port
        self._zc: Zeroconf | None = None
        self._info: ServiceInfo | None = None

    def start(self) -> None:
        self._zc = Zeroconf()
        self._info = ServiceInfo(
            "_http._tcp.local.",
            self.service_name,
            addresses=[socket.inet_aton(self._host)],
            port=self._port,
            properties={},
        )
        self._zc.register_service(self._info)

    def stop(self) -> None:
        if self._zc is None or self._info is None:
            return
        self._zc.unregister_service(self._info)
        self._zc.close()
        self._zc = None
        self._info = None
