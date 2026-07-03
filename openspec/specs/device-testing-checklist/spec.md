## ADDED Requirements

### Requirement: Tester walkthrough page

The user guide SHALL include a "Test your device" page, reachable from the user-guide toctree, that walks a volunteer tester end-to-end: prerequisites (OS support, BLE permissions), `voltkeeper scan` with expected output, `voltkeeper status` with instructions to spot-check readings against the device's own display, the `verify` invocation covering stages 1–3 and stage 4 under a connected load, and how to submit results. Each step SHALL state the expected outcome and what to do on failure. The page SHALL refer to `verify`'s write-risk levels as "stages", noting on first use that `verify.md` calls them tiers.

#### Scenario: Page exists and is navigable

- **WHEN** building the docs
- **THEN** the "Test your device" page renders and appears in the user-guide toctree

#### Scenario: Steps state expected outcomes

- **WHEN** reading any checklist step
- **THEN** it names the command to run, the expected result, and a failure action

### Requirement: BLE failure capture branch

The walkthrough SHALL include a troubleshooting branch for BLE-level failures (connect, handshake) that explains how to capture a btsnoop log on at least Linux (BlueZ), how to run `scripts/parse_btsnoop.py` on it, and that the capture should be attached to the device report.

#### Scenario: Capture instructions present

- **WHEN** a tester's device fails at connect or handshake
- **THEN** the page's failure branch tells them how to record a btsnoop capture and decode it with `scripts/parse_btsnoop.py`

### Requirement: Structured device-report issue form

The repository SHALL provide a GitHub issue form at `.github/ISSUE_TEMPLATE/device-report.yml` with required fields for device model, voltkeeper version, OS and Bluetooth adapter, device firmware/`protocolVer`, the verify report, and a dropdown claiming `HARDWARE_TESTING` or `HARDWARE_VERIFIED` with each option's criteria stated inline. The form SHALL note that verify reports are already scrubbed of serial numbers.

#### Scenario: Form enforces required fields

- **WHEN** a tester opens a device report on GitHub
- **THEN** the form requires model, voltkeeper version, OS/adapter, and firmware fields before submission

#### Scenario: Tier claim shows its criteria

- **WHEN** the tester selects a claimed support tier in the form
- **THEN** the dropdown options state the promotion bar for each tier

### Requirement: Checklist is linked from discovery surfaces

The "Test your device" page SHALL be linked from the support-tiers page's promotion section, from the README "Tested devices" section, and from the `voltkeeper scan` contribution hint URL.

#### Scenario: Scan hint targets the checklist

- **WHEN** `voltkeeper scan` finds a device that is not `HARDWARE_VERIFIED`
- **THEN** the printed hint URL points at the "Test your device" page

#### Scenario: README funnels to the checklist

- **WHEN** reading the README "Tested devices" section
- **THEN** it links the "Test your device" page as the way to contribute a device report
