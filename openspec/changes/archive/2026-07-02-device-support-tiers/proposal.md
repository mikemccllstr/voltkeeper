## Why

The registry lists ~20 device models, but only the AC2A is verified on real hardware (EL100V2 verification is in progress); the rest are APK-derived and untested. Nothing in `scan` output or the docs distinguishes them, so users can't tell what "supported" actually means for their device, and the README's ask for volunteer testers has no concrete entry point. This is item #13 of `code-review-2026-07-02.md`.

## What Changes

- Add a `SupportTier` enum and a `SUPPORT_TIER` class attribute to `BluettiDevice`, defaulting to `APK_DERIVED` so unverified models are labeled untested without any per-model code.
- Override the tier on the two models with hardware evidence: `AC2A` → `HARDWARE_VERIFIED`, `El100V2` → `HARDWARE_TESTING`.
- Show the tier in `voltkeeper scan` output next to the existing encryption flag, with a one-line contribution hint when an untested model is found.
- Add a "Support" column to the model tables in `docs/source/protocol/device-models.md`.
- Add a user-guide page defining the three tiers and the promotion criterion (a passing `voltkeeper verify` run on real hardware), wired into the docs nav.
- Add a test that parses the device-models.md tables and asserts each documented tier matches the model class's `SUPPORT_TIER`, so docs and code cannot drift.

## Capabilities

### New Capabilities

- `device-support-tiers`: per-model hardware-verification tier — the enum and class attribute, tier display in scan output, docs surfacing, and the docs/code consistency guard.

### Modified Capabilities

<!-- none — existing capability requirements are unchanged; the tier is a new orthogonal attribute -->

## Impact

- `src/voltkeeper/core/devices/bluetti_device.py` — `SupportTier` enum + `SUPPORT_TIER` default
- `src/voltkeeper/core/devices/ac2a.py`, `el100v2.py` — tier overrides
- `src/voltkeeper/bluetooth/__init__.py` (`ScanResult.display`) and `src/voltkeeper/cli/scan.py` — tier display and contribution hint
- `docs/source/protocol/device-models.md` — Support column
- `docs/source/user-guide/` — new page + nav entry
- `tests/` — tier attribute tests, scan display tests, docs consistency test
- No protocol, daemon, API, or MQTT behavior changes; no new dependencies
