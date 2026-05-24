# ABOUTME: AC200PL variant of AC200L — V1 protocol (minProtocolVer=1022 in Android).
# ABOUTME: NOTE(divergence): Unit 10 plan lists AC200PL as V2Base, but the Android
# ABOUTME:   DeviceConnUtil.java sets minProtocolVer=1022 (<2000), which is V1.
# ABOUTME: NOTE(divergence): Unit 10 plan lists AC200PL as standalone; here it
# ABOUTME:   inherits from AC200L because the Android source shows they share
# ABOUTME:   identical writable controls (same DeviceFunction flags).
# ABOUTME: TODO(AC200PL): verify against hardware.

from .ac200l import AC200L


class AC200PL(AC200L):
    """AC200PL portable — V1 protocol. Variant of AC200L."""

    def __init__(self, address: str, sn: str):
        super().__init__(address, sn)
        self.type = "AC200PL"
