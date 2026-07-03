## ADDED Requirements

### Requirement: Every device model has a support tier

`BluettiDevice` SHALL define a `SUPPORT_TIER` class attribute of enum type `SupportTier` with members `HARDWARE_VERIFIED`, `HARDWARE_TESTING`, and `APK_DERIVED`. The default SHALL be `APK_DERIVED`, so a model class that does not override it is labeled as untested. `AC2A` SHALL override the tier to `HARDWARE_VERIFIED` and `El100V2` SHALL override it to `HARDWARE_TESTING`.

#### Scenario: Unverified model inherits the default tier

- **WHEN** a registry model class does not override `SUPPORT_TIER`
- **THEN** its `SUPPORT_TIER` is `SupportTier.APK_DERIVED`

#### Scenario: Hardware-verified model

- **WHEN** inspecting `AC2A.SUPPORT_TIER`
- **THEN** the value is `SupportTier.HARDWARE_VERIFIED`

#### Scenario: Hardware-testing model

- **WHEN** inspecting `El100V2.SUPPORT_TIER`
- **THEN** the value is `SupportTier.HARDWARE_TESTING`

### Requirement: Scan output shows the support tier

`voltkeeper scan` SHALL display each discovered device's support tier alongside the existing encryption flag. When a discovered model's tier is not `HARDWARE_VERIFIED`, the scan output SHALL include a one-line hint pointing at the device-testing contribution path. Devices whose name matches no registry prefix SHALL be displayed without a tier rather than erroring.

#### Scenario: Verified model in scan output

- **WHEN** a scan finds a device named `AC2A2305000123456`
- **THEN** the result line includes a tier label indicating it is verified on hardware

#### Scenario: Untested model shows tier and contribution hint

- **WHEN** a scan finds a device whose model class has `SUPPORT_TIER == APK_DERIVED`
- **THEN** the result line includes a label indicating the model is APK-derived and untested
- **THEN** the scan output includes a hint referencing how to help verify the device

#### Scenario: Unknown device name prefix

- **WHEN** a scan finds a BLE device whose name matches no registry prefix
- **THEN** the result is displayed without a tier label and no exception is raised

### Requirement: Docs surface per-model support tiers

The model tables in `docs/source/protocol/device-models.md` SHALL include a Support column stating each model's tier. A user-guide page SHALL define the three tiers and the promotion criteria: `APK_DERIVED` → `HARDWARE_TESTING` when core flows (connect, handshake where applicable, live-data parse) are confirmed on a real unit, and `HARDWARE_TESTING` → `HARDWARE_VERIFIED` when a full `voltkeeper verify` run passes on real hardware. The page SHALL be reachable from the user-guide navigation.

#### Scenario: Model tables carry a Support column

- **WHEN** reading the device model tables in the protocol docs
- **THEN** every model row states its support tier

#### Scenario: Tier definitions page exists in the nav

- **WHEN** building the docs
- **THEN** a user-guide page defines all three tiers and their promotion criteria
- **THEN** the page appears in the user-guide toctree

### Requirement: Docs and code tiers cannot drift

The test suite SHALL include a test that parses the model tables in `docs/source/protocol/device-models.md` and asserts that every registry model appears in the tables exactly once and that each documented tier equals the model class's `SUPPORT_TIER`.

#### Scenario: Documented tier disagrees with code

- **WHEN** a model's Support cell in device-models.md does not match its class's `SUPPORT_TIER`
- **THEN** the consistency test fails, naming the model

#### Scenario: Registry model missing from docs

- **WHEN** a model exists in `_device_registry()` but appears in no model table
- **THEN** the consistency test fails, naming the model
