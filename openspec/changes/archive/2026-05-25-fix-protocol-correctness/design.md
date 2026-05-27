## Context

The current `EL400._build_control_struct` declares two BoolFields on the same register because the writes need different values (1 vs 4) but the reads are conceptually a single state. The current `V2Base._tlv_sections` was authored before per-pack polling was discovered through NODE_INFO; it predates the multi-slave routing. The `topology_discovered` short-circuit was a defensive guard added so single-pack devices wouldn't be perpetually "undiscovered" — but the boolean expression as written is incorrect.

All three are isolated bugs with clean fixes. No new dependencies, no protocol-level negotiation, no schema changes.

## Goals / Non-Goals

**Goals:**
- Fix the three defects in the smallest reasonable way.
- Add test coverage that would have caught each one.
- Keep the public API of `BluettiDevice` unchanged for non-EL400 devices.

**Non-Goals:**
- Refactoring the polling pipeline.
- Generalizing `SystemPowerOff` to V1 devices (V1 uses register 3060 with the same enum semantics, but that's out of scope here — leave it for a future change).
- Reworking topology discovery beyond fixing the precedence bug.

## Decisions

### 1. `SystemPowerOff` as a shared enum

**Decision:** Define `SystemPowerOff(Enum)` in `core/commands.py` next to `WorkingMode`, `ChargingMode`. Use it on EL400 immediately; do not retrofit other devices in this change.

**Rationale:** Putting it in `commands.py` follows the convention used for `WorkingMode`. Other V2 devices currently expose `power_off` as a plain bool (the value `1` is the only one they meaningfully accept). Migrating them is a separable refactor — doing it here would expand the blast radius unnecessarily.

### 2. Per-slave TLV: list[TlvReadHoldingRegisters], not a multi-slave TLV

**Decision:** `tlv_polling_commands` returns a list of `TlvReadHoldingRegisters`, one per slave address that has work to do. The "main" slave (`1`) gets the home + (slow blocks) + NODE_INFO bundle. Each discovered pack slave gets its own bundle (just `PACK_MAIN_INFO`).

```
                              voltkeeper today
                ┌─────────────────────────────────────────┐
                │ 1 × TLV bundle (slave_addr=1)           │
                │   ├─ APP_HOME_DATA   (slave-1 data)     │
                │   ├─ INV_BASE_INFO   (slave-1 data)     │
                │   ├─ NODE_INFO       (slave-1 data)     │
                │   ├─ PACK_MAIN_INFO  (slave-1 data!!)   │   ← wrong: this
                │   └─ PACK_MAIN_INFO  (slave-1 data!!)   │     pack lives on
                └─────────────────────────────────────────┘     slave 41/42

                              after this change
                ┌──────────────────────────────────────┐
                │ TLV bundle (slave_addr=1)            │
                │   ├─ APP_HOME_DATA                   │
                │   ├─ INV_BASE_INFO                   │
                │   └─ NODE_INFO                       │
                └──────────────────────────────────────┘
                ┌──────────────────────────────────────┐
                │ TLV bundle (slave_addr=41)           │
                │   └─ PACK_MAIN_INFO                  │
                └──────────────────────────────────────┘
                ┌──────────────────────────────────────┐
                │ TLV bundle (slave_addr=42)           │
                │   └─ PACK_MAIN_INFO                  │
                └──────────────────────────────────────┘
```

**Rationale:** This mirrors what `ModbusV2Dispatcher` expects on the device side. The `parse_tlv` path already prefixes per-slave parsed fields with `sub[<slave>].`, so consumers see the corrected data automatically. The cost is one extra BLE round-trip per pack per slow cycle, which is the same shape as the non-TLV path in `polling_commands`.

### 3. Topology-discovered gate

**Decision:** `_topology_discovered` is set to `True` only inside `discover_topology()` after a NODE_INFO TLV response is parsed. The `topology_discovered` property returns `self._topology_discovered` only. The class-level `has_battery_packs` declaration is decoupled from the discovery state.

**Rationale:** The previous logic conflated "this device class declares battery packs" with "we have actually seen them on the wire." Those are different. Devices that declare `has_battery_packs=True` will still send the NODE_INFO read on each fast tick (see `_tlv_sections`), so discovery happens automatically on the first poll response — there is no risk of "stuck undiscovered."

## Risks / Trade-offs

- **[Risk] EL400 reads have never been verified against hardware.** The fix is mechanical (one enum on one register) and matches what `ProtocolAddrV2.SYSTEM_POWER_OFF` documents. → **Mitigation**: keep the `TODO(hardware)` marker on EL400; document the new field in the user guide.
- **[Risk] Per-slave TLV doubles command count on stacked devices.** A 2-pack stack goes from 1 → 3 TLV commands per fast tick. BLE has headroom for this. → **Mitigation**: revisit only if a real stacked-pack user reports throughput issues.
- **[Trade-off] We're not migrating other V2 devices to `SystemPowerOff`.** Keeps the change focused; will get picked up if/when someone adds sleep support to another device class.
