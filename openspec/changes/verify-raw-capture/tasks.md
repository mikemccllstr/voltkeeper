# Tasks: Verify Raw Block Capture

## 1. Raw payload recording

- [x] 1.1 Write failing tests: tier 1 records `raw` hex per block for plain reads, per `reg_addr` for TLV items, and on parse failure
- [x] 1.2 Add `raw` to `BlockResult` and record payload hex in `run_tier1` for both read paths
- [x] 1.3 Run tests to green

## 2. Raw payload scrubbing

- [x] 2.1 Write failing tests: SN register bytes zeroed in HOME/INV_BASE_INFO/PACK_MAIN_INFO hex, MAC/IP bytes zeroed in IOT block hex, scrubbed HOME hex still parses (SN `0`), `--no-scrub` leaves bytes identical
- [x] 2.2 Implement raw scrubbing driven by the device's struct field definitions (BCD SN fields) plus the IOT block's fixed MAC/IP offsets; wire into the existing scrub path and `--no-scrub` flag
- [x] 2.3 Run tests to green; run full test suite

## 3. Documentation

- [x] 3.1 Fix verify.md report-location drift: report is written to `hardware-data/`, not the current directory
- [x] 3.2 Document the raw capture in verify.md: what is recorded, the scrubbing behavior, and the report field
- [x] 3.3 Add a fixture-promotion workflow section to verify.md: run verify, copy block `raw` hex into a conftest fixture, document capture-time device state (AC2A fixtures as the pattern)
- [x] 3.4 Update verify-interpretation.md if the report-format tables there need the new `raw` field; rebuild docs and check for warnings

## 4. Review fixes (scrubbing holes found in pre-commit review)

- [x] 4.1 Write failing tests: V1 device SN scrubbed (real_data_struct, block 10), IoT module SN bytes zeroed, TLV item parse failure isolated, unparseable bundle flagged/dropped when scrubbing, `raw_bundle` key under `--no-scrub`
- [x] 4.2 Derive SN scrub ranges from all device structs against each block's read window (covers V1 and any future block; removes hardcoded base addresses); add iot_sn to the IOT fixed ranges
- [x] 4.3 Restructure the TLV failure path: per-item try/except so one item's failure keeps other items' results; unsplittable bundles recorded with `raw_is_bundle`, dropped by scrubbing, reported as `raw_bundle` with `--no-scrub`
- [x] 4.4 Amend spec delta, design.md, and verify.md for the above; run full suite to green
