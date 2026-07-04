## 1. Split ground truth into two phases

- [ ] 1.1 TDD: orchestration test (scripted prompt_fn, fake client) asserting observation prompts complete before any tier-2 write and actuation/induced prompts run only after the tiers
- [ ] 1.2 Refactor `ground_truth.py` entry points so observations and actuations/induced are separately callable; update `cli/verify.py` to call observations after tier 1 and the rest after the tiers
- [ ] 1.3 Verify `--tier 1 --ground-truth` behaviour unchanged (observations + induced offered, actuations skipped as unconsented)

## 1b. App handoff around the observation phase

- [ ] 1b.1 TDD: tests for the handoff — BLE disconnect before the first observation prompt, connect-the-app invitation (with LCD-only skip path), disconnect-the-app instruction after the last observation, reconnect before tier 2, retry loop on reconnect failure, report written with tiers 2+ skipped when the operator gives up
- [ ] 1b.2 Implement disconnect/reconnect orchestration in `cli/verify.py` (reconnect performs a fresh encrypted handshake — reuse the normal connect path)
- [ ] 1b.3 TDD then implement: observation prompts display the parsed value as "what to look for" while asking the operator to type exactly what the app shows (free entry, never y/n against our number); record source `app_live` for app readings, keep multimeter and unanchored paths

## 2. Category skip controls

- [ ] 2.1 TDD: tests for category selection — deselected category produces no prompts and records `skipped (operator category selection)`; `--skip-category` pre-answers the menu; default is all enabled
- [ ] 2.2 Implement the category menu at ground-truth start (observations / load actuations / mode actuations / induced) and the repeatable `--skip-category` CLI option

## 3. Restore audit

- [ ] 3.1 TDD: tests for the audit — deviation detected against tier-1 baseline yields report entry `{field, was, now}` and operator output; clean run yields `status: clean`; `--tier 1` run records not-applicable and performs no re-read
- [ ] 3.2 Implement the end-of-session audit in `core/verify.py`: re-read control/status blocks, diff writable fields vs tier-1 baseline, print plain-language deviations with fix guidance, serialize `restore_audit`
- [ ] 3.3 Ensure the audit runs under `--yes` (report-only) and after ground-truth actuations when present

## 4. Progress narration

- [ ] 4.1 TDD: test that tier functions invoke a supplied progress callback at tier start (with field count) and per field start/completion (with probe count)
- [ ] 4.2 Thread an optional `progress` callback through the tier and ground-truth category functions; wire it to `click.echo` in the CLI with tier banners including duration expectations
- [ ] 4.3 Manual review of a full dry-run transcript: no automated stretch longer than one field's testing without output

## 5. Docs

- [ ] 5.1 Update `docs/verify.md`: session walkthrough in the new order (tier 1 → app handoff + observations → tiers 2–6 → actuations/induced → restore audit), the app connect/disconnect choreography, category menu, `--skip-category`, restore-audit meaning
- [ ] 5.2 Update any docs nav/index entries touched by the verify.md changes

## 6. Verification

- [ ] 6.1 Full test suite green with pristine output
- [ ] 6.2 End-to-end dry run with scripted prompts confirming the new order, a forced restore deviation surfacing in both console and YAML, and a category skip
