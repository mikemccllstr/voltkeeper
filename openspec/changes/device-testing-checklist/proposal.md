## Why

The `verify` command, btsnoop tooling, and (pending) support tiers exist, but there is no tester-facing walkthrough that strings them into "run this, expect this, send us that." Volunteers who want to test their device have no checklist and no structured way to report results, so reports arrive unactionable or not at all. This is item #14 of `code-review-2026-07-02.md` and the contribution funnel the README asks for.

## What Changes

- Add a "Test your device" user-guide page: prerequisites, `scan` → expected output, `status` spot-checks against the device display, the `verify` invocation, what artifact to attach, and a failure branch covering btsnoop capture and `scripts/parse_btsnoop.py`.
- Pin the tier-promotion bar (decided 2026-07-02): `HARDWARE_VERIFIED` requires verify stages 1–3 passing plus stage 4 under a connected load; stages 5–6 are encouraged but optional. `HARDWARE_TESTING` requires the checklist's connect/handshake/live-data steps.
- Add a GitHub issue template (`.github/ISSUE_TEMPLATE/device-report.yml`) with structured fields: model, firmware/`protocolVer`, OS/adapter, voltkeeper version, verify report attachment, checklist confirmation.
- Link the checklist from the support-tiers page's promotion table, the README "Tested devices" section, and retarget the scan contribution hint at the checklist page.
- Disambiguate terminology in new prose: `verify`'s six write-risk "tiers" are referred to as "stages" wherever they appear near support tiers; no code or existing-page renames.

## Capabilities

### New Capabilities

- `device-testing-checklist`: the tester walkthrough page, the promotion bar it defines, and the structured device-report issue template.

### Modified Capabilities

- `device-support-tiers`: the promotion criteria gain the pinned stage-1–4 bar, and the scan contribution hint points at the checklist page instead of the tier-definitions page. (This capability's spec is introduced by the pending `device-support-tiers` change — this change depends on it landing first.)

## Impact

- `docs/source/user-guide/` — new checklist page + toctree entry; `support-tiers.md` promotion table links and pinned criteria
- `.github/ISSUE_TEMPLATE/device-report.yml` — new issue template
- `README.md` — "Tested devices" section links the checklist
- `src/voltkeeper/bluetooth/__init__.py` — contribution-hint URL retarget (one string)
- Tests: hint-URL test update; docs lint covers the new page. No protocol, daemon, or CLI behavior changes; no new dependencies
- Depends on the `device-support-tiers` change being implemented first
