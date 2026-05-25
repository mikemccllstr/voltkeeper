## ADDED Requirements

### Requirement: EL10V2 device model added to registry

The `_device_registry()` in `bluetooth/__init__.py` SHALL include `"EL10V2"` → `EL10V2` mapping. The device name regex SHALL match `EL10V2` prefix.

#### Scenario: EL10V2 in registry and regex
- **WHEN** a BLE device advertises as "EL10V225010101001"
- **THEN** `build_device(...)` returns an `EL10V2` instance

### Requirement: EL30V2 device model added to registry

The `_device_registry()` in `bluetooth/__init__.py` SHALL include `"EL30V2"` → `EL30V2` mapping. The device name regex SHALL match `EL30V2` prefix.

#### Scenario: EL30V2 in registry and regex
- **WHEN** a BLE device advertises as "EL30V225010101001"
- **THEN** `build_device(...)` returns an `EL30V2` instance

### Requirement: EL400 device model added to registry

The `_device_registry()` in `bluetooth/__init__.py` SHALL include `"EL400"` → `EL400` mapping. The device name regex SHALL match `EL400` prefix.

#### Scenario: EL400 in registry and regex
- **WHEN** a BLE device advertises as "EL40025010101001"
- **THEN** `build_device(...)` returns an `EL400` instance

### Requirement: Device model documentation updated

The `device-models.md` protocol documentation SHALL be updated to include EL10V2 (model #62, 25V), EL30V2 (model #32, 25V), EL400 (model #29, 56V), AC180 (model #23, 56V), and PLP022 (model #7, 56V) entries with their protocol version and feature support notes.

#### Scenario: New models in device-models.md
- **WHEN** reading `device-models.md`
- **THEN** EL10V2, EL30V2, EL400, AC180, and PLP022 are listed with correct model numbers and voltages
