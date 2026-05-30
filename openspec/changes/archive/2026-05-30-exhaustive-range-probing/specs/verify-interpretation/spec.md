## ADDED Requirements

### Requirement: verify interpretation guide exists in the documentation

The project SHALL include a `docs/source/user-guide/verify-interpretation.md` document that explains how to read a tier 3 verify output file and how to use findings to update device models. The guide SHALL be written for two audiences: human developers and Claude/agent instances acting on verify results.

#### Scenario: Guide is reachable from the user guide index

- **WHEN** a user reads the documentation
- **THEN** `docs/source/user-guide/index.md` contains a link to `verify-interpretation.md`

### Requirement: interpretation guide explains all tier 3 numeric output fields

The guide SHALL define every field in the tier 3 numeric summary output and state what each field means for model update decisions. It SHALL explain the `probe_cap_hit` flag, the `in_range_rejected` anomaly list, the distinction between `probed_range` and `discovered_range`, and the `declared_range` vs `discovered_range` comparison.

#### Scenario: Reader can determine whether upper bound is confirmed

- **WHEN** a reader (human or agent) reads the guide
- **THEN** the guide explains that `probe_cap_hit: true` means the upper bound is "at least 255, possibly higher" and SHALL NOT be written as a confirmed upper bound in the device model without further investigation

#### Scenario: Reader understands that range discrepancies are findings

- **WHEN** a reader sees `range_discrepancy: true` in a verify report
- **THEN** the guide explains this is a discovery, not a test failure, and describes when it is safe to update the declared range

### Requirement: interpretation guide provides a step-by-step model update workflow

The guide SHALL include a numbered step-by-step procedure that a Claude/agent instance can follow to update a device model file based on a verify report. The procedure SHALL cover: locating the field in the device model, interpreting `discovered_range` vs `declared_range`, handling `probe_cap_hit: true`, handling `in_range_rejected`, and the commit message convention for model updates derived from verify findings.

#### Scenario: Agent can update a field's declared range

- **WHEN** a Claude/agent instance reads the guide and a verify report showing `discovered_range: [3, 4]` for `dc_eco_auto_off_time` (no declared range)
- **THEN** the guide instructs the agent to add `range=(3, 4)` to the field definition and reference the verify file in the commit message

#### Scenario: Agent handles uncertain upper bound correctly

- **WHEN** a verify report shows `probe_cap_hit: true` and `discovered_range: [0, 255]` for a field declared as `(0, 100)`
- **THEN** the guide instructs the agent NOT to update the declared range to `(0, 255)` without further investigation, and to add a comment noting the finding

### Requirement: interpretation guide documents the contiguous range assumption

The guide SHALL state that the exhaustive sweep algorithm assumes accepted values form a single contiguous interval, explain the early termination rule that follows from this assumption, and note that a device violating this assumption would produce incomplete findings.

#### Scenario: Reader understands early termination

- **WHEN** a verify report shows `probed_range: [0, 12]` and `discovered_range: [5, 10]`
- **THEN** the guide explains that the sweep stopped at 12 because values 11 and 12 were both rejected after the last accept at 10, and that — given the contiguous assumption — values 13–255 are inferred to also be rejected
