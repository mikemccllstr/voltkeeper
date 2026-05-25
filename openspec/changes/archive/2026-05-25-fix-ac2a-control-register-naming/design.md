## Context

Our AC2A control register implementation was built from the Bluetti APK v3.0.9's register map (section 15.9 of modbus-registers.md) but used field names we invented rather than the names the app itself uses internally. Investigation of the decompiled APK sources reveals:

1. **`InvBaseSettings`** (base settings, register block 2000): The APK's `ProtocolParserV2.parseInvBaseSettings()` maps byte offsets to field names. Registers at 2022/2023 are `sysLowPower`/`sysHighPower` (system power thresholds), not battery ranges. Registers at 2075/2083 are `socHoldingLow`/`socHoldingHigh` (SOC holding limits).

2. **`InvAdvancedSettings`** (expert settings, register block 2200): The APK's `ProtocolParserV2.parseInvAdvSettings()` maps all the charge/grid/feed limit registers. These registers ARE parsed and read — they're real protocol registers.

3. **`InvAdvancedParamsConfig`**: This boolean-flag class controls which settings appear in the Expert Mode page of the app. For the AC2A model (which inherits from AC70 → AC60 templates in `DeviceConnUtil.getDeviceFunc()`), the following flags are `false`:
   - `maxGridChgPower` (2213), `maxGridInputCurrent` (2214)
   - `maxChargeVoltage` (2211), `maxGridChgCurrent` (2212)
   - `maxGridDsgPower` (2215), `maxGridDsgCurrent` (2216)
   - `invOutputVoltage` (2209)
   - `socHighLimited`, `socLowerLimit`

   These flags only control UI visibility in Expert Mode. The registers themselves are valid — the app reads them and a motivated user could write them via BLE. We keep them writable but document the app's stance.

4. **`system_timezone`** (register 2004): The APK does not parse this byte offset in `parseInvBaseSettings()`. The base info block (1100) might supply timezone data differently, or the app may not use timezone at all for this model.

## Goals / Non-Goals

**Goals:**
- Rename `battery_range_start` and `battery_range_end` to reflect their actual purpose (system power thresholds)
- Rename `soc_low` and `soc_high` to match the APK's `socHoldingLow`/`socHoldingHigh` naming
- Flag `system_timezone` as unverified in docs and code comments
- Update all documentation, tests, and fixtures to reflect the corrected names
- Apply renames to EL100V2 which shares these fields

**Non-Goals:**
- Removing any fields from the control struct or `WRITABLE_FIELD_NAMES` (they remain valid registers)
- Adding the `InvAdvancedParamsConfig` feature-flag concept to our codebase (it's APK UI logic, not our concern)
- Renaming any non-AC2A/non-EL100V2 fields
- Changing the device data schema or MQTT topic structure beyond field name changes

## Decisions

### Decision 1: Rename `battery_range_start`/`battery_range_end` → `sys_low_power`/`sys_high_power`

**Rationale**: The APK names these `sysLowPower` and `sysHighPower`. They are system power thresholds that control when the inverter activates/deactivates based on total system load — not battery SOC ranges. The current name `battery_range_*` is actively misleading to users who configure these expecting to set SOC charge limits.

**Alternatives considered**:
- `system_low_power` / `system_high_power`: More descriptive but verbose. The APK uses `sysLowPower`/`sysHighPower`, and `sys_` is a common prefix in our codebase.
- Keep as-is and document: Users would still be confused by the name suggesting battery behavior.

### Decision 2: Rename `soc_low`/`soc_high` → `soc_holding_low`/`soc_holding_high`

**Rationale**: The APK names these `socHoldingLow` and `socHoldingHigh`. The "holding" term is important — these control SOC thresholds for holding/discharging behavior, distinct from charge limit settings (`socHighLimited` in the APK). Using `soc_holding_*` distinguishes them from any future charge-limit fields.

**Alternatives considered**:
- `soc_low_threshold` / `soc_high_threshold`: Generic, loses the "holding" semantic.
- Keep `soc_low`/`soc_high`: Too vague and doesn't match APK terminology.

### Decision 3: Keep all register fields in WRITABLE_FIELD_NAMES but document APK UI stance

**Rationale**: The `InvAdvancedParamsConfig` flags control what the OFFICIAL APP shows in Expert Mode. Our tool (voltkeeper) is for power users who may want to write these registers directly. The registers ARE valid protocol registers — the app reads them, and the device accepts writes to them. Removing them from `WRITABLE_FIELD_NAMES` would be removing functionality that technically works.

Document in `modbus-registers.md` and `device-models.md` which fields the official app hides for AC2A.

### Decision 4: Flag `system_timezone` (2004) as unverified

**Rationale**: The APK does not parse byte offset 8–9 (register 2004) in `parseInvBaseSettings()`. It may be that register 2004 serves a different purpose, or the timezone is obtained through a different mechanism. We'll add a comment noting "APK does not parse this register" but keep it in the struct since removing it is a breaking change and we haven't confirmed it's invalid.

### Decision 5: Apply renames to EL100V2

**Rationale**: EL100V2 was built from the same template chain and shares these control fields. The same naming corrections apply. This is addressed in the EL100V2 design doc (decision 2: "Model control struct on AC60 with grid/feed additions").

## Risks / Trade-offs

| Risk | Mitigation |
|---|---|
| **Breaking MQTT/HA configs**: Users with Home Assistant automations referencing `battery_range_start`, etc. will break | Document the rename in release notes. MQTT topics will change to the new field names. |
| **Script breakage**: Anyone using `voltkeeper set battery_range_start=50` will break | Document migration in release notes with old→new mapping table. |
| **system_timezone may be wrong address**: If 2004 isn't actually timezone, we're reading/writing a register with incorrect meaning | Flag as unverified. If proven incorrect later, remove or rename. |
| **EL100V2 divergence**: If EL100V2 has different field names in APK than AC2A | We validated that the EL100V2 shares the same V2 register map template. No divergence expected. |

## Migration Plan

1. Rename fields in `ac2a.py` and `el100v2.py` control structs and `WRITABLE_FIELD_NAMES`
2. Update `mqtt_client.py` field configs with new names (MQTT topics change)
3. Update protocol docs with old→new name mapping table
4. Update user docs and man page
5. Update all test fixtures and assertions
6. Run full `mise run check` to verify
7. Document breaking changes in changelog/release notes

Rollback: Revert the commit. No data migration needed — only field name constants change.
