# Protocol Reference

Findings from reverse-engineering the Bluetti Android APK (v3.0.9).

**Package:** `net.poweroak.bluetticloud`
**Version:** 3.0.9 (versionCode 1415)
**Decompiled with:** apktool 2.7.0, jadx 1.5.5

```{toctree}
---
hidden:
---
ble-communication
security
modbus-registers
device-models
encryption-details
polling-strategy
backend-services
firmware-updates
```

Static analysis of ~22,900 decompiled classes yielded the GATT service and
characteristic UUIDs, both BLE security protocols, complete Modbus register
maps for V1 and V2 devices, hardcoded encryption keys and ECDSA keypairs, and
the full backend API and firmware update flows. From these findings, voltkeeper
was built as a standalone Python CLI that speaks the same protocol — using only
observation and reimplementation. No code was copied from Bluetti's libraries.

## Automated Setup

The APK download and decompilation is automated via mise tasks:

```bash
mise install          # installs java + jadx
mise run prepare-all  # download and decompile everything
mise run cleanup      # remove bluetti-files/
```

## Key Facts

- ~23,800 decompiled classes from a single APK
- Two protocol generations: V1 (`protocolVer < 2000`) and V2 (`>= 2000`)
- 120 Bluetti device models across multiple product families (up from 115 in v3.0.8)
- BLE communication is Modbus RTU over GATT characteristics
- Two authentication schemes: legacy AES challenge-response and ECDH+ECDSA
- Encryption keys and ECDSA keypairs are hardcoded, identical across all installations
- Three cloud environments (dev, test, production) with full URLs embedded in the APK
- 20+ backend microservices
- TLV sub-protocol for multi-device data responses (new in v3.0.9)
- 2nd-generation IoT devices use separate modbus slave addresses for battery packs
