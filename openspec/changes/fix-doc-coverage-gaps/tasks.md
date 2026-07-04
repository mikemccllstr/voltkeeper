## 1. Man page additions

- [ ] 1.1 Add verify command entry to voltkeeper.1.md following existing pattern (subsection with synopsis, description, options table)
- [ ] 1.2 Add config group entry (show, set, add-device, remove-device subcommands) to voltkeeper.1.md
- [ ] 1.3 Add daemon group entry (start, status, stop, install, uninstall subcommands) to voltkeeper.1.md
- [ ] 1.4 Add --daemon flag to the status entry in voltkeeper.1.md
- [ ] 1.5 Add --help-field flag to the write entry in voltkeeper.1.md
- [ ] 1.6 Add --device-type flag to the mqtt-listen entry in voltkeeper.1.md
- [ ] 1.7 Add --no-restart-on-source-change flag to mqtt-publish and mqtt-listen entries in voltkeeper.1.md

## 2. README capabilities table

- [ ] 2.1 Add verify row to the README capabilities table
- [ ] 2.2 Add config row to the README capabilities table

## 3. User guide updates

- [ ] 3.1 Add Software versions section to status.md explaining which MCU versions appear in --verbose output (ARM, DSP, BMS, IOT, HMI1, HMI2) and how they are parsed
- [ ] 3.2 Add --help-field documentation to write.md with example usage and explanation
- [ ] 3.3 Add --device-type flag documentation to mqtt.md (mqtt-listen section)
- [ ] 3.4 Add --no-restart-on-source-change flag documentation to mqtt.md alongside --restart-on-source-change

## 4. Daemon HTTP API and Web UI documentation

- [ ] 4.1 Add HTTP API Reference section to daemon.md with table of all 8 endpoints (method, path, auth, description)
- [ ] 4.2 Document authentication mechanisms (Bearer header and ?token= query parameter)
- [ ] 4.3 Document rate limiting (60 req/60s per IP)
- [ ] 4.4 Document GET /api/devices endpoint with response format
- [ ] 4.5 Document GET /api/device/{address} endpoint with response format
- [ ] 4.6 Document GET /api/device/{address}/fields endpoint with response format
- [ ] 4.7 Document POST /api/device/{address}/command endpoint with request/response format
- [ ] 4.8 Document POST /api/shutdown endpoint
- [ ] 4.9 Document POST /api/reload endpoint with restart-required semantics
- [ ] 4.10 Document GET /ws WebSocket endpoint (connection behavior, initial messages, state_update format)
- [ ] 4.11 Add Web UI section to daemon.md describing the interface, authentication, and relationship to API/WebSocket

## 5. Protocol docs

- [ ] 5.1 Update backend-services.md with 3.0.10 cloud API endpoint additions from the apk-v3.0.9-vs-v3.0.10.md diff report

## 6. Issue template

- [ ] 6.1 Create .github/ISSUE_TEMPLATE/device-report.yml with required fields (model, firmware, voltkeeper version, OS, adapter, verify report, claimed tier) matching the existing device-testing-checklist spec and test-your-device.md expectations

## 7. Tier consistency test

- [ ] 7.1 Write a test that parses the model tables in docs/source/protocol/device-models.md and asserts every registry model appears exactly once with the correct SUPPORT_TIER
- [ ] 7.2 Run the test and fix any existing tier discrepancies it reveals

## 8. Verification

- [ ] 8.1 Run mise run check to verify all existing tests, lint, and typecheck still pass
- [ ] 8.2 Run mise run docs to verify Sphinx builds without errors
- [ ] 8.3 Run mise run docs-lint to verify doc formatting
