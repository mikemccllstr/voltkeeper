## 1. Support tier enum and model attributes

- [x] 1.1 Write failing tests: `SupportTier` enum members; default `SUPPORT_TIER` is `APK_DERIVED` for every registry class except AC2A/El100V2; `AC2A` is `HARDWARE_VERIFIED`; `El100V2` is `HARDWARE_TESTING` (extend `tests/test_device_registry.py`)
- [x] 1.2 Add `SupportTier` enum and `SUPPORT_TIER` default to `core/devices/bluetti_device.py`; override in `ac2a.py` and `el100v2.py`; run tests green

## 2. Scan output

- [x] 2.1 Write failing tests: tier label rendered next to the encryption flag for known prefixes; no tier and no exception for unknown prefixes; contribution hint printed when a non-verified model is found
- [x] 2.2 Factor a registry prefix→class lookup usable by scan (reuse the matching in `build_device`), thread the tier into `ScanResult.display()` / `cli/scan.py`, and add the contribution hint line; run tests green

## 3. Documentation

- [x] 3.1 Add Support column to every model table in `docs/source/protocol/device-models.md`
- [x] 3.2 Add user-guide page defining the three tiers, what "supported" vs "verified" means, and the `verify`-based promotion criteria; add it to the user-guide toctree
- [x] 3.3 Update the README "Tested devices" section to reference the tier page and reflect EL100V2's `HARDWARE_TESTING` status
- [x] 3.4 Run `mise run docs-lint` and `mise run docs-format-check`; build docs and confirm the new page renders in the nav

## 4. Docs/code consistency guard

- [x] 4.1 Write failing test that parses the device-models.md tables and asserts every registry model appears exactly once with a Support cell matching its class's `SUPPORT_TIER`, with failure messages naming the model
- [x] 4.2 Fix any mismatches the test surfaces; run the full suite, lint, and typecheck green
