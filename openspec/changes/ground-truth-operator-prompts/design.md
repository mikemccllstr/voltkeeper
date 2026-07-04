## Context

Ground-truth prompts are currently terse strings assembled inline in `ground_truth.py` (e.g. "Device set to off (was on) — does the device display confirm this change? (y/n)"). Run 1 on the EL100V2 showed they fail their purpose: the operator couldn't tell which output was being toggled or what "confirm" meant, so every actuation was answered "n", which is indistinguishable in the data from a genuine label-mapping bug. Related defects: `INDUCED_CHECKS` hardcodes "Elite 100 V2 (rated 100W)" (actual: 1850 W), the firmware prompt says "Firmware version" while the app shows ARM/DSP/BMS/IoT versions with no "firmware" label, and the inv_freq actuation carries no appliance-damage caution.

Mike has decided the prompt metadata lives in a **shared V2-family table with per-model overrides** (the same shape as the shared ChargingMode enum decision in `v2_base`). The group-0 device-screen inventory (archived `2026-07-04-verify-ground-truth/design.md`) is the source for where-to-look hints.

## Goals / Non-Goals

**Goals:**
- Prompts a first-time volunteer can act on without knowing voltkeeper, BLE, or the register map.
- An `unsure` outcome so operator confusion is recorded as such instead of poisoning the denial signal.
- Prompt facts (which output, rated watts, where on the screen) come from data, not prose baked into strings.
- Manual-sourced rated specs on device classes, starting with rated AC output watts.

**Non-Goals:**
- No change to which fields are eligible for actuation, tier classification, consent, or restore logic.
- No session reordering, narration, or category skip menus — that is the `verify-session-flow` change.
- No internationalisation; English prompts only.
- No specs beyond what prompts currently need (rated AC output now; the mechanism accommodates more later).

## Decisions

1. **Metadata model**: a `FieldPromptInfo` dataclass per field: `friendly_name` ("the AC outlets"), `affects` (enum: `load` — interrupts power to connected appliances; `unit` — changes the Bluetti unit's own behaviour/display only; `not_visible` — no observable effect), `watch_for` (what the display/appliance does, e.g. "the AC icon on the main screen goes dark and any appliance plugged into the AC outlets loses power"), optional `caution` (shown at the announce beat and requiring explicit opt-in when present), optional `where` (settings page reference, e.g. "settings page P03"). Stored in a module-level dict `V2_FIELD_PROMPTS: dict[str, FieldPromptInfo]` in a new `core/prompt_metadata.py`; devices may declare `FIELD_PROMPT_OVERRIDES: dict[str, FieldPromptInfo]` merged over the shared table. Resolution: device override → shared table → generated fallback (field name + generic wording flagged as such). Alternative considered — metadata attributes on each struct field — rejected: prompt copy is verify-only concern and would bloat every device file.
2. **Five-beat actuation script** implemented as a single prompt-flow helper in `ground_truth.py` consuming `FieldPromptInfo`; beats: announce (with caution if any), watch-for, ready gate (`Enter` = proceed, `s` = skip), write+readback (existing logic unchanged), confirm (`y`/`n`/`u`). The ready gate replaces nothing existing — today the write happens with no warning. The write-before-confirm principle from the existing spec is preserved; the ready gate precedes the write but asks for readiness, not prediction.
3. **`unsure` outcome**: `device_confirmed` becomes tri-state (`true`/`false`/`null` for skip) plus a distinct recorded `confirm_response: unsure`; the "denial with readback match" label-mapping note fires only on an explicit `n`. Rationale: run 1 shows the denial signal is the single most valuable output of ground truth and must not be diluted by confusion.
4. **Terminology standard** (used by all prompt text, enforced by the metadata table): "the Bluetti unit" = the power station; "your appliance" / "the load" = things plugged into it; outputs always named explicitly ("the AC outlets", "the DC ports (car socket / USB)"). Documented once in `prompt_metadata.py`'s module docstring and `docs/verify.md`.
5. **Rated specs**: class attribute `RATED_AC_OUTPUT_W: int | None = None` on `BluettiDevice` (or `V2Base`), set per model with a comment citing the user manual (EL100V2: 1850 W; AC2A: 300 W). `INDUCED_CHECKS` becomes a builder that receives the device and renders "apply roughly `int(rating × 1.15)` W — for example a space heater". If the device has no rating declared, the overload check is not offered. Alternative — a central specs table keyed by model — rejected: the device class is where all other per-model facts live.
6. **AC frequency caution**: `inv_freq` gets `caution` metadata replicating the user manual's warning (mismatched frequency can damage appliances; unplug appliances before switching) and the actuation defaults to skip — the operator must explicitly type `y` at the ready gate rather than pressing Enter. Wording to be lifted from the manual during implementation (manuals under `bluetti-files/`), not invented.
7. **Firmware observation prompt** enumerates what the operator will actually see: "the app's device-info page lists several versions (ARM, DSP, BMS, IoT); report the ARM value, shown like 2186.14". Comparison logic unchanged.

## Risks / Trade-offs

- [Verbose prompts slow down expert operators] → per-item skip and the ready gate make pacing operator-controlled; expert shortcuts (e.g. a `--terse` flag) deliberately deferred until someone asks.
- [Shared table drifts from per-model screen reality] → overrides are cheap, and the `where`/`watch_for` hints cite the group-0 screen inventory; unknown fields get an honest generated fallback rather than a wrong specific claim.
- [Tri-state confirm complicates the report schema] → additive only (`confirm_response`); existing `device_confirmed` semantics preserved for `y`/`n`.

## Open Questions

- Exact manual wording for the frequency caution — pull from the EL100V2 manual during implementation; if the manual PDF is not in-repo, Mike supplies the sentence.
- Whether `RATED_AC_OUTPUT_W` belongs on `BluettiDevice` or `V2Base` — decide at implementation by checking whether any V1 device reaches ground-truth mode today.
