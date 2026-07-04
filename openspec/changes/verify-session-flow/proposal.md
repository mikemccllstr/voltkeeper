## Why

The first EL100V2 ground-truth session (2026-07-04) exposed three session-structure problems: the operator's pre-session app screenshots were invalidated because tiers 2–5 mutated settings *before* the ground-truth observation prompts asked about them; the tool went silent for minutes during probe sweeps, looking hung; and two failed restores left the device with altered settings, reported only as YAML fields the operator never saw. Operators also need to opt out of whole categories (load switching, overload) up front, not just item by item.

## What Changes

- Session order changes: ground-truth **observations** run immediately after tier 1, while the device is still untouched; **actuations** and induced checks remain after the tiers, as today.
- The observation phase becomes an **app handoff**: voltkeeper drops its BLE connection, invites the operator to connect the vendor app, shows the parsed value for each check while asking the operator to type exactly what the app shows live, then reminds the operator to disconnect the app (return to its device list) so voltkeeper can reconnect for tier 2. Live app readings replace pre/post-session screenshots as the preferred secondary source.
- A **restore audit** runs at the end of any verify session that performed writes: re-read the device, diff writable-field values against the tier-1 baseline, print any deviations to the operator with fix instructions, and record a `restore_audit` section in the report.
- Continuous **progress narration** throughout verify: tier banners with field counts and rough duration expectations, a line per field as probing starts/finishes, so the session never looks hung.
- **Category skip controls** for ground-truth mode: an up-front menu selecting which categories run (observations / output & load actuations / mode actuations / induced conditions) plus matching CLI flags for repeat runs; per-item skip is unchanged.

## Capabilities

### New Capabilities

(none)

### Modified Capabilities

- `device-verify`: gains progress-narration and end-of-session restore-audit requirements.
- `verify-ground-truth`: the ordering requirement changes (observations before tiers 2+, actuations after), category-level skip selection is added, the observation phase gains the app-handoff protocol, and the off-screen-quantities requirement switches from screenshots to live app readings as the preferred source.

## Impact

- `src/voltkeeper/cli/verify.py` — session orchestration order, category menu, skip flags, narration output.
- `src/voltkeeper/core/verify.py` — progress callback threading, restore-audit implementation.
- `src/voltkeeper/core/ground_truth.py` — observation phase separable from actuation phase; category gating.
- `docs/verify.md` — session walkthrough reflecting the new order and skip controls.
- Report schema — new `restore_audit` section; tests for ordering, audit, and category skips.
