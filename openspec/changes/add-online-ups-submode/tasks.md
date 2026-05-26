## 1. APK investigation (V2 offset hunt)

- [x] 1.1 Read `bluetti-files/BLUETTI-v3.0.9.apk/jadx_out/sources/net/poweroak/bluetticloud/ui/connectv2/tools/ProtocolParserV2.java`, locate `parseInvBaseSettings(List<String> dataRes)`
- [x] 1.2 Identify the field that maps to the UPS sub-mode (Online vs Standby) — its byte offset within `INV_BASE_SETTINGS` (register 2000)
- [x] 1.3 Search `connectv2/bean/InvBaseSettings.java` for the field name and integer encoding
- [x] 1.4 Confirm the write path: search the APK for `WriteSingleRegister`-equivalent calls that set the UPS sub-mode; capture the address(es) and value mapping
- [x] 1.5 Document findings in `docs/source/protocol/modbus-registers.md` (V2 section, near WORKING_MODE)
- [x] 1.6 **Decision point**: if (1.2)–(1.4) yield a confident answer, proceed with V2 implementation in this change. If not, scope this change to V1-only and open a follow-up for V2.

## 2. V1 ups_mode field

- [x] 2.1 Add `UPS_MODE = 3035` constant import to V1 device files that will expose it
- [x] 2.2 Add `s.add_bool_field("ups_mode", UPS_MODE)` to `_build_control_struct` on AC300, AC500, AC200L, AC200PL, EP500, EP600
- [x] 2.3 Add `"ups_mode"` to each device's `WRITABLE_FIELD_NAMES`
- [x] 2.4 Verify `V1Base.build_setter_command` BoolField handling produces `WriteSingleRegister(3035, 1)` for "on" and `(3035, 0)` for "off"

## 3. V2 ups_mode field (conditional on 1.6)

- [x] 3.1 Add field declaration to `V2Base._build_control_struct` or applicable subclass `_build_control_struct` overrides
- [x] 3.2 Use the address/encoding identified in (1.2)
- [x] 3.3 Add `"ups_mode"` to the relevant `WRITABLE_FIELD_NAMES` lists
- [x] 3.4 If the V2 offset is part of `INV_BASE_SETTINGS` rather than a standalone register, ensure the read path through `control_struct.parse` decodes it

## 4. Tests

- [x] 4.1 Unit test: `voltkeeper write <ac300-addr> ups_mode on` produces `WriteSingleRegister(3035, 1)`
- [x] 4.2 Unit test: `voltkeeper write <ac300-addr> ups_mode off` produces `WriteSingleRegister(3035, 0)`
- [x] 4.3 Unit test: reading register 3035 raw value 1 yields `ups_mode = True` in parsed result
- [x] 4.4 Unit test (V2 path, if implemented): writes produce the correct register and encoding
- [x] 4.5 Unit test: `ups_mode` is NOT exposed on devices that don't support Online UPS (AC2A, EB3A, AC60, AC180, AORA Mini)

## 5. Documentation

- [x] 5.1 Update `docs/source/protocol/device-models.md` per-device feature matrix: add an "Online UPS" column
- [x] 5.2 Update `docs/source/user-guide/write.md` with a short "Online vs Standby UPS" section: explain that Online UPS reduces switchover to ~0–20ms but keeps the inverter active, increasing idle drain
- [x] 5.3 Note in the spec/user-guide that `ups_mode` only takes effect when `working_mode = STANDARD_UPS`

## 6. Verification

- [x] 6.1 Run `mise run check` — full suite green
- [ ] 6.2 Hardware verification on any V1 device available (AC300/AC500 ideal); confirm round-trip read/write of `ups_mode`
- [x] 6.3 If V2 implementation lands, mark `TODO(hardware)` on touched V2 device classes until verified
