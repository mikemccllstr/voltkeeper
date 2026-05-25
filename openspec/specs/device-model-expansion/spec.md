## ADDED Requirements

### Requirement: Device registry includes new v3.0.9 models

The system SHALL add device class definitions for the 5 new device models introduced in APK v3.0.9: AORA100_MINI, AORA30_MINI, AORA200_MINI, HB500S, and BH500E. Each SHALL be added to the `_device_registry()` in `bluetooth/__init__.py` and importable from the devices package.

#### Scenario: AORA100_MINI is in the registry
- **WHEN** a BLE device with name prefix "AORA100_MINI" is scanned
- **THEN** `build_device("AORA100_MINI12345")` returns an `Aora100Mini` instance

#### Scenario: HB500S is in the registry
- **WHEN** a BLE device with name prefix "HB500S" is scanned
- **THEN** `build_device("HB500S1234567890123")` returns an `HB500S` instance

### Requirement: AORA mini devices share a base class

The three AORA mini models (AORA100_MINI, AORA30_MINI, AORA200_MINI) SHALL share a common base class `AoraMiniBase` that inherits from `BluettiDevice`. Individual model classes SHALL inherit from `AoraMiniBase` and override only model-specific attributes (type string, model number).

#### Scenario: AORA mini base class defines shared layout
- **WHEN** inspecting `AoraMiniBase`
- **THEN** it inherits from `BluettiDevice`
- **THEN** it defines the protocol version and register blocks common to all AORA mini models

#### Scenario: Individual AORA mini models are thin subclasses
- **WHEN** inspecting `Aora100Mini`
- **THEN** it inherits from `AoraMiniBase`
- **THEN** it overrides only `type = "AORA100_MINI"` and minimal model-specific attributes

### Requirement: Battery pack devices share a base class

The HB500S and BH500E battery pack models SHALL share a common base class `BatteryPackBase` that inherits from `BluettiDevice`. This base class SHALL define the register layout specific to battery pack devices (distinct from both V1Base and V2Base power station layouts).

#### Scenario: BatteryPackBase defines pack-specific layout
- **WHEN** inspecting `BatteryPackBase`
- **THEN** it inherits from `BluettiDevice`
- **THEN** it defines PACK_MAIN_INFO, PACK_ITEM_INFO, and PACK_BMU_INFO register blocks
- **THEN** it does NOT reference inverter-specific blocks (INV_PV_INFO, INV_GRID_INFO, etc.)

#### Scenario: HB500S inherits pack layout
- **WHEN** inspecting `HB500S`
- **THEN** it inherits from `BatteryPackBase`
- **THEN** it overrides `type = "HB500S"` and model-specific attributes

### Requirement: Device name regex matches new model prefixes

The `_DEVICE_NAME_SN_RE` regex in `bluetooth/__init__.py` SHALL be extended to match all new model prefixes: `AORA100_MINI`, `AORA30_MINI`, `AORA200_MINI`, `HB500S`, `BH500E`.

#### Scenario: AORA model name matches
- **WHEN** a BLE device advertises name "AORA100_MINI20250101001"
- **THEN** the regex matches with group(1)="AORA100_MINI"

#### Scenario: Battery pack model name matches
- **WHEN** a BLE device advertises name "HB500S1234567890123"
- **THEN** the regex matches with group(1)="HB500S"

### Requirement: New device models marked as hardware-unverified

All new device class files (AORA mini base, individual AORA models, BatteryPackBase, HB500S, BH500E) SHALL include `# TODO(hardware): verify against physical device` comments at the top of the class definition, following the existing convention for untested models.

#### Scenario: New device classes have TODO comments
- **WHEN** inspecting any new device class file
- **THEN** the class definition includes a `# TODO(hardware):` comment
