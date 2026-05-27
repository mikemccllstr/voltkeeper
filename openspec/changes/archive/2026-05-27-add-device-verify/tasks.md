## 1. Core verify module

- [x] 1.1 Create `src/voltkeeper/core/verify.py` with `FIELD_TIERS` dict (tier 4/5/6 classifications)
- [x] 1.2 Add `SKIP_TIER2` set for fields with no safe default (e.g., `system_time`)
- [x] 1.3 Add `safe_default(field: DeviceField) -> int` — returns safe write value for unreadable fields
- [x] 1.4 Add `build_tier_plan(device) -> dict[int, list[str]]` — partitions WRITABLE_FIELD_NAMES by tier
- [x] 1.5 Add `read_single_register(client, device, address) -> dict` — issues ReadHoldingRegisters(address, 1) and parses result via device.parse()

## 2. Tier runners

- [x] 2.1 Add `run_tier1(client, device) -> TierResult` — polls all control_commands + polling_commands, parses, records per-block results
- [x] 2.2 Add `run_tier2(client, device, tier1_result, fields) -> TierResult` — identity write loop; uses safe default when field absent from tier1 parse
- [x] 2.3 Add `run_tier3_bool(client, device, field, current) -> FieldResult` — toggle and restore
- [x] 2.4 Add `run_tier3_enum(client, device, field, current) -> FieldResult` — cycle all members, restore after each
- [x] 2.5 Add `run_tier3_numeric(client, device, field, current) -> FieldResult` — probe boundary sequence, infer discovered_range, set range_discrepancy flag
- [x] 2.6 Add `run_tier3(client, device, tier1_result, fields) -> TierResult` — dispatches to type-specific runners above
- [x] 2.7 Add `run_tier_supervised(client, device, tier1_result, fields, tier_num) -> TierResult` — identity write only (no probe writes) for tiers 4/5/6
- [x] 2.8 Handle restore failures in all tier-3 runners: set `restore_failed: true`, record `last_known_value`, skip remaining probes for that field

## 3. Report builder

- [x] 3.1 Add `build_report(device, sn, address, tier_results) -> dict` — assembles full report dict
- [x] 3.2 Scrub SN to `VKTEST000000` and BLE address to `AA:BB:CC:DD:EE:FF` in report
- [x] 3.3 Include firmware fields from tier-1 parse result in `device` section
- [x] 3.4 Represent skipped tiers as `{status: skipped, reason: "user declined", fields: {}}` (not omitted)
- [x] 3.5 Add `write_report(report: dict, path: str)` — serializes to YAML

## 4. CLI command

- [x] 4.1 Add `verify` command to `src/voltkeeper/cli.py` with args: `address`, `--output`, `--tier`, `--yes`, `--no-scrub`
- [x] 4.2 Implement tier-boundary prompt logic: print risk description, ask `Continue? [y/N]`, handle `--yes` bypass
- [x] 4.3 Implement tier-6 typed confirmation: require exact string `"I understand this is irreversible"`; `--yes` bypasses
- [x] 4.4 Print per-tier progress summary (one line per tier: `Tier 1  ████████  23/23  ✓`)
- [x] 4.5 Print halt recommendation after any tier with failures: "⚠ N issue(s) found — consider sharing the report before continuing"
- [x] 4.6 Print report path and GitHub issue reminder on completion
- [x] 4.7 Respect `--tier N` flag: stop after tier N (skip remaining tiers, record as `skipped (tier limit)`)

## 5. Tests

- [x] 5.1 Unit test `build_tier_plan` — verify ac_output → tier 4, charging_mode → tier 3, unknown field → tier 3
- [x] 5.2 Unit test `safe_default` — bool → 0, enum → first member, uint with range → range_min, uint without range → 0
- [x] 5.3 Unit test `run_tier2` — field present in status: identity write, match; field absent: safe default, note recorded
- [x] 5.4 Unit test `run_tier3_numeric` with declared range: verify boundary probe sequence and `discovered_range` inference
- [x] 5.5 Unit test `run_tier3_numeric` range_discrepancy: discovered range wider than declared → flag set
- [x] 5.6 Unit test `run_tier3_bool`: toggle and restore sequence; restore_failed path
- [x] 5.7 Unit test `run_tier3_enum`: all members cycled, each restored
- [x] 5.8 Unit test report scrubbing: real SN and address absent from output dict
- [x] 5.9 Unit test skipped tier in report: `status: skipped` present, not omitted
- [x] 5.10 Add `FakeBluetoothClient` to test helpers — stateful dict[address→value], write updates state, read returns current bytes, configurable rejected addresses for failure-path testing
- [x] 5.11 Test tier-2 roundtrip using FakeBluetoothClient: write current value, verify readback matches
- [x] 5.12 Test tier-2 mismatch path: configure FakeBluetoothClient to return a different value than written, verify `match: false` and `status: fail`
- [x] 5.13 Test tier-3 range probe using FakeBluetoothClient: verify boundary sequence runs, discovered_range inferred, restore verified
- [x] 5.14 Test restore-failure path: configure FakeBluetoothClient to reject the restore write, verify `restore_failed: true` and testing continues with next field

## 6. Documentation

- [x] 6.1 Create `docs/source/user-guide/verify.md` — cover command syntax, all six tiers with risk descriptions, the output YAML format, scrubbing behaviour, and how to submit the report as a GitHub issue
- [x] 6.2 Add `verify` to `docs/source/user-guide/index.md` navigation

## 7. Verification

- [x] 7.1 Run `mise run check` — lint, typecheck, tests all green
- [ ] 7.2 Hardware test on AC2A: run `voltkeeper verify` through tier 3, confirm report matches expected AC2A capabilities
- [ ] 7.3 Confirm tier-6 typed confirmation UX works correctly (manual test)
- [ ] 7.4 Review report output for readability — would a user understand it well enough to file a useful GitHub issue?
