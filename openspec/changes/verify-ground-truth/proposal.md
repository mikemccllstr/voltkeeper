# Verify Ground Truth Mode

> **Status: sketch.** Deliberately drafted ahead of need, to be re-evaluated and likely revised after `verify-raw-capture` lands and the first bench session answers the open questions (app/BLE concurrency, on-device UI coverage). Do not implement without revisiting.

## Why

Verify's tiers prove self-consistency — the device echoes back what we wrote — but cannot prove our *interpretation* is correct. Every interpretation bug found so far (AC2A pack-voltage 10× scale, the suspected TURBO/SILENT charging-mode swap) was caught by comparing our parsed values against an external reference: the device's own display or the vendor app. That comparison is currently ad-hoc and undocumented. A ground-truth mode makes it a first-class, durable part of a verify session: the operator observes the device, keys in what it shows, and the report records observation, parsed value, and raw hex side by side — a fact base for validating and refining device implementations, per model and per firmware.

## What Changes

- An attended ground-truth mode for `voltkeeper verify` (opt-in flag; unattended `--yes` runs are unaffected) with three interaction classes:
  - **Passive observation**: prompt the operator for values shown on the device's own UI (SoC, charging mode, AC/DC output state, voltages, load watts); record them alongside the parsed values and raw hex, with tolerance-aware comparison for numeric fields
  - **Active control checks**: write a setting (e.g., charging mode → turbo), then ask the operator to confirm the effect on the device UI; records confirmed/denied — this directly catches enum label swaps
  - **Induced-condition checks**: the operator creates a physical condition the device is designed to handle (e.g., AC overload tripping the designed protection), and the tool captures the alarm/fault registers during it — validating alarm-bit decoding against reality
- Numeric comparisons account for observation noise (operator enters 122 V, register reads 121.0) and support scale inference: when an observation matches the raw register under a different decimal scale (raw 1210 vs. observed 121 → decivolts), the report says so
- All prompts, observations, and outcomes recorded durably in the report's `ground_truth` section
- Safety guardrails: induced-condition checks are limited to conditions within the device's designed protections and require typed confirmation, following the existing tier-6 pattern

## Capabilities

### New Capabilities

- `verify-ground-truth`: attended verify mode capturing operator-observed device state, control-effect confirmations, and induced-condition register captures, with tolerance and scale-inference comparison.

### Modified Capabilities

None yet — sketch assumes the mode is additive to `device-verify`; if implementation ends up changing existing tier behavior or report structure beyond adding a section, a `device-verify` delta gets added at revision time.

## Impact

- `src/voltkeeper/core/verify.py` (or a sibling module): prompt flow, comparison/tolerance logic, `ground_truth` report section
- `src/voltkeeper/cli/`: new flag, interactive prompts
- Depends on `verify-raw-capture` (observations are anchored to captured raw hex)
- Docs: verify.md attended-mode section; verify-interpretation.md for the new report section
- Downstream consumers: the charging-mode swap investigation becomes a scripted active-control check instead of a bespoke session; future device bring-up (support-tier promotion) gains a repeatable characterization protocol
