# Design: Verify Ground Truth Mode (sketch)

> **Status: sketch.** Decisions below are provisional; the open questions at the bottom gate implementation.

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

## Decisions (provisional)

### 1. The device UI is the primary ground-truth source

Prompts ask what the device's own screen shows, not the app. This sidesteps BLE exclusivity entirely and makes the session face-to-face with the hardware by design. If the bench test shows the app can display live data concurrently (cloud path), app observations become an optional secondary source — an additive revision, not a redesign.

### 2. Three interaction classes, in escalating involvement

1. **Observe**: "What SoC does the device show?" → record `{field, observed, parsed, raw_ref, match}`.
2. **Actuate and confirm**: tool writes a value ("switching charging mode to TURBO"), operator confirms the device UI reflects it → record `{field, wrote, device_confirmed}`. A denial with a readback match is the signature of a label swap — exactly the TURBO/SILENT case.
3. **Induce and capture**: operator creates a designed-protection condition (e.g., plug in a load above the device's rating), tool snapshots alarm/fault registers and raw HOME hex during the event → validates alarm-bit decoding that is otherwise untestable without a fault. Typed confirmation required, tier-6 style, and each induced check documents why it is within designed protections.

### 3. Tolerance and scale inference for numeric observations

Numeric comparisons carry a per-quantity tolerance (voltage ±2 V, watts ±10 % or ±10 W, SoC ±1). Beyond match/mismatch, the comparator tries candidate decimal scales (×1, ÷10, ÷100) against the raw register value: observed 121 V against raw `1210` reports "matches at ÷10 (decivolts)". This turns a mismatch from a dead end into the answer — the mechanism that would have caught the AC2A pack-voltage scale on the first session.

### 4. Prompt script is derived, with a curated observation list

The actuate-and-confirm set derives from the device's writable enum/bool fields (skip-listed like verify's SKIP_AUTO). The observe set is a curated core list (SoC, charging mode, AC/DC state, AC output voltage, load watts, firmware versions) — small enough that a session stays tolerable. Everything is skippable; a skipped prompt records `skipped`, never blocks the run.

### 5. Results live in the verify report's `ground_truth` section

Same file as the raw capture (`verify-raw-capture`), so one session yields one artifact: raw bytes, parsed values, and operator observations cross-referenced. No separate report format.

## Risks / Trade-offs

- [Operator burden makes sessions rare] → opt-in, skippable prompts, curated core list; the mode is for characterization sessions (new device, new firmware, suspected bug), not routine verification.
- [Observation noise causes false mismatches] → tolerances per quantity; report records both values so a human adjudicates borderline cases rather than the tool asserting failure.
- [Induced-condition checks carry physical risk] → restricted to designed protections, typed confirmation, documented rationale per check; anything that risks damage or requires defeating a protection is out of scope permanently.
- [Device UI may not display some quantity we want to anchor] → prompts allow "not shown on device"; those fields simply stay unanchored (status quo).

## Open Questions

- **App/BLE concurrency**: can the vendor app show live data (cloud path) while voltkeeper holds BLE? Test at the next bench session. Determines whether app observations become a secondary source.
- **Device UI coverage**: inventory what the EL100V2 (and AC2A) screens actually display — which core-list fields are anchorable at all.
- **Flag vs. subcommand**: `verify --ground-truth` reusing the tier flow, or a standalone attended command? Leaning flag, but the induce-and-capture class may fit awkwardly inside the tier sequence.
- **Which induced conditions are worth scripting**: AC overload is the obvious first; anything else (DC overload? low-battery cutoff?) needs a per-condition safety argument.
- **Re-evaluation gate**: revisit this whole sketch after `verify-raw-capture` is implemented and one EL100V2 bench session has been run manually — the manual session is the prototype for what the prompts should ask.
