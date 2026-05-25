## Context

Voltkeeper supports V1 and V2 Bluetti device protocols over BLE with an inheritance model: `BluettiDevice` → `V1Base`/`V2Base` → per-model classes. A cross-reference of Bluetti's official App Features Guide blog post against the APK v3.0.9 source revealed registers and device models present in the APK but absent from voltkeeper. The APK is the authoritative source for register addresses and value semantics; the blog post confirmed the user-facing behavior.

## Goals / Non-Goals

**Goals:**
- Add WORKING_MODE register (3001/2005) with a `WorkingMode` enum replacing the boolean-only UPS_MODE understanding
- Add Child Lock registers (2072, 2076) with level semantics and feature-gating
- Document SYSTEM_POWER_OFF multi-value encoding and add sleep register constants
- Add AC180 base device class for the AC180/PLP022 portable power station family
- Add EL10V2, EL30V2, and EL400 device classes to the registry
- Update protocol docs with new register value mappings
- Test all new writable fields with fabricated data derived from APK parser structures

**Non-Goals:**
- D400S (SolarX 4K) or B500K support (tabled for separate change — different device category)
- OTA firmware update support (out of scope for voltkeeper)
- Cloud/MQTT-only features (weather alerts, carbon tracking, AI energy management)
- Real hardware verification (will test with fabricated data; hardware testing deferred)

## Decisions

### Decision 1: WORKING_MODE is an EnumField, not a BoolField

UPS_MODE (3035) is the Online/Standby sub-toggle — correctly implemented as a BoolField. WORKING_MODE (3001/2005) is the broader strategy selector with 6+ values. It must be an EnumField.

**Rationale**: The APK `WorkingMode` enum has values 1-5 and 11. UPS_MODE at 3035 has only 0/1. These are two distinct registers serving different purposes. The blog post conflated them; the APK clarifies.

**Alternatives considered**: Adding more values to the existing UPS_MODE field. Rejected because they're different registers at different addresses.

### Decision 2: Child Lock 2072 uses bitfield write logic

Register 2072 uses bit 5 for ON (value 32) and bit 4 for OFF (value 16) — not a simple 0/1. We need to handle this at the write level.

**Rationale**: The APK `DeviceSettingsChildLockActivity.java:90` shows: `addSetTask(2072, i == 0 ? 1 << 5 : 1 << 4)`. Writing 0 to turn off would write to bit 4, not clear the register — this must be preserved.

**Implementation**: Expose `child_lock` as a BoolField at 2072, but override the write in `build_setter_command` to map True → 0x20 (bit 5), False → 0x10 (bit 4). Register 2076 uses simple integer values (1 or 2).

### Decision 3: AC180 gets its own base class (not V2Base)

AC180 creates a `new DeviceFunction(DeviceCategory.PORTABLE_POWER, ...)` with specific writable registers that differ from the ELITE200_V2 family. PLP022 and EL10V2 inherit from AC180.

**Rationale**: The APK inheritance chain is AC180 → PLP022 → EL10V2. AC180 has writable features (gridPlusModeCtrl, invFrequency, factoryReset, childLockCtrl) not present on all V2Base devices. EL10V2 adds dcInputSourceExtensions, checkInvStatus2ACFreqSet, socHighLimited, voltSet5521. In voltkeeper terms, AC180 extends V2Base with its specific writable fields; EL10V2 extends AC180.

**Alternatives considered**: Making EL10V2 extend V2Base directly. Rejected because AC180 and PLP022 are distinct device models customers own; having a class for them is valuable for future support even if EL10V2 is the immediate target.

### Decision 4: EL30V2 and EL400 extend V2Base (ELITE200_V2 family)

EL30V2 shares a code block with EL100V2 in the APK — literally the same `if` branch. EL400 is in a sibling block with EL320/AORA320. Both use ELITE200_V2 as base template.

**Rationale**: These devices use the same register layout as EL100V2 (already implemented). The differences are minor feature flag toggles: EL30V2 adds `checkInvStatus2ACFreqSet=true`; EL400 adds `remotePowerCtrl=true`, `sysSleepConditions`, `packAging=true`, `socHighLimited=true`. We can subclass EL100V2 or create siblings that add the extra fields.

**Implementation**: EL30V2 can extend V2Base with the same register set as EL100V2 plus the unique flag (if it maps to a writable register). EL400 extends V2Base with the EL100V2 set plus `remote_power_ctrl` and `sys_power_conditions` fields.

### Decision 5: SYSTEM_POWER_OFF keeps current behavior; sleep registers are separate writable fields

The blog and APK confirm SYSTEM_POWER_OFF (2013/3060) accepts values 1-4. Our existing `shutdown` command writes value 1 — that's correct. We'll document the full encoding and add separate writable fields for sleep mode (`sleep_enable` → writes value 4), remote startup SOC (2074), and sleep power threshold (2079).

**Rationale**: The shutdown command shouldn't change semantics. Sleep mode is a different user intent and warrants its own field.

### Decision 6: Fabricated test data from APK parser offsets

New device classes (AC180, EL10V2, EL30V2, EL400) will be tested with fabricated hex response data constructed by tracing APK parser field offsets. This is the same approach we used for EL100V2.

**Rationale**: We don't have physical hardware for these models. The APK parser code precisely documents field positions and types. Fabricated data that exercises each parser branch provides useful regression protection.

## Risks / Trade-offs

- **[Risk] No hardware verification for new device models** → Mitigation: all new classes marked with `# TODO(hardware): verify against physical device` comments; fabricated test data exercises parser paths
- **[Risk] EL10V2 voltage (25V) differs from AC180 (56V)** → Mitigation: `DEFAULT_PACK_VOLTAGE_SCALE` is already overrideable per device class; EL10V2 sets its own voltage scale
- **[Risk] Child Lock bitfield at 2072 might interact with other bits in the register** → Mitigation: read-modify-write if the APK shows other bits are used; otherwise, write the specific bit value (16 or 32) since the APK writes these values directly without reading first
- **[Risk] WORKING_MODE register semantics on devices that don't support all modes** → Mitigation: all 6 enum values are always exposed; unsupported modes will be NACK'd by the device firmware — same behavior as the official app's read-then-write pattern
