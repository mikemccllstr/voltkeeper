# Tasks: Verify Ground Truth Mode

> Group 0 (the re-evaluation gate) is complete; groups 1+ are cleared for implementation.
> Groups 1, 3, 4, and 5 were re-opened after code review (2026-07-04); group 6 collected the
> remediation work. Remaining open items: 6.8c (deferred by design) and V1 alarm-path
> support in 6.4 (currently V2-only).

## 0. Re-evaluation gate (bench findings first)

- [x] 0.1 During the next bench session, test whether the vendor app can display live device data (cloud/IoT path) while voltkeeper holds the BLE connection; record the answer in design.md (no — BLE is exclusive and cloud path was inactive; recorded in design.md open questions)
- [x] 0.2 Inventory what the EL100V2 and AC2A on-device screens display; mark which core-list observation fields are anchorable; record in design.md (done from official user manuals in `bluetti-files/manuals/` — see "Device-screen inventory" in design.md)
- [x] 0.3 Run one manual ground-truth session using notes (the `el100v2-improvements` hardware session is the natural opportunity) and use it to refine the prompt list and tolerances in this change's spec (session: 2026-07-03 EL100V2 bench, `hardware-data/verify-EL100V2-2026-07-03-notes.md`; spec refined: totals-vs-sums, alternating-values answer, secondary-source voltage class, display-format firmware comparison, `not_confirmable_on_device` outcome)
- [x] 0.4 Decide flag vs. standalone subcommand based on how the induce-and-capture flow fit the manual session; revise proposal/design/spec accordingly and get Mike's sign-off to proceed (decided: `verify --ground-truth` flag, design decision 6; Mike sign-off 2026-07-04)

## 1. Passive observations

- [x] 1.1 Write failing tests: prompt flow records observation/parsed/raw-ref/match; tolerances applied per quantity; skip records `skipped`; alternating two-level answers match either level; "not available" on secondary-source prompts records `unanchored`; source recorded as `multimeter`; `battery_direction` removed (uint vs. string comparison can't work); `firmware_display` fixed to apply display format (÷100) against the parsed raw value
- [x] 1.2 Implement the observation prompt flow, core field list, tolerance comparison, and `ground_truth` report section
- [x] 1.3 Run tests to green

## 2. Scale inference

- [x] 2.1 Write failing tests: mismatched numeric observation tested against raw value at ×1/÷10/÷100; matching scale recorded
- [x] 2.2 Implement the scale-inference comparator
- [x] 2.3 Run tests to green

## 3. Active control checks

- [x] 3.1 Write failing tests: actuate-and-confirm records wrote/readback/device_confirmed; SKIP_AUTO fields excluded; tier-6 fields never actuated; unconsented tier-4/5 fields excluded; `not_confirmable_on_device` still performs write/readback/restore; restore happens on every path that wrote (including readback failure); denial with readback match recorded distinctly
- [x] 3.2 Implement actuate-and-confirm over writable enum/bool fields, gated by FIELD_TIERS and per-tier consent threaded from the CLI
- [x] 3.3 Run tests to green

## 4. Induced-condition checks

- [x] 4.1 Write failing tests: typed confirmation gates each check; alarm state decoded via the device's own alarm decoding over the captured HOME payload; captured raw hex is scrubbed under default scrubbing; skip path records `skipped`
- [x] 4.2 Implement the AC-overload check with its documented designed-protection rationale
- [x] 4.3 Run tests to green; run full test suite

## 5. Documentation

- [x] 5.1 Add a ground-truth mode section to verify.md: what it is, when to run it, the session checklist, safety notes for induced conditions, tier-gating of actuations, and the `--yes` mutual exclusion
- [x] 5.2 Update verify-interpretation.md for the `ground_truth` report section (source values, `unanchored` semantics, alarm_bits as parsed alarm keys, tier-skip notes)
- [x] 5.3 Update docs navigation/toctree if pages were added; rebuild docs and check for warnings

## 6. Review remediation

- [x] 6.1 Tier-gate actuations: consult `FIELD_TIERS`, never actuate tier 6, actuate tier 4/5 only with the run's per-tier consent (consent state threaded from CLI into `_run_ground_truth`); import `SKIP_AUTO` instead of the `ACTUATE_SKIP` copy
- [x] 6.2 Reject `--yes` + `--ground-truth` as a CLI error before connecting; removed pre-consent skip paths from the ground-truth runners
- [x] 6.3 Fix `_lookup_raw_value`: scan all blocks by enclosing address range (not field address); add `SYNTH_REGISTERS` map for synthesized phase keys (`acPhase[0].voltage`, `gridPhase[0].voltage`); populate `raw_ref` on observations
- [x] 6.4 Replace the hardcoded alarm register 110 with the device's alarm decoding over the captured HOME payload (V2 `APP_HOME_DATA`=100); V1 alarm path not yet supported
- [x] 6.5 Scrub the `ground_truth` section: induced-check `raw_hex` passed through `_scrub_block_raw` with BCD-serial-field logic, matching tier-results scrubbing
- [x] 6.6 Restore the original value on every actuation path that performed a write, including readback failure
- [x] 6.7 Derive the actuation write value once at build time and store it on `ActuateCheck` so the report label cannot diverge from the written register value
- [x] 6.8a Reuse `verify._serialize` instead of `_serialize_gt`
- [x] 6.8b Use `CORE_OBS_MAP` instead of rebuilding `defs_by_id`
- [ ] 6.8c Consider a no-BLE opt-in prompt before each actuation write (deferred — conflicts with spec's write-before-confirm; keep current write-then-prompt flow)
- [x] 6.9 Run ground truth under a `--tier` limit: `_maybe_run_ground_truth` called from the early `--tier 1`/`--tier 2` exits and the main path; CLI-level tests in `tests/cli/test_verify.py` pin the report section presence/absence
- [x] 6.10 Test `run_actuations` against `FakeBluetoothClient`: wrote/readback/confirmed recording, restore on every written path including readback failure (write_log ordering asserted), denial-with-readback-match note, not-confirmable fields write/readback/restore without prompting
