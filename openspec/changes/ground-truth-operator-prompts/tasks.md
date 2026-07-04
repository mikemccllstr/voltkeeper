## 1. Prompt metadata model

- [x] 1.1 TDD: tests for metadata resolution — shared entry returned by default, device override wins, unknown field yields a generated entry flagged generic
- [x] 1.2 Create `core/prompt_metadata.py`: `FieldPromptInfo` dataclass (`friendly_name`, `affects`, `watch_for`, optional `caution`, optional `where`), `V2_FIELD_PROMPTS` shared table, resolution function honouring device `FIELD_PROMPT_OVERRIDES`; module docstring documents the unit/load terminology standard
- [x] 1.3 Populate the shared table for all currently actuated/observed fields (ac_output, dc_output, ac_eco_mode, dc_eco_mode, ctrl_grid, ctrl_feed, charging_mode, working_mode, alarm_sound, inv_freq, …) with where-to-look hints sourced from the group-0 screen inventory (archive/2026-07-04-verify-ground-truth/design.md)

## 2. Rated specs on device classes

- [x] 2.1 TDD: test that EL100V2 exposes rated AC output 1800 W and that a device without a rating yields no overload offer
- [x] 2.2 Add the rated-AC-output attribute (per design decision 5, deciding BluettiDevice vs V2Base placement) and set it for EL100V2 (1800 W) and AC2A (300 W) with manual citation comments

## 3. Five-beat actuation script

- [x] 3.1 TDD: tests for the actuation flow — ready gate precedes write, skip at ready gate records `skipped` with no write, caution fields default to skip (bare Enter skips, explicit yes proceeds), confirm accepts y/n/unsure, unsure never carries the label-mapping note, explicit no with readback match does
- [x] 3.2 Implement the five-beat prompt flow in `ground_truth.py` consuming `FieldPromptInfo`, replacing the current single-line actuation prompts; preserve existing write/readback/restore logic and `not_confirmable_on_device` handling
- [x] 3.3 Record `confirm_response` in the actuation result and thread it through report serialization

## 4. Observation and induced prompts

- [x] 4.1 Rewrite observation prompts using metadata terminology and where-to-find guidance; make the firmware prompt name the ARM component, mention the other listed versions (DSP, BMS, IoT), and show a "2186.14"-style example
- [x] 4.2 Convert `INDUCED_CHECKS` to a builder taking the device: compute the overload suggestion from the rated AC output with a household example; omit the check (with a report note) when no rating is declared; remove the hardcoded 100 W / 300 W prose
- [x] 4.3 Add the AC-frequency caution to inv_freq metadata, wording lifted from the EL100V2 user manual (check `bluetti-files/`; if the manual text is not in-repo, ask Mike for the sentence)

## 5. Docs

- [x] 5.1 Update `docs/verify.md` ground-truth section: the five-beat script, y/n/unsure semantics, terminology standard, caution-gated fields
- [x] 5.2 Update any docs nav/index entries touched by the verify.md changes

## 6. Verification

- [x] 6.1 Full test suite green with pristine output
- [x] 6.2 Dry-run the prompt flow with a scripted prompt_fn (no hardware): assert generated prompt text for ac_output, dc_output, inv_freq, charging_mode, firmware, and overload reads correctly for a novice (names the right output, right rating, right page references)
