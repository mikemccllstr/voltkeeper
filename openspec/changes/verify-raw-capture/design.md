# Design: Verify Raw Block Capture

## Context

`run_tier1` in `core/verify.py` executes every polling and control command, holding the raw payload (`raw` for plain reads, `item.value` per TLV item) before parsing — then drops it, recording only `fields_parsed` counts per block. The YAML report scrubs the parsed SN and MAC by string replacement, but raw bytes never reach the report.

Fixtures for parse tests (AC2A's conftest hex blobs) were harvested manually from a one-off BLE session. Every new device model and firmware revision will need the same harvest.

## Goals / Non-Goals

**Goals:**

- Every verify run durably records interpretation-free raw block bytes.
- Captured bytes are safe to commit (SN/MAC scrubbed) by default.
- A documented, repeatable path from capture to conftest fixture.

**Non-Goals:**

- No diffing framework, capture DSL, or automatic fixture generation — `diff`, git history, and deliberate hand-promotion cover those. Fixtures stay frozen, documented snapshots; auto-regeneration would churn test expectations every session.
- No new CLI command — this rides the existing verify flow. A standalone capture command can be split out later if a need appears.
- No semantic verification (e.g., whether charging mode 1 actually quiets the fan) — that remains a human check.

## Decisions

### 1. Raw hex goes in the existing YAML report, per block

Each tier-1 `BlockResult` gains a `raw` field: the payload as a hex string, keyed by the existing block address key (TLV items record per `reg_addr`, same as parse dispatch). One artifact per hardware session, additive format, ~2 KB growth.

*Alternative considered:* sidecar file per run. Rejected — two artifacts to keep paired, and the report already carries the device/firmware metadata that gives the bytes meaning.

### 2. Raw scrubbing zeroes sensitive bytes at struct-known offsets

The existing scrub replaces parsed SN/MAC strings in the YAML text; raw payloads need byte-level treatment. Sensitive fields are locatable from the device's own struct definitions: BCD SN fields (home 116–119, inv_base 1107–1110, pack_main 6004–6007) and the IOT block's MAC/IP bytes (fixed offsets per `_parse_iot_info`). Those byte ranges are zeroed in the recorded hex. Zeroed SN parses as `0`, which the report's `device` section already presents scrubbed, so parsed and raw stay consistent. `--no-scrub` bypasses raw scrubbing along with the existing text scrubbing.

*Alternative considered:* encode a fake SN (`VKTEST000000`) into the bytes. Rejected — BCD SN fields are numeric and can't hold that string; zeroing is honest about what was removed and round-trips through the parsers safely.

### 3. Fixture promotion is documented, not automated

verify.md gains a short workflow: run verify, copy the block's `raw` hex from the report into a conftest fixture, record the capture-time device state in the fixture docstring (the AC2A fixtures are the pattern). The scrubbed-by-default capture resolves the SN-in-fixtures question that the AC2A blobs (which carry a real SN) left open.

### 4. Fix the verify.md output-path drift in this change

The doc says reports go to the current directory; spec and code say `hardware-data/`. This change already rewrites that page's report-format section, so the fix lands here.

## Risks / Trade-offs

- [Zeroing bytes could hide a parse bug near SN offsets in fixtures made from captures] → the zeroed ranges are exactly the fields whose parsed values are scrubbed anyway; tests asserting SN content already use synthetic values.
- [Offsets for sensitive fields vary if a future device redefines struct layouts] → offsets are derived from the device instance's struct field definitions at scrub time, not hardcoded per model.
- [Report size growth] → ~2 KB/run; negligible against existing report sizes.

## Open Questions

None.
