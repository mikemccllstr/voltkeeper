# BLE Communication

This page covers the Bluetti device Bluetooth Low Energy (BLE) GATT service details, characteristic UUIDs, scan data patterns, and BLE advertising structure.
<!-- Extracted from FINDINGS.md §5 and §15.1 -->

## 5. Bluetooth (BLE) Communication

- BLE is used for local device pairing, provisioning, and control (when not on Wi-Fi)
- Encrypted BLE channel: `ConnectManager.bleEncryptedHandle` uses AES-CFB/NoPadding (`net.poweroak.lib_base.utils.AesExtKt`)
- Keys are negotiated per-session (not hardcoded)
- Device discovery by Bluetooth uses `/api/blusmartprod/device/basic/v1/findDeviceByBluetooth`

---

## Section 15 — BLE Protocol Reference for Developers

> **Target device:** AC2A (model code `"AC2A"`, number 20 in `DeviceModel` enum). The AC2A is an inverter-class device using protocol V2 (≥2000).

### 15.1 BLE GATT Details

| Item | UUID |
|------|------|
| Service | `0000ff00-0000-1000-8000-00805f9b34fb` |
| Notify/Read characteristic | `0000ff01-0000-1000-8000-00805f9b34fb` |
| Write characteristic | `0000ff02-0000-1000-8000-00805f9b34fb` |
| CCC descriptor | `00002902-0000-1000-8000-00805f9b34fb` |

**Scan filter:** Service UUID `0000ff00-...` is used as the BLE scan filter.

**Scan record identification (manufacturer-specific data):**
| Hex prefix | Meaning |
|-----------|---------|
| `424c5545545449` ("BLUETTI") | ESP32 device, non-encrypted |
| `424c5545545445` ("BLUETTE") | ESP32 encrypted |
| `424c5545545446` ("BLUETTF") | ESP32 encrypted variant |

**Write characteristic:**
- MTU: 247 bytes (BLE 4.2 max) for ESP32/encrypted devices
- Write without response: `writeCharacteristic()` or `writeCharacteristicSplit()` with `supportMaxLength=244`
