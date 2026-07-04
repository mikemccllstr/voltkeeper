## Why

The first EL100V2 ground-truth session (2026-07-04) produced unusable actuation data because every prompt assumed the operator already knew what the tool was doing: prompts didn't say whether the AC or DC output was being switched, didn't distinguish the Bluetti unit from the appliance plugged into it, and gave no hint where to look on the device — so even voltkeeper's co-author answered "n" to every actuate-and-confirm check. The overload prompt also stated a wrong rated output (100 W for an 1800 W device), the firmware prompt didn't say which of the app's several version numbers to report, and the AC-frequency actuation carried none of the user manual's caution.

## What Changes

- Every ground-truth prompt is rewritten for a target operator who is an enthusiastic volunteer with zero familiarity with the process or the hardware: verbose, explains what to expect, names the exact output/port involved, and uses standard terminology ("the Bluetti unit" vs. "your appliance / the load").
- Actuate-and-confirm checks follow a five-beat script: announce the upcoming change → describe what to watch for (on the unit's display and on any connected appliance) → ready gate (Enter to proceed, skip option) → perform the write → ask for the observed result with `y / n / unsure` (unsure recorded distinctly, not as a denial).
- Prompt content is driven by a shared V2-family field-metadata table (plain-language name, what it affects, where the change shows on the device UI) with per-model overrides — same pattern as the shared ChargingMode enum in `v2_base`.
- Device classes gain manual-sourced hardware specs (initially rated AC output watts) used by prompts; the induced-overload prompt computes its suggested load from the device's actual rating instead of hardcoded prose (EL100V2: 1800 W, not 100 W).
- The AC output frequency actuation replicates the user manual's caution (appliance damage risk, unplug loads first) and becomes opt-in (default skip).
- The firmware observation prompt names the specific version to read (ARM, shown as e.g. "2186.14") and where the app/device displays it.

## Capabilities

### New Capabilities

- `operator-prompt-metadata`: shared per-field prompt metadata table with per-model overrides, and manual-sourced per-model hardware specs consumed by prompt text.

### Modified Capabilities

- `verify-ground-truth`: the passive-observation, actuate-and-confirm, and induced-condition requirements gain the novice-operator prompt standard, the five-beat actuation script with `unsure` outcome, the frequency caution, and the computed overload suggestion.

## Impact

- `src/voltkeeper/core/ground_truth.py` — prompt construction, actuation flow, INDUCED_CHECKS.
- New metadata module (shared table + override mechanism) under `src/voltkeeper/core/`.
- Device classes (`v2_base.py`, `el100v2.py`, others with ground-truth support) — rated-spec attributes and any per-model prompt overrides.
- `docs/verify.md` — ground-truth session description and terminology.
- Tests for metadata resolution, prompt text assembly, and the y/n/unsure outcome recording.
