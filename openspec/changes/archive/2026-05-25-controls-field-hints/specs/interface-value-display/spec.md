## MODIFIED Requirements

### Requirement: CLI verbose display adds unit suffixes

The CLI verbose output SHALL append unit suffixes to fields whose `UintField.unit` attribute is set. The source of truth for which fields carry which unit is the device's control struct definition, not a hardcoded name list in the display layer.

This broadens coverage to include the AC200L, AC300, and AC500 naming variants (`eco_off_time` → `h`, `eco_auto_off` → `h`) which were previously omitted.

#### Scenario: ECO timeout shown with hours suffix
- **WHEN** CLI verbose output renders `ac_eco_auto_off_time = 4` (any device)
- **THEN** the display shows `"4h"`

#### Scenario: ECO power shown with watts suffix
- **WHEN** CLI verbose output renders `dc_eco_power = 10` (any device)
- **THEN** the display shows `"10W"`

#### Scenario: AC300 eco_off_time shown with hours suffix
- **WHEN** CLI verbose output renders `eco_off_time = 2` on an AC300
- **THEN** the display shows `"2h"`

#### Scenario: AC200L eco_auto_off shown with hours suffix
- **WHEN** CLI verbose output renders `eco_auto_off = 1` on an AC200L
- **THEN** the display shows `"1h"`

#### Scenario: Fields with no unit are unaffected
- **WHEN** CLI verbose output renders `lcd_timeout = 30`
- **THEN** the display shows `"30"` with no suffix
