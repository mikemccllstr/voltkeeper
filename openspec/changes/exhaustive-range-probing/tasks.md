## 1. FieldResult dataclass

- [x] 1.1 Add `current_value: Optional[int]` field to `FieldResult`
- [x] 1.2 Add `probes_count: Optional[int]` field to `FieldResult`
- [x] 1.3 Add `probed_range: Optional[list[int]]` field to `FieldResult`
- [x] 1.4 Add `probe_cap_hit: Optional[bool]` field to `FieldResult`
- [x] 1.5 Add `declared_range: Optional[list[int]]` field to `FieldResult`
- [x] 1.6 Add `in_range_rejected: Optional[list[int]]` field to `FieldResult`

## 2. run_tier3_numeric — failing tests first (TDD)

- [x] 2.1 Write test: exhaustive sweep discovers range not starting at 0 (e.g., accepted [5, 10], sweep stops at 12)
- [x] 2.2 Write test: pre-range zone never triggers early termination
- [x] 2.3 Write test: post-range early termination after 2 consecutive rejections
- [x] 2.4 Write test: known declared range, all values accepted — correct summary fields emitted, no `probes` list
- [x] 2.5 Write test: known declared range with in_range_rejected values — status remains pass
- [x] 2.6 Write test: full 0–255 sweep with device accepting all — `probe_cap_hit: true`, `discovered_range: [0, 255]`
- [x] 2.7 Write test: restore skipped when readback equals current_int
- [x] 2.8 Write test: restore failure sets `restore_failed: true` and halts probe loop for that field
- [x] 2.9 Write test: `declared_range` and `range_discrepancy` correct when declared range differs from discovered
- [x] 2.10 Confirm all new tests fail before implementation

## 3. run_tier3_numeric — implementation

- [x] 3.1 Replace sparse probe sequence with ascending sweep `range(0, 256)`
- [x] 3.2 Implement pre/in/post-range state machine with consecutive-rejection counter
- [x] 3.3 Implement restore optimisation: skip restore when `readback == current_int`
- [x] 3.4 Populate `current_value`, `probes_count`, `probed_range`, `probe_cap_hit` from sweep state
- [x] 3.5 Populate `declared_range` from `_field_range_raw` (as a list, or null)
- [x] 3.6 Populate `in_range_rejected` from probes where declared range exists and value was rejected
- [x] 3.7 Set `status: fail` only when `restore_failed` is true (remove any other fail conditions from numeric path)
- [x] 3.8 Remove `probes` list population from numeric path
- [x] 3.9 Confirm all new tests pass; confirm existing bool/enum tests still pass

## 4. _tier_result_to_dict — serialisation

- [x] 4.1 Add serialisation for `current_value`
- [x] 4.2 Add serialisation for `probes_count`
- [x] 4.3 Add serialisation for `probed_range`
- [x] 4.4 Add serialisation for `probe_cap_hit`
- [x] 4.5 Add serialisation for `declared_range`
- [x] 4.6 Add serialisation for `in_range_rejected` (omit when null or empty list)
- [x] 4.7 Write test: serialised output for a numeric field matches expected YAML structure
- [x] 4.8 Confirm serialisation tests pass

## 5. hardware-data folder

- [ ] 5.1 Create `hardware-data/` directory at project root
- [ ] 5.2 Write `hardware-data/README.md` explaining purpose, naming convention, and that files are committed
- [ ] 5.3 Move `verify-AC2A-2026-05-26.yaml` and `verify-AC2A-2026-05-27.yaml` into `hardware-data/`
- [ ] 5.4 Update CLI default output path to `hardware-data/verify-<MODEL>-<DATE>.yaml`
- [ ] 5.5 Write test: CLI default output path resolves to `hardware-data/` prefix

## 6. Documentation — verify.md updates

- [ ] 6.1 Update tier 3 description to describe exhaustive sweep, state machine, and early termination
- [ ] 6.2 Update report structure example to show new numeric field summary format
- [ ] 6.3 Update result codes section: remove `probes` list description for numeric fields; add descriptions for new summary fields (`probes_count`, `probed_range`, `probe_cap_hit`, `declared_range`, `in_range_rejected`)
- [ ] 6.4 Update output file section: replace `.gitignore` advice with `hardware-data/` folder description
- [ ] 6.5 Add a note about expected runtime (approximately 2 min per numeric field at typical BLE throughput)

## 7. Documentation — verify-interpretation.md (new)

- [ ] 7.1 Write `docs/source/user-guide/verify-interpretation.md` with sections: Overview, Field Reference, How to Update a Device Model, Contiguous Range Assumption, Worked Examples
- [ ] 7.2 Field reference section: define every tier 3 numeric output field and its implications
- [ ] 7.3 Model update workflow: numbered steps for a Claude/agent instance — locate field, compare declared vs discovered, handle `probe_cap_hit`, handle `in_range_rejected`, commit message convention
- [ ] 7.4 Worked example 1: field with no declared range, narrow discovered range (e.g., `dc_eco_auto_off_time: [3, 4]`) → add range to device model
- [ ] 7.5 Worked example 2: field with declared range where device accepts wider range and `probe_cap_hit: true` → do NOT update range; add investigation comment
- [ ] 7.6 Worked example 3: field with in_range_rejected values → narrow the declared range
- [ ] 7.7 Contiguous assumption section: explain the pre/in/post-range model, what early termination means, and what happens if the assumption is violated
- [ ] 7.8 Add link to `verify-interpretation.md` from `docs/source/user-guide/index.md`

## 8. OpenSpec spec update

- [ ] 8.1 Sync `openspec/specs/device-verify/spec.md` with the delta spec (update tier 3 requirement text and scenarios, update output report requirement)
- [ ] 8.2 Create `openspec/specs/verify-interpretation/spec.md` with the new capability spec
