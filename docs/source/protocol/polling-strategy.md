# Polling Strategy (APK v3.0.9)

How the Bluetti Android APK schedules Modbus register reads against devices,
and how voltkeeper's strategy compares.

## APK Architecture

### Time-Sliced Polling via `TimerScene`

The APK does **not** poll all register blocks every cycle. It rotates through
`TimerScene` values on a fixed timer:

| Mode          | Interval |
| ------------- | -------- |
| BLE (local)   | 800 ms   |
| MQTT (remote) | 1000 ms  |

Each timer tick, `DeviceDataReader.readDeviceData()` dispatches to one of 43
scene-specific read methods based on `getTimerScene()`.

The default scene (home screen) is `TimerScene.DEFAULT`, which calls
`readDefault()`. Other scenes are used when the user navigates to specific pages
(settings, faults, upgrade).

### Default Scene: `readDefault()`

For devices with `supportModbusTLV == 1` (most V2 devices), the default poll
bundles multiple register addresses into a single TLV read request:

```
buildTLVReadTask([100, 2000, 2200])
  + PACK_ITEM_INFO      (if grid-off/EMS-parallel AND timerCounter % 3 == 0)
  + PANEL_BASE_INFO     (if discovered nodeInfo contains EPANEL)
  + WT_INFO             (if COMBOX scene == 2)
  + PAYGO (30001)       (if baseConfig.hasPayGo)
```

For devices without TLV, blocks are read individually in a coroutine with
100ms delays between reads.

### Other Scenes (Navigation-Driven)

| Scene                  | What Gets Polled                                                        |
| ---------------------- | ----------------------------------------------------------------------- |
| `HOME_INFO`            | Register 100 only (`addHomeDataTask()`)                                 |
| `BASE_SETTINGS`        | TLV-bundled: 2000 + 2200 (varies by category)                           |
| `BASE_SETTINGS_SINGLE` | V1: register 3000 / V2: 2000 then 2200 after 100ms                      |
| `HOME_FAULT`           | TLV-bundled: 100 + IOT_BASE + PACK_MAIN + PACK_ITEM + AT1_BASE (if AT1) |
| `INV_BASE_INFO`        | Register 1100                                                           |
| `PACK_MAIN_INFO_V2`    | Register 6000 per pack                                                  |
| `NODE_INFO`            | Write version to 21000, read TLV response                               |
| `DCDC_INFO`            | DCDC-specific registers                                                 |

### TLV Bundling

When `isSupportModbusTLV() == 1`, multiple register reads are bundled into one
Modbus request using TLV encoding. The device responds with TLV-encoded data
containing all requested blocks plus CRC per item.

```java
// DeviceDataReader.java line 548
ModbusTaskUtils.INSTANCE.buildTLVReadTask(mgr, [2000, 2200])
```

This reduces BLE round-trips from N to 1 for each poll cycle.

### NODE_INFO: Runtime Topology Discovery

NODE_INFO (register 21000) is **not** a simple read — it's a write-then-read:

1. **Check if binding is needed:** `isBindingNodeInfo()` returns `true` when
   `deviceFunc.getBindingNodeInfo()` (or `iotFunc.getBindingNodeInfo()`) is
   true and the device is not in parallel grid mode.

1. **Lazy initialization:** In `readDefault()`, if `isBindingNodeInfo()` is
   true and `nodeInfo` is null:

   ```java
   delay(100ms)
   readNodeInfo(version=0)   // writes version to register 21000
   nodeInfo = emptyPlaceholder  // prevents re-read
   ```

1. **Data arrives asynchronously** via BLE notify → `nodeInfoHandle()` →
   TLV-parsed into `DeviceNodeInfo` containing sub-device topology (packs,
   inverters, panels).

### How Capabilities Affect Polling

The APK uses **three layers** of capability resolution:

| Layer            | Source                                          | Example                                       |
| ---------------- | ----------------------------------------------- | --------------------------------------------- |
| Compile-time     | `DeviceConnUtil.getDeviceFunc(model, ver, ...)` | 100+ boolean flags per model                  |
| Runtime config   | `DeviceBaseConfigBean` (parsed from register 1) | `supportModbusTLV`, `hasPayGo`, `comboxScene` |
| Runtime topology | `DeviceNodeInfo` (from NODE_INFO TLV response)  | Which packs/panels/inverters exist            |

The `ctrl_event` register (124) is **not** used for polling decisions — it is
display-only, surfaced on the device home screen.

### `DeviceConnUtil.getDeviceFunc()`

A monolithic 1675-line function that maps `(deviceModel, protocolVer, iotProtVer, specs, isHighVolt)` to a `DeviceFunction` with ~135 boolean flags.
Key flags relevant to polling:

| Flag               | Effect                                                 |
| ------------------ | ------------------------------------------------------ |
| `bindingNodeInfo`  | Whether to discover topology via NODE_INFO             |
| `packInfoFromNode` | Whether pack data comes from node info vs. direct read |
| `batteryPack`      | Whether device has battery pack telemetry              |
| `dcdcSupport`      | Include DCDC registers in polling                      |
| `panelSupport`     | Include panel registers                                |
| `meterCtrl`        | Include meter registers                                |
| `smartPlug`        | Include smart plug registers                           |
| `hasSubDevices`    | Whether child devices exist                            |
| `gridInput`        | Whether grid telemetry block should be polled          |
| `pvInput`          | Whether PV telemetry block should be polled            |

## Comparison: voltkeeper vs. APK

After the polling strategy improvements:

```
                         voltkeeper              │  APK v3.0.9
─────────────────────────────────────────────────┼─────────────────────────
Polling model            Time-sliced: fast blocks │  Time-sliced: one
                         every cycle, slow every  │  TimerScene per tick
                         3rd cycle                │
                                                  │
Registers per cycle      1 TLV-bundled command    │  1 TLV-bundled command
                         (1 BLE round trip)       │  (1 BLE round trip)
                                                  │
NODE_INFO                Polled at connect time,  │  Write-then-read at
                         parsed for topology      │  runtime, parsed from
                                                  │  device TLV response
                                                  │
Battery packs            Discovered via           │  Discovered via
                         NODE_INFO topology       │  NODE_INFO topology
                                                  │
ctrl_event usage         Display + probe output   │  Display only
                                                  │
Capability lookup        Per-class                │  Monolithic
                         WRITABLE_FIELD_NAMES     │  getDeviceFunc()
                                                  │
TLV bundling             Build AND parse TLV      │  Build AND parse TLV
```

## TLV Read Request Encoding

The TLV-bundled read request format, matching the APK's
`ModbusTaskUtils.buildTLVReadTask()`:

```
00105208 <total_len/2:2B big-endian> <total_len:1B> 9C450101
  [00 <slave_addr:1B> <reg_addr:2B> <byte_count:2B>]...
<CRC16_MODBUS:2B>
```

Each section specifies a register address and the number of bytes to read
(= register count × 2). The device responds with TLV-encoded data
(magic `40 00 04`) containing all requested blocks.

## Time-Sliced Polling

Fast blocks (every cycle):

- `APP_HOME_DATA` (100)
- `INV_BASE_SETTINGS` (2000)
- `INV_ADVANCE_SETTINGS` (2200)
- `PACK_MAIN_INFO` / `NODE_INFO` (if discovered)

Slow blocks (every 3rd cycle, or forced after write):

- `INV_BASE_INFO` (1100)
- `INV_PV_INFO` (1200)
- `INV_GRID_INFO` (1300)
- `INV_LOAD_INFO` (1400)
- `INV_INV_INFO` (1500)

A write operation to any register forces the next poll to include all
blocks regardless of counter value.

## Probe `ctrl_event` Capabilities

When probing a V2 device, register 124 (ctrl_event) is decoded from
the `APP_HOME_DATA` sweep and emitted as a `capabilities` section
in the YAML output:

```yaml
capabilities:
  ctrl_event: 1799
  decoded:
    power_control: true
    ac_control: true
    dc_control: true
    inv_control: false
    grid_control: false
    pv_control: false
    feedback: false
    meter: false
    led: false
    eco: false
    super_power: false
```

## Source Files

All paths relative to `bluetti-files/BLUETTI-v3.0.9.apk/jadx_out/sources/`:

| File                                                                 | Role                                                 |
| -------------------------------------------------------------------- | ---------------------------------------------------- |
| `net/poweroak/bluetticloud/ui/connect/helper/DeviceDataReader.java`  | Poll orchestrator — builds task lists per TimerScene |
| `net/poweroak/bluetticloud/ui/connect/ConnectManager.java`           | Timer loop, BLE task queue, node info handling       |
| `net/poweroak/bluetticloud/ui/connect/DeviceConnUtil.java`           | Capability resolver — `getDeviceFunc()` lookup table |
| `net/poweroak/bluetticloud/ui/connect/TimerScene.java`               | 43 poll scene enum values                            |
| `net/poweroak/bluetticloud/ui/connect/bean/DeviceFunction.java`      | ~135 boolean capability flags per model              |
| `net/poweroak/bluetticloud/ui/connectv2/tools/ModbusTaskUtils.java`  | TLV task builder — `buildTLVReadTask()`              |
| `net/poweroak/bluetticloud/ui/connectv2/tools/ProtocolParserV2.java` | V2 response parser, `getReadRegLen()`                |
