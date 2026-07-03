## 1. Checklist page

- [ ] 1.1 Write `docs/source/user-guide/test-your-device.md`: prerequisites, scan step, status spot-check step, verify stages 1–3 step, stage 4 under-load step, submission step — each with command, expected outcome, and failure action; "stages" terminology noted against `verify.md`'s "tiers" on first use
- [ ] 1.2 Add the BLE-failure troubleshooting branch: btsnoop capture on Linux/BlueZ, decoding with `scripts/parse_btsnoop.py`, attach-to-report instruction
- [ ] 1.3 Add the page to the user-guide toctree

## 2. Issue form

- [ ] 2.1 Add `.github/ISSUE_TEMPLATE/device-report.yml`: required model, voltkeeper version, OS/adapter, firmware/`protocolVer` fields; verify-report textarea noting reports are pre-scrubbed; tier-claim dropdown with criteria inline; checklist-followed checkbox
- [ ] 2.2 Validate the form YAML renders (GitHub schema — `gh api` preview or push to a branch and check the new-issue chooser)

## 3. Cross-links and hint retarget

- [ ] 3.1 Update `support-tiers.md` promotion table to the pinned bar (stages 1–3 + stage 4 under load, 5–6 optional) and link the checklist page
- [ ] 3.2 Update README "Tested devices" section to link the checklist page
- [ ] 3.3 Update failing test first, then retarget the scan contribution-hint URL in `bluetooth/__init__.py` to the checklist page; run tests green

## 4. Verification

- [ ] 4.1 Run `mise run docs-lint`, `mise run docs-format-check`, and a docs build; confirm the new page renders in the nav and all new cross-links resolve
- [ ] 4.2 Run the full test suite, lint, and typecheck green
