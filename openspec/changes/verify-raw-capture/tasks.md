# Tasks: Verify Raw Block Capture

## 1. Raw payload recording

- [ ] 1.1 Write failing tests: tier 1 records `raw` hex per block for plain reads, per `reg_addr` for TLV items, and on parse failure
- [ ] 1.2 Add `raw` to `BlockResult` and record payload hex in `run_tier1` for both read paths
- [ ] 1.3 Run tests to green

## 2. Raw payload scrubbing

- [ ] 2.1 Write failing tests: SN register bytes zeroed in HOME/INV_BASE_INFO/PACK_MAIN_INFO hex, MAC/IP bytes zeroed in IOT block hex, scrubbed HOME hex still parses (SN `0`), `--no-scrub` leaves bytes identical
- [ ] 2.2 Implement raw scrubbing driven by the device's struct field definitions (BCD SN fields) plus the IOT block's fixed MAC/IP offsets; wire into the existing scrub path and `--no-scrub` flag
- [ ] 2.3 Run tests to green; run full test suite

## 3. Documentation

- [ ] 3.1 Fix verify.md report-location drift: report is written to `hardware-data/`, not the current directory
- [ ] 3.2 Document the raw capture in verify.md: what is recorded, the scrubbing behavior, and the report field
- [ ] 3.3 Add a fixture-promotion workflow section to verify.md: run verify, copy block `raw` hex into a conftest fixture, document capture-time device state (AC2A fixtures as the pattern)
- [ ] 3.4 Update verify-interpretation.md if the report-format tables there need the new `raw` field; rebuild docs and check for warnings
