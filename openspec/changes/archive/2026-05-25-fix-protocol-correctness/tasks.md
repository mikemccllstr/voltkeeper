## 1. Shared SystemPowerOff enum

- [x] 1.1 Add `SystemPowerOff(Enum)` to `src/voltkeeper/core/commands.py` with members `NORMAL=0, SHUTDOWN=1, POWER_DOWN_V1=2, POWER_DOWN_V2=3, SLEEP=4`
- [x] 1.2 Unit test: each enum value round-trips through `int(SystemPowerOff(n)) == n`

## 2. EL400 register 2013 modeling

- [x] 2.1 Remove `power_off` BoolField and `sleep_mode` BoolField (same address 2013) from `EL400._build_control_struct`
- [x] 2.2 Add `system_power` EnumField at 2013 using `SystemPowerOff`
- [x] 2.3 Update `WRITABLE_FIELD_NAMES`: drop `power_off`, `sleep_mode`; add `system_power`
- [x] 2.4 Remove the `sleep_mode` branch from `EL400.build_setter_command` (no longer needed — enum value 4 maps directly)
- [x] 2.5 For backward compatibility of CLI muscle memory, leave a one-line note in `docs/source/user-guide/write.md` showing the new field name
- [x] 2.6 Unit test: reading register 2013 with raw value `4` yields `system_power = SLEEP`, not two true bools
- [x] 2.7 Unit test: `write system_power sleep` produces `WriteSingleRegister(2013, 4)`
- [x] 2.8 Unit test: `write system_power shutdown` produces `WriteSingleRegister(2013, 1)`

## 3. Per-slave TLV bundling

- [x] 3.1 Change `V2Base.tlv_polling_commands` return type to `list[TlvReadHoldingRegisters]`
- [x] 3.2 Build the main bundle (home + slow blocks + NODE_INFO) with `slave_addr=1`
- [x] 3.3 For each `pack_slave` in `_discovered_packs`, append a bundle containing just `(PACK_MAIN_INFO, 32)` with `slave_addr=pack_slave`
- [x] 3.4 Fallback when `_discovered_packs` is empty but `has_battery_packs` is true: single PACK_MAIN_INFO on `slave_addr=1` (current behavior)
- [x] 3.5 Unit test: AC2A produces exactly one bundle, all sections on slave 1
- [x] 3.6 Unit test: a device with `_discovered_packs = [41, 42]` produces three bundles with slave addresses [1, 41, 42]
- [x] 3.7 Audit `device_handler.py` callers to confirm they iterate the returned list correctly (they already iterate `polling_commands`, so the shape change should be a no-op for the call site)

## 4. topology_discovered precedence fix

- [x] 4.1 Rewrite `V2Base.topology_discovered` property to return `self._topology_discovered` only — drop the `has_battery_packs` short-circuit
- [x] 4.2 Verify `discover_topology()` is the only setter of `self._topology_discovered`
- [x] 4.3 Unit test: a device declaring `has_battery_packs=True` reports `topology_discovered=False` before any NODE_INFO read
- [x] 4.4 Unit test: after `discover_topology(<valid TLV bytes>)`, `topology_discovered=True`
- [x] 4.5 Unit test: NODE_INFO is included in `_tlv_sections` for `has_battery_packs=True` devices regardless of `_topology_discovered`

## 5. Verification

- [x] 5.1 Run `mise run check` — lint + typecheck + tests all green
- [ ] 5.2 Hardware verification on AC2A: `voltkeeper status` output unchanged (no regression on the only tested device) — deferred to in-environment hardware testing; AC2A is not touched by this change so the call-site shape (single TLV bundle, slave 1) is unchanged.
- [x] 5.3 Mark `TODO(hardware)` on EL400 file with note that the new `system_power` enum is unverified — comment added next to the EnumField in `el400.py`
