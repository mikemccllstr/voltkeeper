## MODIFIED Requirements

### Requirement: Scan output shows the support tier

`voltkeeper scan` SHALL display each discovered device's support tier alongside the existing encryption flag. When a discovered model's tier is not `HARDWARE_VERIFIED`, the scan output SHALL include a one-line hint whose URL points at the "Test your device" user-guide page. Devices whose name matches no registry prefix SHALL be displayed without a tier rather than erroring.

#### Scenario: Verified model in scan output

- **WHEN** a scan finds a device named `AC2A2305000123456`
- **THEN** the result line includes a tier label indicating it is verified on hardware

#### Scenario: Untested model shows tier and contribution hint

- **WHEN** a scan finds a device whose model class has `SUPPORT_TIER == APK_DERIVED`
- **THEN** the result line includes a label indicating the model is APK-derived and untested
- **THEN** the scan output includes a hint whose URL points at the "Test your device" page

#### Scenario: Unknown device name prefix

- **WHEN** a scan finds a BLE device whose name matches no registry prefix
- **THEN** the result is displayed without a tier label and no exception is raised

### Requirement: Docs surface per-model support tiers

The model tables in `docs/source/protocol/device-models.md` SHALL include a Support column stating each model's tier. A user-guide page SHALL define the three tiers and the promotion criteria: `APK_DERIVED` → `HARDWARE_TESTING` when core flows (connect, handshake where applicable, live-data parse) are confirmed on a real unit, and `HARDWARE_TESTING` → `HARDWARE_VERIFIED` when verify stages 1–3 pass and stage 4 passes under a connected load on real hardware (stages 5–6 optional). The promotion section SHALL link the "Test your device" walkthrough. The page SHALL be reachable from the user-guide navigation.

#### Scenario: Model tables carry a Support column

- **WHEN** reading the device model tables in the protocol docs
- **THEN** every model row states its support tier

#### Scenario: Tier definitions page exists in the nav

- **WHEN** building the docs
- **THEN** a user-guide page defines all three tiers and their promotion criteria
- **THEN** the page appears in the user-guide toctree

#### Scenario: Promotion bar is the pinned stage 1–4 criterion

- **WHEN** reading the promotion criteria on the support-tiers page
- **THEN** `HARDWARE_VERIFIED` requires verify stages 1–3 passing plus stage 4 under a connected load, with stages 5–6 listed as optional
- **THEN** the criteria link the "Test your device" walkthrough
