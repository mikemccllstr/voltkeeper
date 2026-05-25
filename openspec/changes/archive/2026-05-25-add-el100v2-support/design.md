## Context

The EL100V2 is a V2-protocol portable power station (56V, category PORTABLE_POWER). Per the APK v3.0.9, it inherits through ELITE200_V2 → AC200PL → AC240 templates, with minProtocolVer overridden to 2007 (V2). Our codebase already has `V2Base` which provides V2 polling, TLV bundling, time-slicing, NODE_INFO discovery, and parse dispatch. The closest existing V2 portable device class is `AC60` (22 writable fields).

## Goals / Non-Goals

**Goals:**
- Full V2 telemetry read for EL100V2 (all 6 standard register blocks)
- Writable controls matching the APK-inferred capability set
- ctrl_event bit decoding for capability display
- BLE registry entry for auto-detection

**Non-Goals:**
- EL100V2-specific register addresses (no evidence of custom addresses in APK)
- Other EL-series or PR-series models (EL30V2, PR100V2, ELITE200_V2)
- V1 protocol fallback (EL100V2 is V2 only per APK)

## Decisions

### Decision 1: Inherit from V2Base, not V1Base

**Choice:** `El100V2(V2Base)`. The APK sets minProtocolVer to 2007 via the ELITE200_V2 template. All V2 features (TLV bundling, time-slicing, NODE_INFO discovery, parse dispatch) are inherited automatically.

**Alternative:** V1Base would require reimplementing all V2 polling, TLV, and dispatch — wrong for a V2 device.

### Decision 2: Model control struct on AC60 with grid/feed additions

**Choice:** Base the writable field set on AC60's control struct, adding grid control (2207), feed-in control (2208), charge limits (2211-2214), and feed limits (2215-2216) which the APK enables for EL100V2 via `maxGridInputCurrent = true` and the chain's `InvAdvancedParamsConfig`. Exclude `power_lifting` and `super_power` which are not in the EL100V2-specific DeviceFunction override chain.

**Alternative:** Copy AC2A's full 38-field control struct — too many fields, likely includes capabilities EL100V2 doesn't have (meter, smart plug, etc.).

### Decision 3: Use standard V2 CTRL_EVENT_BITS

**Choice:** Use `V2_CTRL_EVENT_BITS` from `v2_base.py` (same 11 bits as AC2A). The EL100V2 is a V2 portable power station; the bit definitions are standard across V2 devices.

**Alternative:** Define EL100V2-specific bits — unnecessary divergence; the APK doesn't define model-specific ctrl_event bits.

### Decision 4: DEFAULT_PACK_VOLTAGE_SCALE = 1 (÷10)

**Choice:** Use the V2Base default. EL100V2 is 56V nominal. With scale=1, raw register / 10 = volts (e.g., 560 / 10 = 56V).

**Alternative:** Scale=2 (÷100) like AC2A — only correct for 8S LiFePO4 architectures (~25.6V). EL100V2 is 56V nominal, so ÷10 is correct.

## Risks / Trade-offs

- **[Unconfirmed writable fields]** The writable field set is inferred from APK DeviceFunction flags, not verified against physical hardware. → Mitigation: Fields use standard V2 register addresses (documented in modbus-registers.md). If a field doesn't exist on the device, the Modbus write will return an exception, which our code handles gracefully. Fields can be removed if hardware testing reveals gaps.

- **[Different firmware versions]** EL100V2 may report a protocol version < 2007, which would still be V2 (≥ 2000) and work with V2Base. → Mitigation: No minimum version gating; V2Base accepts any protocolVer ≥ 2000.

## Open Questions

- What are the exact SOC range limits for EL100V2? (Using AC60's 0-100% range as default)
- Does EL100V2 support `dc_eco_mode` and `ac_eco_mode`? (Included based on APK chain capabilities; may need verification)
- What LED colors does EL100V2 support? (Included `led_color` field; enum values TBD)
