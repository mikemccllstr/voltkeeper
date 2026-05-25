# ABOUTME: EP500 home power station — V1 protocol (minProtocolVer=1016 in Android).
# ABOUTME: TODO(EP500): verify writable fields and register layout against hardware.

from .v1_base import V1Base


class EP500(V1Base):
    """EP500 home power station. V1 protocol."""

    protocol_version = 1016

    def __init__(self, address: str, sn: str):
        super().__init__(address, "EP500", sn)
