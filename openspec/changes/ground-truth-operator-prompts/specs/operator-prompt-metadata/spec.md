## ADDED Requirements

### Requirement: Shared field prompt metadata with per-model overrides

The system SHALL provide a shared V2-family prompt-metadata table mapping writable field names to prompt metadata: a plain-language friendly name, an effect classification (`load` — interrupts power to connected appliances, `unit` — affects only the Bluetti unit's own behaviour or display, `not_visible` — no observable effect), a watch-for description of what the operator should see change, and optional caution text and device-UI location. Device classes MAY declare per-field overrides which take precedence over the shared table. When a field has no metadata in either source, the system SHALL generate a fallback entry from the field name and mark it as generic so prompt text can acknowledge the missing detail rather than assert a wrong specific claim.

#### Scenario: Shared entry used by default
- **WHEN** prompt metadata is resolved for `ac_output` on a V2 device with no override
- **THEN** the shared table entry is returned, naming the AC outlets and describing the load interruption

#### Scenario: Device override wins
- **WHEN** a device class declares an override for a field also present in the shared table
- **THEN** the override entry is returned for that device and the shared entry for all others

#### Scenario: Unknown field gets a marked fallback
- **WHEN** metadata is resolved for a writable field absent from both sources
- **THEN** a generated entry based on the field name is returned, flagged as generic

### Requirement: Prompt terminology distinguishes the unit from the load

All operator-facing prompt text generated from the metadata SHALL use consistent terminology: "the Bluetti unit" for the power station itself, "your appliance" or "the load" for equipment plugged into it, and explicit output names ("the AC outlets", "the DC ports") — never a bare "output" or "device" where the referent is ambiguous.

#### Scenario: Output toggle names the specific outlets
- **WHEN** an actuation prompt is generated for `dc_output`
- **THEN** the text names the DC ports explicitly and does not use the bare word "output" to refer to them

### Requirement: Device classes carry manual-sourced rated specs

Device classes SHALL support a rated AC output attribute (watts), populated per model from the manufacturer's user manual with a citation comment, and left unset when unknown. The EL100V2 rating SHALL be 1850 W. Prompt text that references device ratings SHALL derive its numbers from this attribute and SHALL NOT hardcode per-model wattages in prose.

#### Scenario: EL100V2 rating available to prompts
- **WHEN** the overload prompt is built for an EL100V2
- **THEN** the suggested load is computed from the 1850 W rating

#### Scenario: Unknown rating means no overload offer
- **WHEN** a device class has no rated AC output declared
- **THEN** the induced-overload check is not offered for that device
