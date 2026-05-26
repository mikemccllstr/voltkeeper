## Why

The Bluetti app advertises "Online UPS" as a distinct UPS strategy with sub-20ms switchover (0 ms on Apex 300 dedicated outlets, 15 ms on Elite 400, 10 ms on Elite 10/30 V2). Looking at the protocol, this isn't a new `WORKING_MODE` value — it's a sub-toggle within `STANDARD_UPS` that selects Online (continuous inversion) vs Standby (transfer-on-grid-loss). The V1 register is `UPS_MODE` at address 3035 (`Online=1, Standby=0`). The V2 equivalent lives in `INV_BASE_SETTINGS` (2000) and is set via the same `WORKING_MODE` flow but with an additional field that the APK parses in `ProtocolParserV2.parseInvBaseSettings`. voltkeeper currently exposes neither, so a user cannot select Online UPS at all.

## What Changes

- **V1 path:** add `ups_mode` as a writable `BoolField` (`Online=1, Standby=0`) at register 3035 on V1 devices that support it (the docs already list it in `v1-control-registers`, but no device class exposes it). Update `V1Base` and applicable V1 device classes (`AC300`, `AC500`, `AC200L`, `AC200PL`, `EP500`, `EP600`).
- **V2 path investigation:** decode `parseInvBaseSettings` in `ProtocolParserV2.java` to identify the byte offset for the UPS sub-mode field. Add a writable field on V2 device classes whose `DeviceFunction.hasOnlineUPS` is true (EL10V2, EL30V2, EL100V2, EL400 per blog).
- **CLI documentation:** brief section in `docs/source/user-guide/write.md` explaining when to use Standard UPS vs Online UPS and the safety implications (Online UPS keeps the inverter running continuously, draining battery faster).

## Capabilities

### Modified Capabilities

- `v1-control-registers`: `ups_mode` Online/Standby toggle exposed on V1 device classes.
- `working-mode`: documented relationship between `working_mode` (strategy) and `ups_mode` (sub-mode of Standard UPS).

### Added Capabilities

- New capability **`online-ups`** describing the Online UPS sub-mode semantics and the read/write surface on both protocols.

## Impact

- **Modified modules**: `src/voltkeeper/core/devices/v1_base.py` (writable field plumbing), most V1 device classes (`ac300.py`, `ac500.py`, `ac200l.py`, `ac200pl.py`, `ep500.py`, `ep600.py`) to add `ups_mode` to `_build_control_struct` and `WRITABLE_FIELD_NAMES`.
- **Possibly modified modules**: V2 device classes if the V2 sub-mode field is identified during implementation. If the V2 offset cannot be confidently identified from the APK, the V2 portion is split into a follow-up change rather than guessing.
- **Risk**: medium. Online UPS keeps the inverter active 100% of the time — a user who flips this without understanding the trade-off may complain about faster battery drain or fan noise. Mitigation: clear docs and don't default the value.
