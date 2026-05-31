## Context

The EL100V2 device model was derived from the APK v3.0.9 `ELITE200_V2` template chain (ELITE200_V2 → AC200PL → AC240). The model defines its `control_commands` as four separate Modbus reads:

```
ReadHoldingRegisters(2000, 24)  — registers 2000–2023
ReadHoldingRegisters(2060, 27)  — registers 2060–2086
ReadHoldingRegisters(2200, 18)  — registers 2200–2217
ReadHoldingRegisters(3035, 1)   — UPS mode (V1 register, used by V2 per APK)
```

A hardware verification run (EL100V2, FW SW#3, 2026-05-30) revealed:
- `Read(2060, 27)` — **timeout** after 5 retries (no response at all)
- `Read(3035, 1)` — **Modbus exception 3** (illegal)

Analysis of the APK source (`DeviceDataReader.java:794`, `ProtocolParserV2.getReadRegLen`) shows the Bluetti app reads base settings as a **single contiguous read** starting at 2000 with a count of 85–96 registers (protocol-version dependent), covering 2000–2084+. It never splits the range. The APK also does not read register 3035 for V2 devices — `DeviceSettingsWorkingModeActivityV2` hardcodes the UPS display to "Backup" in the V2 code path.

The AC2A device uses the same split-read pattern and passes verification, suggesting the EL100V2 Modbus implementation specifically rejects reads starting mid-block at 2060.

## Goals / Non-Goals

**Goals:**
- Fix EL100V2 `control_commands` to align with APK's single contiguous base settings read
- Remove unreachable `ups_mode` field from EL100V2 (not read by APK for V2 devices, hardware returns exception)
- Ensure existing AC2A behavior is unaffected

**Non-Goals:**
- Change other unverified EL devices (EL10V2, EL30V2, EL400) — they retain the split-read pattern until hardware is available
- Change AC2A's control_commands (works correctly as-is)
- Add protocol-version-dependent read counts (we don't parse runtime protocol version)
- Fix tier 3 restore failures (likely a separate timing/reliability issue on EL100V2)

## Decisions

### Decision 1: Merge base settings into single `Read(2000, 87)`

**Choice**: Replace `Read(2000, 24)` + `Read(2060, 27)` with `Read(2000, 87)` covering registers 2000–2086.

**Why 87?**: 87 registers (2000–2086 inclusive) matches the existing `writable_ranges` upper bound `range(2000, 2087)` that was already declared. The highest field address is `soc_holding_high` at 2083; 87 registers comfortably cover all fields. The APK uses 85–96 depending on protocol version; 87 is within that range.

**Alternative considered**: Use the exact APK count for protocol version ≥ 2015 (85 registers). Rejected: we don't have a reliable protocol version mapping; 85 would only reach 2084 and might be insufficient for future fields; 87 is a safe superset.

### Decision 2: Remove `ups_mode` from EL100V2 entirely

**Choice**: Remove the `ups_mode` BoolField (register 3035) from `_build_control_struct()`, `WRITABLE_FIELD_NAMES`, and `control_commands`. Remove `V1_UPS_MODE` import.

**Rationale**:
- Hardware: `Read(3035, 1)` returns Modbus exception 3 (illegal)
- APK: V2 code path never reads 3035; hardcodes display to "Backup"
- The field was annotated `TODO(hardware): verify` — verification failed

**Alternative considered**: Keep as write-only (still writable, not in control_commands, skip verification). Rejected: a field that can be set but never read is misleading to users; the APK renders it as dead UI for V2 devices.

### Decision 3: Override `writable_ranges` in EL100V2

**Choice**: Add a `writable_ranges` property to `El100V2` returning `[range(2000, 2087), range(2200, 2218)]` — excluding the UPS range.

**Rationale**: AC2A already overrides `writable_ranges` (line 268–269). EL100V2 can do the same. V2Base's default includes `range(3035, 3036)` because EP600 uses UPS mode, but EL100V2 doesn't.

**Alternative considered**: Change V2Base to remove the UPS range. Rejected: EP600 depends on it.

### Decision 4: Don't change other EL devices or AC2A

**Choice**: Scope changes to EL100V2 only.

**Rationale**: Other EL devices are TODO(hardware) — untested. AC2A passes verification with split reads. Changing unverified code introduces risk without evidence.

## Risks / Trade-offs

- **Risk**: Merged read returns 174 bytes (87 × 2). If the EL100V2 BLE→Modbus gateway has a per-response size limit, the read could fail differently than the split read. **Mitigation**: AC2A reads 140 bytes (70 registers for INV_PV_INFO) without issue; the APK reads 170+ bytes (85 registers) successfully. 174 bytes should be within device limits.

- **Risk**: Removing `ups_mode` from EL100V2 means users who rely on setting UPS mode on this device lose that capability. **Mitigation**: The APK doesn't expose functional UPS mode for V2 devices. If it worked, the hardware wouldn't return exception 3. Removing non-functional UI is an improvement.

- **Risk**: V2Base `writable_ranges` change (or override) might break EP600 verification. **Mitigation**: EP600 has its own `control_commands` returning only `[ReadHoldingRegisters(3035, 1)]`. Since we only override in EL100V2, V2Base's default remains for EP600.

## Open Questions

- Do other EL100V2 hardware units (different FW, different batch) exhibit the same behavior?
- Should tier 3 restore failures on this EL100V2 unit be investigated separately? (They may be device-specific timing issues.)
- Do EL10V2/EL30V2/EL400 need the same fix? (Can only determine via hardware verification.)
