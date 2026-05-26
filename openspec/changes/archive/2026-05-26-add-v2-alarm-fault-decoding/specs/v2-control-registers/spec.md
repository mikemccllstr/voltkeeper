## ADDED Requirements

### Requirement: V2 alarm and fault name tables ported from ConnConstantsV2

The system SHALL maintain table sets in `src/voltkeeper/core/devices/_v2_alarm_tables.py` mirroring the APK's `ConnConstantsV2` arrays:

- `LOW_POWER_WARN_NAMES` / `LOW_POWER_FAULT_NAMES` (single-phase portable inverters)
- `HIGH_POWER_WARN_NAMES` / `HIGH_POWER_FAULT_NAMES` (3-phase / home-power inverters)
- `MICRO_INV_WARN_NAMES` / `MICRO_INV_FAULT_NAMES` (BalconySolar / micro-inverter family)
- `PACK_HIGH_VOLT_ALARM_NAMES` / `PACK_HIGH_VOLT_ERROR_NAMES` (high-voltage battery packs)
- `BMU_WARN_NAMES` (BMU-level warnings)

Each table SHALL be a `dict[int, list[str | None]]` where the integer key is the 1-based word index and the list contains 16 entries (one per bit), with `None` for unused positions. Names SHALL be transcribed verbatim from APK string resources, preserving any spelling quirks.

#### Scenario: Module importable with all tables
- **WHEN** importing the alarm-tables module
- **THEN** all eight named tables are present as module-level constants
- **THEN** each table is a `dict[int, list[str | None]]`

### Requirement: V2Base selects alarm tables via per-class profile

`V2Base` SHALL expose `V2_ALARM_PROFILE: str = "low_power"` as a class attribute. Subclasses SHALL override this attribute to `"high_power"` for 3-phase devices (EP500, EP600, any future home-power class) or `"micro_inv"` for micro-inverter devices. The class attribute `PACK_ALARM_PROFILE: str | None = None` SHALL select a pack alarm table set, with `"high_volt"` enabling high-voltage pack alarm decoding.

#### Scenario: Default profile for portable power stations
- **WHEN** inspecting `AC2A.V2_ALARM_PROFILE`
- **THEN** the value is `"low_power"`

#### Scenario: High-power override
- **WHEN** inspecting `EP600.V2_ALARM_PROFILE`
- **THEN** the value is `"high_power"`

### Requirement: V2 alarm bits decoded into named keys

When `V2Base.parse()` processes an `APP_HOME_DATA` block (address 100), it SHALL call `_fill_v2_alarms(result, data)`. That method SHALL extract alarm-info (bytes 52–59, 4 × 16-bit words) and fault-info (bytes 66–77, 6 × 16-bit words) from the data payload and, for each set bit, add a key `alarm.<name>` or `fault.<name>` (value `True`) to the result dict using the table selected by `V2_ALARM_PROFILE`. Bits with `None` names SHALL be skipped silently.

#### Scenario: No alarms set
- **WHEN** parsing an `APP_HOME_DATA` block with all alarm/fault bytes zero
- **THEN** the result contains no keys starting with `alarm.` or `fault.`

#### Scenario: One alarm bit set
- **WHEN** parsing an `APP_HOME_DATA` block with alarm-word 1 bit 0 set, profile `"low_power"`
- **THEN** the result contains `alarm.<the name at low-power warn word 1 bit 0> = True`

#### Scenario: Profile selection affects output names
- **WHEN** identical input bytes are parsed on a `low_power` profile device vs a `high_power` profile device
- **THEN** the emitted alarm names differ, matching the respective table set

### Requirement: V2 pack alarm bits decoded with sub-device prefix

When pack alarm bytes are present in a parsed `PACK_MAIN_INFO` block (address 6000) on a device whose `PACK_ALARM_PROFILE` is set, the system SHALL emit `alarm.<name>` / `fault.<name>` keys. When the pack arrives via `_parse_node_info` with a non-zero slave address, the keys SHALL be prefixed with `sub[<slave_addr>].`.

#### Scenario: Pack alarm via direct read
- **WHEN** parsing `PACK_MAIN_INFO` on a device with `PACK_ALARM_PROFILE="high_volt"` and a set alarm bit
- **THEN** the result contains `alarm.<the corresponding pack alarm name> = True` (no `sub[...]` prefix)

#### Scenario: Pack alarm via NODE_INFO
- **WHEN** `_parse_node_info` returns a TLV item with `slave_addr=41` and `reg_addr=PACK_MAIN_INFO`, alarm bit set
- **THEN** the result contains `sub[41].alarm.<the corresponding pack alarm name> = True`
