## 1. Source extraction from APK

- [x] 1.1 Open `bluetti-files/BLUETTI-v3.0.9.apk/jadx_out/sources/net/poweroak/bluetticloud/ui/connectv2/tools/ConnConstantsV2.java`; locate `lowPowerWarnNames`, `lowPowerFaultNames`, `highPowerWarnNames`, `highPowerFaultNames`, `microInvWarnNames`, `microInvFaultNames`, `packHighVoltAlarmNames`, `packHighVoltErrorNames`, `bmuWarnNames`
- [x] 1.2 Cross-reference each bit position against `apktool_out/res/values/strings.xml` to get the human-readable label
- [x] 1.3 Document each table's word count and per-bit assignment in module docstring

## 2. New module `_v2_alarm_tables.py`

- [x] 2.1 Create `src/voltkeeper/core/devices/_v2_alarm_tables.py` with ABOUTME headers and a docstring listing the APK source classes
- [x] 2.2 Define `LOW_POWER_WARN_NAMES`, `LOW_POWER_FAULT_NAMES` as `dict[int, list[str | None]]` (mirror existing V1 shape)
- [x] 2.3 Define `HIGH_POWER_WARN_NAMES`, `HIGH_POWER_FAULT_NAMES`
- [x] 2.4 Define `MICRO_INV_WARN_NAMES`, `MICRO_INV_FAULT_NAMES`
- [x] 2.5 Define `PACK_HIGH_VOLT_ALARM_NAMES`, `PACK_HIGH_VOLT_ERROR_NAMES`, `BMU_WARN_NAMES`
- [x] 2.6 Preserve APK typos verbatim (matches V1 convention); add `# typo: ...` comment next to each suspected typo

## 3. Profile-based selector in V2Base

- [x] 3.1 Add `V2_ALARM_PROFILE: str = "low_power"` class attribute to `V2Base`
- [x] 3.2 Add `PACK_ALARM_PROFILE: str | None = None` class attribute to `V2Base` (None = no pack alarms)
- [x] 3.3 Add `_V2_INV_TABLES: dict[str, tuple[dict, dict]]` mapping `"low_power"`/`"high_power"`/`"micro_inv"` to `(warn_names, fault_names)`
- [x] 3.4 Add `_V2_PACK_TABLES: dict[str, tuple[dict, dict]]` mapping `"high_volt"` to `(alarm_names, error_names)`

## 4. `_fill_v2_alarms()` implementation

- [x] 4.1 Implement `_fill_v2_alarms(result: dict, data: bytes)` on `V2Base`, called from `parse()` for `APP_HOME_DATA` address range
- [x] 4.2 Resolve warn/fault tables from `V2_ALARM_PROFILE`
- [x] 4.3 Decode warn words: for each 16-bit word at the configured byte offsets, walk bits 0–15, emit `alarm.<name>` for set bits where name is non-None
- [x] 4.4 Decode fault words similarly, emitting `fault.<name>`
- [x] 4.5 Document the byte offsets within APP_HOME_DATA (alarmInfo bytes 52–59, faultInfo bytes 66–77) in code comments referencing `ProtocolParserV2.parseHomeData`; mark `TODO(hardware): verify`
- [x] 4.6 Implement `_fill_v2_pack_alarms(result, data)` for pack alarm decoding from `PACK_MAIN_INFO` / `PACK_BMU_INFO` blocks
- [x] 4.7 Wire pack-alarm calls into both `_parse_node_info` (sub-device-prefixed) and `pack_main_struct.parse`-following hook

## 5. Per-device profile selection

- [x] 5.1 Subclasses keep `V2_ALARM_PROFILE = "low_power"` by default (no change needed for AC2A, AC60, AC180, EL10V2, EL30V2, EL100V2, EL400)
- [x] 5.2 Override `V2_ALARM_PROFILE = "high_power"` on EP500, EP600 (and any V2 high-power class added)
- [x] 5.3 Override `V2_ALARM_PROFILE = "micro_inv"` on any micro-inverter class (none today, leave hook for future)
- [x] 5.4 Override `PACK_ALARM_PROFILE = "high_volt"` on classes that report high-voltage packs (EP500, EP600)

## 6. Tests

- [x] 6.1 Unit test: synthetic INV_BASE_INFO with all-zero alarm words yields no `alarm.*` / `fault.*` keys
- [x] 6.2 Unit test: single bit set in warn word 1 yields exactly one `alarm.<expected name>` key
- [x] 6.3 Unit test: profile switch — same input bytes on a `high_power` device emit high-power names, on `low_power` emit low-power names
- [x] 6.4 Unit test: pack alarm prefixed with `sub[N].` when decoded via `_parse_node_info`
- [x] 6.5 Unit test: regression — V1 alarm decoding unchanged after V2 changes land

## 7. Documentation

- [x] 7.1 Update `docs/source/protocol/modbus-registers.md` to point to `_v2_alarm_tables.py` (similar to how V1 is referenced)
- [x] 7.2 Add a "Alarms and faults" section to `docs/source/user-guide/status.md` showing how alarm keys appear in CLI output
- [x] 7.3 Mark byte offsets as `TODO(hardware): verify` where they're inferred without ground truth

## 8. Verification

- [x] 8.1 Run `mise run check` — full suite green
- [x] 8.2 On AC2A: confirmed no spurious alarms under grid-on or battery-only (grid unplugged) operation
- [x] 8.3 AC2A raises no alarm when grid is unplugged (expected — portable device, battery is primary); alarmInfo/faultInfo byte offsets confirmed correct via probe. Pack alarm offsets remain unverified pending EP600/B500K hardware.
