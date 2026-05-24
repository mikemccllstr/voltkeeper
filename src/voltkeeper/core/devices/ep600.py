# ABOUTME: EP600 home power station — V2 protocol, high-voltage pack (÷10 default).
# ABOUTME: TODO(EP600): verify against hardware.

from .v2_base import V2Base


class EP600(V2Base):
    """EP600 home power station. V2 protocol, high-voltage pack."""

    def __init__(self, address: str, sn: str):
        super().__init__(address, "EP600", sn)
