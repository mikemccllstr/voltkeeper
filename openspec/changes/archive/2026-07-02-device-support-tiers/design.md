## Context

`_device_registry()` maps ~20 name prefixes to device classes, but hardware evidence exists for only two: the AC2A (author's unit, full workflow) and the EL100V2 (encrypted handshake and live data confirmed; verification ongoing). The distinction lives in one README paragraph. `scan` prints `address — name [encrypted|plaintext]` via `ScanResult.display()` and already appends next-step hints in `cli/scan.py`. The docs list all models in tables in `protocol/device-models.md` with no verification status. Review item #13 asks for a per-model support tier surfaced in scan output and docs.

## Goals / Non-Goals

**Goals:**

- One source of truth in code for each model's verification status, with a safe default for new contributions.
- Tier visible at the two places users meet a model: `scan` output and the docs model tables.
- An objective promotion criterion, and a mechanical guard against docs/code drift.

**Non-Goals:**

- Per-field verification granularity (which writes are confirmed vs derived) — deferred to the hardware-verification checklist work (review item #14).
- Renaming `is_supported_device_type()` or changing its semantics ("has a register map"). The user-guide page defines "supported" vs "verified" in prose instead.
- Warnings on `status`/daemon connect for untested models — scan is the discovery surface; runtime warnings can follow later if wanted.

## Decisions

**Tier lives as a class attribute, not a separate table.** `SUPPORT_TIER: SupportTier = SupportTier.APK_DERIVED` on `BluettiDevice`, overridden per model. This matches the existing capability-defaults pattern (`WRITABLE_FIELD_NAMES = []`): a model contributed without hardware access is automatically labeled untested. Alternative — a dict in `bluetooth/__init__.py` beside the registry — keeps model files untouched but splits a model's definition across two files and can silently miss new entries.

**Three tiers, not two.** `HARDWARE_VERIFIED`, `HARDWARE_TESTING`, `APK_DERIVED`. The EL100V2 is genuinely in-between: real-hardware handshake and live data, but incomplete verification. Collapsing it either overstates (verified) or understates (untested) the truth. No fourth tier until a device needs one.

**Enum defined in `bluetti_device.py`.** The tier is a property of the device model, so it lives with `BluettiDevice` in `core/` (which stays BLE-free — the enum is pure data). `ScanResult.display()` gains an optional tier argument (or the scan path resolves it via `build_device`/registry prefix match) so `bluetooth/` renders it without `core/` knowing about display strings.

**Promotion criterion is a passing `voltkeeper verify` run.** Documented on the user-guide page: `APK_DERIVED` → `HARDWARE_TESTING` when core flows (connect, handshake if encrypted, live data parse) are confirmed on a real unit; → `HARDWARE_VERIFIED` when a full `verify` run passes and the result is recorded. This ties tiers to the existing `device-verify` capability instead of inventing a parallel process.

**Docs guarded by a cross-check test, not generated.** A pytest parses the markdown tables in `protocol/device-models.md`, maps the Support column to enum values, and asserts equality with each registry class's `SUPPORT_TIER` — and that every registry model appears in exactly one table. Generation was rejected: the tables carry hand-curated prose columns (Notes, voltages) and the project convention is hand-edited docs with lint/test guards (cf. the mise-task tests).

## Risks / Trade-offs

- [Tier display in `scan` requires resolving name → class before connect] → the registry prefix match in `build_device` already does this without I/O; factor the prefix lookup so scan can reuse it cheaply.
- [Docs table parsing is brittle to formatting changes] → mdformat normalizes table syntax in CI, so the parser targets a stable format; the test failure message names the model and file to make fixes obvious.
- ["Verified" may be read as a guarantee] → tier definitions page states it means "verified by a community member on their unit", consistent with the README's existing candor.
