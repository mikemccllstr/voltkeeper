## MODIFIED Requirements

### Requirement: AC180 device base class

The system SHALL provide an `AC180` device class in `src/voltkeeper/core/devices/ac180.py` that inherits from `V2Base` and defines the writable registers applicable to the AC180/AC180P/PLP022 portable power station family. The class SHALL NOT be registered in the device registry (it is a base class). Voltage SHALL be 56V nominal.

#### Scenario: AC180 inherits V2Base
- **WHEN** inspecting `AC180` class
- **THEN** it inherits from `V2Base`
- **THEN** `protocol_version = 2000`

#### Scenario: AC180 defines writable fields with proper enums
- **WHEN** inspecting AC180's `_build_control_struct()` method
- **THEN** `inv_freq` is defined as `add_enum_field("inv_freq", 2210, InvFrequency)`
- **THEN** `led_color` is defined as `add_enum_field("led_color", 2078, LedColor)` (if applicable per APK flags)
- **THEN** WRITABLE_FIELD_NAMES includes all writable fields

### Requirement: EL10V2 device class

The system SHALL provide an `EL10V2` device class in `src/voltkeeper/core/devices/el10v2.py` that inherits from `V2Base` and customizes for the Elite 10 V2 model (model #62, 25V).

#### Scenario: EL10V2 uses enum fields
- **WHEN** inspecting EL10V2's `_build_control_struct()` method
- **THEN** `inv_freq` is defined as `add_enum_field("inv_freq", 2210, InvFrequency)`
- **THEN** `led_color` is defined as `add_enum_field("led_color", 2078, LedColor)`

### Requirement: EL30V2 device class

The system SHALL provide an `EL30V2` device class in `src/voltkeeper/core/devices/el30v2.py` that inherits from `V2Base` and defines the writable registers for the Elite 30 V2 model (model #32, 25V). The class SHALL mirror the EL100V2 register layout with proper enum fields.

#### Scenario: EL30V2 uses enum fields
- **WHEN** inspecting EL30V2's `_build_control_struct()` method
- **THEN** `inv_freq` is defined as `add_enum_field("inv_freq", 2210, InvFrequency)`
- **THEN** `pv_type_set` is defined as `add_enum_field("pv_type_set", 2060, PvType)`
- **THEN** `pv2_type_set` is defined as `add_enum_field("pv2_type_set", 2061, Pv2Type)`

### Requirement: EL400 device class

The system SHALL provide an `EL400` device class in `src/voltkeeper/core/devices/el400.py` that inherits from `V2Base` and defines the writable registers for the Elite 400 model (model #29, 56V). EL400 SHALL include remote power control and sleep mode support in addition to the standard writable fields.

#### Scenario: EL400 uses enum fields
- **WHEN** inspecting EL400's `_build_control_struct()` method
- **THEN** `inv_freq` is defined as `add_enum_field("inv_freq", 2210, InvFrequency)`
- **THEN** `pv_type_set` is defined as `add_enum_field("pv_type_set", 2060, PvType)`
- **THEN** `pv2_type_set` is defined as `add_enum_field("pv2_type_set", 2061, Pv2Type)`
