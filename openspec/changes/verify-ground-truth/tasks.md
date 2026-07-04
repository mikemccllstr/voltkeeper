# Tasks: Verify Ground Truth Mode (sketch)

> **Status: sketch.** Group 0 gates everything else; do not start groups 1+ until it is done and the change has been re-evaluated against its findings.

## 0. Re-evaluation gate (bench findings first)

- [x] 0.1 During the next bench session, test whether the vendor app can display live device data (cloud/IoT path) while voltkeeper holds the BLE connection; record the answer in design.md (no — BLE is exclusive and cloud path was inactive; recorded in design.md open questions)
- [ ] 0.2 Inventory what the EL100V2 and AC2A on-device screens display; mark which core-list observation fields are anchorable; record in design.md
- [ ] 0.3 Run one manual ground-truth session using notes (the `el100v2-improvements` hardware session is the natural opportunity) and use it to refine the prompt list and tolerances in this change's spec
- [ ] 0.4 Decide flag vs. standalone subcommand based on how the induce-and-capture flow fit the manual session; revise proposal/design/spec accordingly and get Mike's sign-off to proceed

## 1. Passive observations

- [ ] 1.1 Write failing tests: prompt flow records observation/parsed/raw-ref/match; tolerances applied per quantity; skip records `skipped`; `--yes` never prompts
- [ ] 1.2 Implement the observation prompt flow, core field list, tolerance comparison, and `ground_truth` report section
- [ ] 1.3 Run tests to green

## 2. Scale inference

- [ ] 2.1 Write failing tests: mismatched numeric observation tested against raw value at ×1/÷10/÷100; matching scale recorded
- [ ] 2.2 Implement the scale-inference comparator
- [ ] 2.3 Run tests to green

## 3. Active control checks

- [ ] 3.1 Write failing tests: actuate-and-confirm records wrote/readback/device_confirmed; SKIP_AUTO fields excluded; denial with readback match recorded distinctly
- [ ] 3.2 Implement actuate-and-confirm over writable enum/bool fields
- [ ] 3.3 Run tests to green

## 4. Induced-condition checks

- [ ] 4.1 Write failing tests: typed confirmation gates each check; alarm/fault registers and raw HOME hex captured during the condition; skip path records `skipped`
- [ ] 4.2 Implement the AC-overload check with its documented designed-protection rationale
- [ ] 4.3 Run tests to green; run full test suite

## 5. Documentation

- [ ] 5.1 Add a ground-truth mode section to verify.md: what it is, when to run it, the session checklist, safety notes for induced conditions
- [ ] 5.2 Update verify-interpretation.md for the `ground_truth` report section
- [ ] 5.3 Update docs navigation/toctree if pages were added; rebuild docs and check for warnings
