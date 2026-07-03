# Verify Raw Block Capture

## Why

`voltkeeper verify` reads every register block during tier 1 and then discards the raw bytes, keeping only values interpreted through our own parsers — so a parser bug bakes itself into the evidence (the AC2A capture reads `charging_mode: silent`, but "silent" is our possibly-wrong enum label). Raw hex is interpretation-free ground truth: it lets us re-interpret historical captures after parser fixes, diff behavior across firmware versions, and harvest test fixtures reproducibly instead of hand-copying bytes from ad-hoc BLE sessions (how the AC2A conftest fixtures were made). The immediate consumer is the `el100v2-improvements` change, whose fixture tests need exactly this capture.

## What Changes

- Tier 1 of `voltkeeper verify` records the raw hex payload of every register block it reads (plain and TLV-bundled) in the YAML report, alongside the existing parse results
- Raw payloads are scrubbed before writing: serial-number registers and IoT MAC/IP bytes are zeroed at their known offsets, consistent with the existing SN/MAC scrubbing of parsed values; `--no-scrub` bypasses both
- The verify user guide documents the raw capture and the workflow for promoting captured hex into test fixtures
- Fix existing doc drift in `docs/source/user-guide/verify.md`: the report is written to `hardware-data/`, not the current directory

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `device-verify`: tier 1 requirement gains raw-payload recording; the output-report requirement gains raw-payload scrubbing and the corresponding report format.

## Impact

- `src/voltkeeper/core/verify.py`: `run_tier1` records block hex; scrub logic extended to raw payloads
- `tests/test_iot_probe.py` / verify test modules: new tests for raw recording and raw scrubbing
- `docs/source/user-guide/verify.md`: report-location fix, raw-capture section, fixture-promotion workflow
- Report files grow by roughly 2 KB per run (hex of ~8 blocks); format is additive, existing consumers unaffected
- Downstream: `el100v2-improvements` group 3 consumes this capability for its hardware session
