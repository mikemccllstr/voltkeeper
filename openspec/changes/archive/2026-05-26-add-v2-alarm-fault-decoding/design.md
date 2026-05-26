## Context

V1 alarm/fault decoding lives in `_v1_alarm_tables.py` plus `V1Base._fill_alarms`. It reads the alarm/fault region of `BASE_REAL_DATA` (register 10), bit-decodes 4 alarm words and up to 7 fault words, and emits `alarm.<name>` / `fault.<name>` keys for set bits. The tables come from APK `ConnectConstants` and `ConnConstantsV2.lowPower*` arrays — V1's parsing path branches by `isLowPower`.

V2 has the same conceptual layout but the source data lives in a different place. Per `docs/source/protocol/modbus-registers.md`:
- **V2 BASE_REAL_DATA path is gone** — V2 devices don't read register 10. Faults are surfaced via `INV_BASE_INFO` (1100) and `APP_HOME_DATA` (100) and pack alarms via `PACK_MAIN_INFO` (6000) / `PACK_BMU_INFO` (7200).
- **Three V2 inverter table sets**:
  - `highPowerWarn/Fault` — inverter type 3 (3-phase, EP/AC300/AC500 class)
  - `microInvWarn/Fault` — micro-inverter (BalconySolar family)
  - `lowPowerWarn/Fault` — everything else (single-phase portables: AC2A, AC180, EL*, AC60, etc.)
- **Pack table sets**:
  - `packHighVoltAlarmNames` / `packHighVoltErrorNames` — high-voltage packs (B500K, BH500E etc.)
  - `bmuWarnNames` — BMU-level warnings

The selection logic in the APK uses `DeviceFunction.invType` (or model-derived classification). We use the simpler `invPowerType` byte at home-data offset 122 (already parsed into `invPowerType`) plus model registration — this is sufficient for the current device fleet.

## Goals / Non-Goals

**Goals:**
- Decode V2 alarms with the same UX as V1: `alarm.<human-readable-name> = True` for each set bit.
- Cover the three inverter table sets and the two pack table sets.
- Make the selection mechanism extensible so new device families slot in cleanly.

**Non-Goals:**
- Decoding ATS / AT1 / EPAD / DCDC / Charging-Pile alarm tables. Those are large and only relevant once those device classes have actual support.
- Live alarm history or rate-of-change. Single snapshot per poll is enough.
- Auto-clearing alarms or `handlingAlarm` API integration (cloud-only).

## Decisions

### 1. Selection mechanism: per-class attribute, with sensible defaults

**Decision:** Add a class attribute `V2Base.V2_ALARM_PROFILE: str = "low_power"` with possible values `"low_power" | "high_power" | "micro_inv"`. Pack tables are selected by a separate attribute on pack-bearing devices. Subclasses override.

```python
class AC2A(V2Base):
    V2_ALARM_PROFILE = "low_power"      # default, kept explicit

class EP600(V2Base):
    V2_ALARM_PROFILE = "high_power"
    PACK_ALARM_PROFILE = "high_volt"
```

**Rationale:** This mirrors how V1 subclasses pick a table set by overriding `ALARM_NAMES` / `FAULT_NAMES`. It keeps the dispatch logic out of `_fill_v2_alarms`. It doesn't try to be clever based on runtime data, which would couple alarm decoding to discovery state.

### 2. Where alarms come from in V2

**Decision:** Read the alarm/fault bytes from the `APP_HOME_DATA` block (100) — that's where `ProtocolParserV2.parseHomeData` extracts `alarmInfo` (warn words) and `faultInfo` (fault words) in the APK. Pack alarms come from the relevant offsets in `PACK_MAIN_INFO`.

```
                APK v3.0.9: V2 alarm sources
              ┌─────────────────────────────────┐
              │  APP_HOME_DATA (100)            │
              │   ├─ alarmInfo: bytes 52–59     │
              │   │             4 × 16-bit      │
              │   │             (regs 126–129)  │
              │   └─ faultInfo: bytes 66–77     │
              │                 6 × 16-bit      │
              │                 (regs 133–138)  │
              └─────────────────────────────────┘
              ┌─────────────────────────────────┐
              │  PACK_MAIN_INFO (6000)          │
              │   ├─ packSysErr  bytes 76–81    │
              │   │              3 × 16-bit     │
              │   │              → packHighVoltErrorNames │
              │   └─ packHighVoltAlarm bytes 82–83 │
              │                  1 × 16-bit    │
              │                  → packHighVoltAlarmNames │
              └─────────────────────────────────┘
```

**Rationale:** APK research shows `parseHomeData` (not `parseInvBaseInfo`) contains the alarm decoding. The byte offsets within APP_HOME_DATA come from `ProtocolParserV2.parseHomeData` in APK v3.0.9 and will be documented with `TODO(hardware): verify` markers in code since they are inferred from decompiled source.

### 3. Output shape: `alarm.<name>` / `fault.<name>` / `pack[N].alarm.<name>`

**Decision:** Top-level inverter alarms use bare `alarm.<name>` / `fault.<name>` keys (same as V1). Pack-specific alarms are namespaced under the sub-device prefix already used by `_parse_node_info` and TLV dispatch: `sub[N].alarm.<name>` / `sub[N].fault.<name>`.

**Rationale:** Consistency with existing V1 output and with the per-slave prefix convention already established in TLV/NODE_INFO parsing.

## Risks / Trade-offs

- **[Risk] Wrong byte offsets** within `INV_BASE_INFO` / `PACK_MAIN_INFO`. The APK is the source of truth but the docs/code I'm reading from is decompiled. → **Mitigation**: hardware verification on AC2A using `voltkeeper probe` while toggling a fault condition; cross-check against APK strings.xml display names.
- **[Risk] APK string-resource names contain typos** (`valtage`, `Multihost` etc.). V1 preserves them verbatim. → **Mitigation**: do the same for V2 — verbatim transcription with comments noting suspected typos. Users searching forums for vendor docs find the same names.
- **[Trade-off] No live alarm acknowledgment / clearing.** That's a cloud API call; we don't do cloud.
