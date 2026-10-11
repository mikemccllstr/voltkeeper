## 1. Man page additions

- [x] 1.1 Add verify command entry to voltkeeper.1.md following existing pattern (subsection with synopsis, description, options table)
- [x] 1.2 Add config group entry (show, set, add-device, remove-device subcommands) to voltkeeper.1.md
- [x] 1.3 Add daemon group entry (start, status, stop, install, uninstall subcommands) to voltkeeper.1.md
- [x] 1.4 Add --daemon flag to the status entry in voltkeeper.1.md
- [x] 1.5 Add --help-field flag to the write entry in voltkeeper.1.md
- [x] 1.6 Add --device-type flag to the mqtt-listen entry in voltkeeper.1.md
- [x] 1.7 Add --no-restart-on-source-change flag to mqtt-publish and mqtt-listen entries in voltkeeper.1.md

## 2. README capabilities table

- [x] 2.1 Add verify row to the README capabilities table
- [x] 2.2 Add config row to the README capabilities table

## 3. User guide updates

- [x] 3.1 Add Software versions section to status.md explaining which MCU versions appear in --verbose output (ARM, DSP, BMS, IOT, HMI1, HMI2) and how they are parsed
- [x] 3.2 Add --help-field documentation to write.md with example usage and explanation
- [x] 3.3 Add --device-type flag documentation to mqtt.md (mqtt-listen section)
- [x] 3.4 Add --no-restart-on-source-change flag documentation to mqtt.md alongside --restart-on-source-change

## 4. Daemon HTTP API and Web UI documentation

- [x] 4.1 Add HTTP API Reference section to daemon.md with table of all 8 endpoints (method, path, auth, description)
- [x] 4.2 Document authentication mechanisms (Bearer header and ?token= query parameter)
- [x] 4.3 Document rate limiting (60 req/60s per IP)
- [x] 4.4 Document GET /api/devices endpoint with response format
- [x] 4.5 Document GET /api/device/{address} endpoint with response format
- [x] 4.6 Document GET /api/device/{address}/fields endpoint with response format
- [x] 4.7 Document POST /api/device/{address}/command endpoint with request/response format
- [x] 4.8 Document POST /api/shutdown endpoint
- [x] 4.9 Document POST /api/reload endpoint with restart-required semantics
- [x] 4.10 Document GET /ws WebSocket endpoint (connection behavior, initial messages, state_update format)
- [x] 4.11 Add Web UI section to daemon.md describing the interface, authentication, and relationship to API/WebSocket

## 5. Protocol docs

- [x] 5.1 Update backend-services.md with 3.0.10 cloud API endpoint additions from the apk-v3.0.9-vs-v3.0.10.md diff report

## 6. Issue template

- [x] 6.1 Create .github/ISSUE_TEMPLATE/device-report.yml with required fields (model, firmware, voltkeeper version, OS, adapter, verify report, claimed tier) matching the existing device-testing-checklist spec and test-your-device.md expectations — already present, added in commit 0701756

## 7. Tier consistency test

- [x] 7.1 Write a test that parses the model tables in docs/source/protocol/device-models.md and asserts every registry model appears exactly once with the correct SUPPORT_TIER — already present as TestDocsConsistency in tests/test_device_registry.py, added in commit 533281b
- [x] 7.2 Run the test and fix any existing tier discrepancies it reveals — no discrepancies; the test passes against the current registry

## 8. Review corrections

- [x] 8.1 Make FIELD and VALUE optional on `voltkeeper write` so the documented `--help-field` invocation runs, with CLI tests
- [x] 8.2 Correct write.md and the man page: `--help-field` needs only ADDRESS, does a BLE scan lookup, and prints ranges without a unit suffix when the field defines none
- [x] 8.3 Correct daemon.md: `ws://` (the daemon terminates no TLS), reload does not detect a changed server.api_key, cross-reference direction, cached state_update on connect
- [x] 8.4 Correct status.md: drop MCU type code 0 (never emitted), describe all three format_version shapes
- [x] 8.5 Remove the duplicated mqtt-listen example in mqtt.md
- [x] 8.6 Note the `/file/v1/getFile` path variant in backend-services.md

## 9. Verification

- [x] 9.1 Run mise run check to verify all existing tests, lint, and typecheck still pass — 1004 passed, 2 skipped
- [x] 9.2 Run mise run docs to verify Sphinx builds without errors — build succeeded, 9 pre-existing index.md heading warnings
- [x] 9.3 Run mise run docs-lint to verify doc formatting — no problems found
