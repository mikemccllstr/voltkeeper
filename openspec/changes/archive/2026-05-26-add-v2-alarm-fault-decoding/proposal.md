## Why

V2 devices (every device family released after AC200M) account for the majority of supported hardware in voltkeeper but have no alarm or fault decoding. A user whose AC2A, EL400, EL100V2, or AC180 hits a real fault sees nothing useful in `voltkeeper status` — at best the raw `invWorkingStatus` byte (3/4/5 normal, 7 abnormal) hints that something is wrong, but nothing identifies which subsystem or which fault. The APK has the data: `ConnConstantsV2.java` defines `highPowerWarnNames` / `highPowerFaultNames`, `lowPowerWarnNames` / `lowPowerFaultNames`, `microInvWarnNames` / `microInvFaultNames`, plus pack-side tables `packHighVoltAlarmNames` / `packHighVoltErrorNames` / `bmuWarnNames`. We already have the analogous V1 plumbing (`_v1_alarm_tables.py`, `V1Base._fill_alarms`). This change brings V2 up to parity.

## What Changes

- **New shared table module** `src/voltkeeper/core/devices/_v2_alarm_tables.py` containing the four V2 name table sets (low/high/micro/pack), ported verbatim from `ConnConstantsV2.java`.
- **`V2Base._fill_v2_alarms()`** method that decodes alarm and fault bitmasks from the appropriate block, emitting `alarm.<name>` / `fault.<name>` keys analogous to V1's behavior.
- **Table selection** driven by the inverter power-type byte already parsed in `INV_BASE_INFO`: high-power for 3-phase inverter devices (EP500, EP600, AC300, AC500), micro-inv for the BalconySolar/MicroInv family, low-power for everything else.
- **Pack alarm decoding** in `_parse_node_info` and `pack_main_struct.parse` pathways uses the pack-specific tables when fields are present in the response.

## Capabilities

### Modified Capabilities

- `v2-control-registers`: alarm/fault decoding for V2 devices using ConnConstantsV2 name tables.

## Impact

- **New module**: `src/voltkeeper/core/devices/_v2_alarm_tables.py` (~200 lines, mostly string literals).
- **Modified module**: `src/voltkeeper/core/devices/v2_base.py` — adds `_fill_v2_alarms`, calls it from `parse()` after `home_struct`/`pack_main_struct` parsing.
- **No new fields on existing parsed structs** — alarm/fault keys are added to the result dict only when the corresponding bit is set, mirroring `V1Base._fill_alarms`.
- **Risk**: low. Alarm decoding is pure additive output. If the offset choices are wrong, the worst case is misnamed alarms or none at all — no functional degradation.
- **User-visible behavior**: `voltkeeper status` on a V2 device with active alarms now lists e.g. `alarm.Battery Pack Communication Abnormal = True`.
