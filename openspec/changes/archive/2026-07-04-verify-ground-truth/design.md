# Design: Verify Ground Truth Mode

> **Status: ready for implementation.** The group-0 open questions are answered below; the interface decision (flag) has Mike's sign-off (2026-07-04).

## Context

Write/readback verification cannot detect wrong interpretation: swapped enum labels, wrong decimal scales, misassigned registers. External references can — and two are reliably available:

- **The device's own UI**: comprehensive on most models, and crucially it stays live while voltkeeper holds the BLE connection. Ground truth does not depend on the vendor app.
- **The physical setup**: a wired fan or lightbulb is a steady, known AC load; a DC charger or 12 V supply is a steady charge source; AC line voltage is stable. In a deliberate bench setup, observation volatility is low — the noise is bounded (±1–2 V, a few watts), not structural.

The vendor app is a third reference if the device supports a concurrent app connection (via cloud/IoT while we hold BLE) — doubtful, to be tested, and the design must not depend on it.

## Goals / Non-Goals

**Goals:**

- Durable, structured record of operator-observed device state next to parsed values and raw hex.
- Catch interpretation errors: enum label swaps, decimal-scale errors, register misassignment.
- Repeatable protocol for new-device bring-up and firmware-revision re-characterization.

**Non-Goals:**

- No dependence on the vendor app being connectable during the session.
- No unattended operation — this mode is definitionally hands-on; `--yes` runs never enter it.
- No unsafe induced conditions — nothing outside the device's designed protections.
- Not a replacement for verify's existing tiers; it layers on top of them.

## Decisions

### 1. The device UI is the primary ground-truth source

Prompts ask what the device's own screen shows, not the app. This sidesteps BLE exclusivity entirely and makes the session face-to-face with the hardware by design. If the bench test shows the app can display live data concurrently (cloud path), app observations become an optional secondary source — an additive revision, not a redesign.

### 2. Three interaction classes, in escalating involvement

1. **Observe**: "What SoC does the device show?" → record `{field, observed, parsed, raw_ref, match}`.
2. **Actuate and confirm**: tool writes a value ("switching charging mode to TURBO"), operator confirms the device UI reflects it → record `{field, wrote, device_confirmed}`. A denial with a readback match is the signature of a label swap — exactly the TURBO/SILENT case.
3. **Induce and capture**: operator creates a designed-protection condition (e.g., plug in a load above the device's rating), tool snapshots alarm/fault registers and raw HOME hex during the event → validates alarm-bit decoding that is otherwise untestable without a fault. Typed confirmation required, tier-6 style, and each induced check documents why it is within designed protections.

### 3. Tolerance and scale inference for numeric observations

Numeric comparisons carry a per-quantity tolerance (voltage ±2 V, watts ±10 % or ±10 W, SoC ±1). Beyond match/mismatch, the comparator tries candidate decimal scales (×1, ÷10, ÷100) against the raw register value: observed 121 V against raw `1210` reports "matches at ÷10 (decivolts)". This turns a mismatch from a dead end into the answer — the mechanism that would have caught the AC2A pack-voltage scale on the first session.

### 4. Prompt script is derived, with a curated observation list

The actuate-and-confirm set derives from the device's writable enum/bool fields (skip-listed like verify's SKIP_AUTO), gated by the same FIELD_TIERS risk classification the tiers use: tier-6 (irreversible) fields are never actuated, and tier-4/5 fields are actuated only when the operator consented to that tier during the run — the write precedes the confirmation prompt by design, so consent must come from the tier gate, not the prompt. The observe set is a curated core list matching what the device screens actually show (SoC, total output/input watts, AC/DC output state, AC output frequency, charging mode, firmware versions where on-screen — charge/discharge direction was dropped: its parsed field is a bare uint with no validated label mapping to compare an operator's answer against, and direction is already triangulated by the watt totals and charging-mode checks); voltages are a separate secondary-source class (multimeter or pre/post-session app screenshot) since neither LCD displays any voltage. Small enough that a session stays tolerable. Everything is skippable; a skipped prompt records `skipped`, never blocks the run.

### 5. Results live in the verify report's `ground_truth` section

Same file as the raw capture (`verify-raw-capture`), so one session yields one artifact: raw bytes, parsed values, and operator observations cross-referenced. No separate report format.

### 6. Ground-truth mode is a flag: `verify --ground-truth`

Not a standalone subcommand (Mike sign-off, 2026-07-04). The manual prototype session fit naturally around a normal verify run, decision 5 already puts results in the verify report, and a separate command would duplicate the connection/tier/report plumbing. The induce-and-capture class runs as a distinct phase after the tiers — it is gated behind typed confirmation either way, so its awkwardness inside the tier sequence is avoided by ordering, not by a separate command. The phase runs after whatever tiers execute, including under a `--tier` limit: observations and induced checks need only the tier-1 capture, and the tier-consent gate (decision 4) already handles actuations — a tier that never ran was never consented.

## Risks / Trade-offs

- [Operator burden makes sessions rare] → opt-in, skippable prompts, curated core list; the mode is for characterization sessions (new device, new firmware, suspected bug), not routine verification.
- [Observation noise causes false mismatches] → tolerances per quantity; report records both values so a human adjudicates borderline cases rather than the tool asserting failure.
- [Induced-condition checks carry physical risk] → restricted to designed protections, typed confirmation, documented rationale per check; anything that risks damage or requires defeating a protection is out of scope permanently.
- [Device UI may not display some quantity we want to anchor] → prompts allow "not shown on device"; those fields simply stay unanchored (status quo).

## Open Questions

- **App/BLE concurrency**: ANSWERED (EL100V2 bench, 2026-07-03) — no. While voltkeeper held BLE, the Android app's device scan did not show the EL100V2 (it reappeared after disconnect), and the cloud path was inactive (`mqtt_status: false`). The device accepts one BLE session at a time; app observations stay out of the design (decision 1 stands).
- **Device UI coverage**: ANSWERED (official user manuals, `bluetti-files/manuals/`: Elite 100 V2 manual V2.1 §3.2 "LCD Display" + §6 "View Device Information"; AC2A manual V3.0 §6 "LCD Display") — see "Device-screen inventory" below.
- **Flag vs. subcommand**: ANSWERED — flag; see decision 6.
- **Which induced conditions are worth scripting**: AC overload only for now; anything else (DC overload? low-battery cutoff?) needs a per-condition safety argument before being added.
- **Re-evaluation gate**: CLOSED — `verify-raw-capture` landed, the 2026-07-03 EL100V2 bench session served as the manual prototype, and its lessons are reflected in the spec (totals-vs-sums, alternating values, secondary-source voltages, display-format firmware comparison, `not_confirmable_on_device`).

## Device-screen inventory (task 0.2, from official manuals)

Both LCDs share one layout family: total INPUT W, total OUTPUT W, SoC % (digits + ring), remaining time (h), AC output frequency (50/60 Hz), and status/alarm icons. Sources: Elite 100 V2 user manual V2.1 (§3.2, §5.1, §6), AC2A user manual V3.0 (§6) — `bluetti-files/manuals/`.

| Core-list field | EL100V2 LCD | AC2A LCD | Anchorable? |
| --- | --- | --- | --- |
| SoC % | yes (digits + ring) | yes | yes |
| Output watts | total AC+DC only | total only | yes, vs. sum of parsed AC+DC outputs |
| Input watts | total only (AC-input/DC-input source icons, no split) | total only (GRID / PV icons) | yes, vs. sum of parsed grid+PV inputs |
| AC / DC output state | on/off icons | on/off icons | yes |
| AC output frequency | 50Hz/60Hz indicator | same | yes (coarse) |
| Charging mode | Turbo icon; full mode readable in Settings Mode page P03 (Standard/Turbo settable on-device; Silent activated via app only) | Turbo icon only; mode set via app | partial — Turbo icon alone can't distinguish Standard from Silent; EL100V2 needs the P03 page for that |
| Firmware version | yes — device-info "Version" page (Settings Mode, long-press DC on P01) | not shown | EL100V2 only |
| Serial number | yes — device-info SN page | not shown | EL100V2 only |
| Voltages (AC out, grid, pack) | **not shown anywhere** | **not shown anywhere** | no — needs multimeter or pre/post-session app screenshots |
| Battery charge/discharge direction | arrow icons | arrow icons + progress bar | yes |
| Alarms/faults | Temp Alert, Overload, Short Circuit, System Fault icons; Error Code + Fault History pages | High Temp, Overload, Overcurrent, Fault icons | yes — induce-and-capture can be device-confirmed |

Design consequences:

1. **Voltage anchoring cannot come from the device screen.** Scale-inference (decision 3) still works, but the observation source for voltages is a multimeter or app screenshots taken before/after the session (BLE exclusivity blocks during). Decision 1's "device UI is primary" stands, with the physical setup / pre-session app captures as the documented secondary source for voltage-class quantities.
2. **Watt prompts must compare against sums**, not per-port parsed fields — the LCDs only show totals. Grid-draw totals can legitimately alternate between AC-only and AC+DC levels (battery-supplied DC bus with periodic grid top-up, observed 2026-07-03: 46 W ↔ 60 W with a 14 W DC load); the prompt needs a "value alternates between levels" answer, not a wider tolerance. The charge/discharge arrow icon is the on-screen witness for which phase the device is in.
3. **The Standard↔Silent leg of actuate-and-confirm is weaker than the Turbo legs** on the main display (no icon difference); on EL100V2 the operator confirms via the P03 settings page, on AC2A it is not device-confirmable at all.
4. **Alarm icons and the EL100V2 fault-history page make induced-condition checks confirmable on-device** — the AC-overload check has both a live icon and a persistent record to prompt for.
5. **Firmware-version prompts are EL100V2-only** (device-info page) and the comparison must apply the display format (raw ÷ 100, e.g. 218614 → "2186.14").
