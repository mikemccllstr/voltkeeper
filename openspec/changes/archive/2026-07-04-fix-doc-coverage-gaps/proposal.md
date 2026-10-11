## Why

A spec-vs-docs review revealed 19 gaps where user-facing documentation is missing,
incomplete, or inaccurate. The man page omits 3 command groups (verify, config,
daemon), the README omits verify and config from its capabilities table, the
daemon HTTP API has no structured reference, the WebSocket and fields endpoints are
undocumented, the required GitHub issue template does not exist, and several CLI
flags (--help-field, --device-type, --daemon on status) are absent from docs
that users rely on.

## What Changes

- Add verify, config, and daemon entries to the man page (voltkeeper.1.md)
- Add verify and config to the README capabilities table
- Document --daemon flag on status in the man page
- Document --help-field flag on write in write.md and the man page
- Document --device-type flag on mqtt-listen in mqtt.md and the man page
- Document --no-restart-on-source-change flag alongside its positive counterpart in mqtt.md
- Create .github/ISSUE_TEMPLATE/device-report.yml (required by existing device-testing-checklist spec)
- Document the daemon HTTP API: all 8 endpoints, auth, rate limiting, WebSocket in daemon.md
- Add a "Software versions" section to status.md explaining verbose output per the software-version-display spec
- Update backend-services.md with 3.0.10 cloud endpoint additions per apk-v3.0.9-vs-v3.0.10.md
- Add Web UI documentation section to daemon.md describing the interface served at /
- Add a test enforcing docs-code tier consistency (required by existing device-support-tiers spec)

## Capabilities

### New Capabilities
- daemon-http-api-docs: Structured reference for the daemon REST/WebSocket API including all endpoints, authentication, rate limiting, and network access control

### Modified Capabilities
<!-- No spec-level requirement changes. This change implements existing requirements
     from device-testing-checklist (issue template file) and device-support-tiers
     (consistency test) that were specified but not yet implemented. -->

## Impact

- docs/source/man/voltkeeper.1.md -- new command entries
- docs/source/user-guide/status.md -- new software versions section
- docs/source/user-guide/write.md -- --help-field docs
- docs/source/user-guide/mqtt.md -- --device-type and --no-restart-on-source-change docs
- docs/source/user-guide/daemon.md -- HTTP API reference and Web UI section
- docs/source/protocol/backend-services.md -- 3.0.10 endpoint additions
- README.md -- capabilities table additions
- .github/ISSUE_TEMPLATE/device-report.yml -- new file
- tests/ -- new test for docs-code tier consistency
