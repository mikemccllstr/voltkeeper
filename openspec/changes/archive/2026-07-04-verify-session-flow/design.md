## Context

The verify session currently runs tiers 1–6 then the whole ground-truth phase (observations, actuations, induced checks) at the end. Run 1 showed the observation prompts belong before any write: the operator gathers screenshots and screen readings against a pristine device, and tiers 2–5 then invalidate them. Separately, `verify.py`'s probe loops emit nothing between tier summaries (tier 3 issued ~140 writes in silence on run 1), and restore failures (`ac_eco_power` left near 34 instead of 10; `lcd_timeout` clamped to 5) surfaced only in the YAML.

The `ground-truth-operator-prompts` change (sibling proposal) restructures the prompt *content*; this change restructures the session *shape*. They touch different requirements and can land in either order, but both edit `ground_truth.py` — implement sequentially, not in parallel worktrees.

## Goals / Non-Goals

**Goals:**
- Observations happen against unmutated device state; the report still cross-references tier-1 raw blocks.
- The operator always knows what the tool is doing and roughly how long it will take.
- Any settings the session failed to restore are stated plainly to the operator at the end, with the original value.
- Whole ground-truth categories are skippable up front, interactively and via CLI flags.

**Non-Goals:**
- No change to tier semantics, consent prompts, FIELD_TIERS, or probe algorithms.
- No prompt-copy rewrites (sibling change).
- No attempt to auto-repair unrestored settings beyond the existing per-field restore logic — the audit reports; the operator fixes.

## Decisions

1. **Split ground truth into two phases**: `run_observations` after tier 1, `run_actuations` + induced checks after the tiers, replacing today's single post-tier block. Observations depend only on the tier-1 capture (already true per spec), so the move is orchestration-only in `cli/verify.py`. Under `--tier 1` the actuation phase still records skips exactly as today. Alternative — full ground truth before tiers — rejected: actuations require tier consent context and deliberately reuse the tiers' risk gating, and running writes before the tiers would recreate the same invalidation problem in reverse for the tiers' own baselines.
1a. **Observation phase is an app handoff.** BLE exclusivity means the vendor app and voltkeeper cannot be connected simultaneously — the old design worked around this with pre/post-session screenshots, which run 1 showed go stale. Instead: after the tier-1 capture, voltkeeper disconnects BLE and prompts the operator to open the vendor app and connect to the unit; each observation prompt then shows the value we parsed and asks the operator to type exactly what the app shows right now; after the last observation, voltkeeper instructs the operator to return the app to its device list (releasing the connection) and reconnects — retrying with a "make sure the app has disconnected, then press Enter" loop on failure, since reconnection requires a fresh encrypted handshake. Observations recorded this way carry source `app_live`; multimeter remains available for quantities the app doesn't show, and the LCD remains a source for on-screen values if the operator has no app. **Anchoring trade-off**: showing the parsed value biases the observer, but run 1 showed an unanchored observer doesn't know what they're looking for; mitigation is free-entry ("type exactly what the app shows, even if it differs") rather than y/n confirmation of our number.
1b. **Drift between the tier-1 read and the app observation** (SoC ticking, watts fluctuating) is absorbed by the existing per-quantity tolerances; the report keeps both values, so an adjudicating human sees the gap.
2. **Restore audit** at session end for any run where tier ≥ 2 executed: re-read the device's control/status blocks, compare every writable field's parsed value against the tier-1 baseline, and (a) print a plain-language list of deviations ("ac_eco_power was 10, is now 34 — set it back in the app or with `voltkeeper write`"), (b) record `restore_audit: {status, deviations: [{field, was, now}]}` in the report. Clean audit records `status: clean`. Fields legitimately changed by the session's design (none today — every path restores) don't need an allowlist yet; if one appears, it gets an explicit exclusion with a comment. Volatile telemetry is excluded by construction because only writable fields are compared.
3. **Narration via a progress callback**: `core/verify.py` tier/field functions accept an optional `progress: Callable[[str], None]` (default no-op) that the CLI wires to `click.echo`. Emit: a banner per tier (name, field count, expectation like "3–30 writes per field, a few minutes total"), one line per field start with probe counts on completion, and one line per ground-truth category. Alternative — logging module — rejected: this is operator UI, not diagnostics, and must not interleave with log config.
4. **Category skips**: at ground-truth start, a checklist-style prompt listing the four categories (observations, output/load actuations, mode actuations, induced conditions) with all enabled by default; plus a repeatable CLI option `--skip-category [observations|load-actuations|mode-actuations|induced]` that pre-answers the menu (giving repeat runs a non-interactive path). Skipped categories record `skipped (operator category selection)` per check group in the report. Per-item skip behaviour is unchanged.

## Risks / Trade-offs

- [Observations-first means the operator handles the device twice (observe, then actuate)] → inherent to the fix; the narration and category menu set expectations up front.
- [Restore audit adds a full re-read at session end] → one extra polling pass (~seconds) against hardware sessions measured in tens of minutes; acceptable.
- [Restore audit false positives from values that drift on their own despite being writable (e.g. clock-like fields)] → compare only fields the session actually wrote to, plus SKIP_AUTO exclusions already remove write-only oddities.
- [Merge friction with ground-truth-operator-prompts in `ground_truth.py`] → implement the two changes sequentially; whichever lands second rebases its edits.
- [Reconnect after the app handoff fails (app still holds the connection, pairing hiccup)] → prompt-and-retry loop with clear instructions; if the operator gives up, write the report with tiers 2+ recorded as skipped (connection lost) rather than losing the tier-1 and observation data.
- [Operator has no vendor app installed] → the handoff prompt offers to skip straight to LCD-based observation, matching today's behaviour.

## Open Questions

- Whether the restore audit should also run after a `--yes` unattended session (nobody is watching the printout, but the report section is still valuable) — default to yes, report-only.
