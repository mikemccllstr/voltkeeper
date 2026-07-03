## Context

`verify` runs six escalating write-risk tiers (1–3 automatic, 4–6 supervised) and emits a scrubbed YAML report; `verify-interpretation.md` tells maintainers how to act on it; `scripts/parse_btsnoop.py` decodes BLE captures. The pending `device-support-tiers` change adds `SupportTier`, a scan contribution hint, and a `support-tiers.md` page whose promotion criterion is loosely "a full verify run passes." What's missing is the tester-facing path between "I own a device" and "the maintainer received an actionable report" — review item #14.

Mike pinned the promotion bar on 2026-07-02: verify stages 1–3 pass plus stage 4 under a connected load; stages 5–6 optional.

## Goals / Non-Goals

**Goals:**

- One page a non-developer can follow end-to-end, with expected output at each step so testers can self-diagnose where things diverge.
- Reports arrive structured enough to act on without a follow-up round-trip (model, firmware, environment, verify report, capture when relevant).
- An unambiguous, documented promotion bar shared by the checklist and the support-tiers page.

**Non-Goals:**

- No changes to `verify` command behavior, its tier structure, or its report format.
- No renaming of `verify`'s tiers in code or on existing pages — disambiguation is prose-only on new/edited text.
- No per-field verification granularity (stays deferred, per the device-support-tiers design).
- No documentation of the `integration` pytest marker for volunteers — that is a developer surface, not a tester one.

## Decisions

**One page, ordered as a decision tree, not a reference.** The checklist page runs: prerequisites → scan → status spot-check → verify (stages 1–3) → stage 4 under load → submit. Each step states the command, the expected outcome, and "if this fails, do X" — where X for BLE-level failures is the btsnoop capture branch. Alternative — splitting happy path and troubleshooting into separate pages — was rejected: testers hit failures mid-flow, and the existing `verify.md`/`verify-interpretation.md` split already covers the reference material, which this page links rather than repeats.

**Promotion bar lives on the support-tiers page; the checklist links to it.** The pending `support-tiers.md` already owns the promotion table, so the pinned bar (stages 1–3 + stage 4 under load) amends that table rather than being stated twice. The checklist page says "complete steps 1–N and you've met the `HARDWARE_TESTING` bar; complete through step M for `HARDWARE_VERIFIED`" and links the table. Single source of truth for criteria; the checklist maps steps to bars.

**Issue form (`.yml`), not a markdown template.** GitHub issue forms give required fields (model, voltkeeper version, OS/adapter, firmware/`protocolVer`) and a checkbox acknowledging the checklist was followed, which is precisely the "actionable report" guarantee. A markdown template can be deleted wholesale by the reporter. The verify report attaches as a file/paste field; scrubbing is already done by `verify` itself, and the form says so to reduce reporter anxiety.

**Terminology: verify's "tiers" become "stages" in new prose only.** Renaming in code, `verify.md`, or the `device-verify` spec would churn a stable, shipped surface for a vocabulary problem. New text says "verify stage 3 (called *tier 3* in the verify reference)" on first use, then "stage" thereafter. If the collision proves confusing in practice, a later change can rename `verify.md`'s headings.

**Scan hint retargets to the checklist page.** The hint exists to convert a curious scanner into a tester; the checklist is that funnel's entry point, and it links the tier definitions in its intro. One-string change plus its test.

## Risks / Trade-offs

- [Checklist drifts as `verify` evolves] → the page links `verify.md` for stage semantics instead of restating them; only step ordering and expected outputs live on the checklist.
- [Stage 4 requires a load; testers may skip it and expect `HARDWARE_VERIFIED`] → the checklist and issue form both state the bar explicitly; the form's tier-claim field is a dropdown (`HARDWARE_TESTING` / `HARDWARE_VERIFIED`) with the criteria beside each option.
- [Issue form can't validate attachments] → the form marks the verify-report field required-by-policy and the triage response for missing reports is a link back to the checklist step.
- [Depends on unmerged `device-support-tiers` change] → tasks sequence this change after it; if priorities flip, the checklist page can land with the promotion-table edits deferred.

## Open Questions

- None — the promotion bar was decided by Mike on 2026-07-02.
