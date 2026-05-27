## Why

Three protocol-layer correctness defects were identified during the APK v3.0.9 parity audit. Each is benign on the AC2A hardware that voltkeeper is regularly tested against, but each will surface as wrong data or silent misreads on EL400 or any V2 device with battery packs attached. Fixing them now keeps the trust contract — "voltkeeper reports what the device actually said" — intact before more users bring stacked or sleep-capable hardware online.

## What Changes

1. **EL400 register 2013 modeling.** `power_off` and `sleep_mode` are both modeled as `BoolField` on the same address. Reads collide: any non-zero value (`1=shutdown`, `4=sleep`) lights up both flags. Replace with a single `EnumField` (`SystemPowerOff: NORMAL=0, SHUTDOWN=1, POWER_DOWN_V1=2, POWER_DOWN_V2=3, SLEEP=4`). Keep the existing write override that maps `sleep_mode=on → 4`.

2. **Per-slave TLV bundling.** `V2Base.tlv_polling_commands` appends pack sections into a single TLV bundle but sends the whole bundle with `slave_addr=1`. The APK builds one TLV per slave. Split into one `TlvReadHoldingRegisters` per discovered slave address.

3. **`topology_discovered` precedence bug.** The expression `hasattr(self, "has_battery_packs") and self.has_battery_packs or self._topology_discovered` is `(hasattr and has_battery_packs) or _topology_discovered`, so any device declaring `has_battery_packs=True` is reported as discovered before NODE_INFO arrives. Combined with (2), stacked-pack devices skip per-pack polling silently. Fix: require an actual NODE_INFO response to flip `_topology_discovered`.

## Capabilities

### Modified Capabilities

- `v2-control-registers`: EL400 system-power register (2013) modeled as enum.
- `tlv-protocol`: TLV bundles are per-slave; topology-discovery flag reflects NODE_INFO arrival, not class declaration.

## Impact

- **Modified modules**: `src/voltkeeper/core/devices/el400.py`, `src/voltkeeper/core/devices/v2_base.py`, `src/voltkeeper/core/commands.py` (new `SystemPowerOff` enum).
- **Tests**: new unit tests for EL400 read-side disambiguation, multi-slave TLV bundling, and topology-discovered gating.
- **Risk**: low. EL400 hardware is `TODO(hardware): verify`; the read fix is observable only when someone tests a real EL400. Multi-slave fix is only exercised by stacked packs (none in test fleet today).
- **User-visible behavior**:
  - `voltkeeper status` on an EL400 in sleep mode now shows `system_power = sleep` instead of both `power_off=on` and `sleep_mode=on`.
  - Stacked-pack devices (EP600 + 2× B500K, etc.) will start reporting per-pack telemetry instead of duplicates of pack 1.
