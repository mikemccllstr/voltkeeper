## Why

Our interoperable implementation is reverse-engineered from the Bluetti Android app, so when Bluetti ships a new APK we need to know whether the protocol surface we depend on (BLE UUIDs, Modbus registers, the encrypted handshake, device models) has changed. Today decompilation is ad hoc: there is no way to bring an older APK into the workflow for comparison, no version-to-version diff, and the `cleanup` task destroys downloaded APKs that cannot be re-fetched. Version 3.0.10 just shipped and we need a repeatable way to assess its impact against 3.0.9.

## What Changes

- Add an `import-apk <path>` mise task that stages an arbitrary/archived APK into `bluetti-files/<version>/bluetti.apk`, so the existing `decompile-jadx` / `decompile-apktool` tasks process historical versions unchanged.
- Add a `diff-apk <verA> <verB>` mise task that emits focused comparison artifacts into `bluetti-files/` (gitignored, regenerable) along three complementary lenses: (a) **protocol anchors** from the code (BLE UUIDs, register/numeric constants, crypto-class usage, device-model identifiers) — "does this affect our implementation?"; (b) the **resource / user-facing surface** from the resources (default string resources, GUI layouts, drawable/asset inventory, manifest components & permissions, build/version properties) — "what is this release about?", which often reveals new device support or features more readably than code; and (c) the **backend / cloud API surface** from the code (Retrofit/OkHttp endpoints, host/base URLs, hardcoded URLs) — "did the cloud contract change?". Raw `diff -r` of decompiled trees is unusable because R8/ProGuard renames classes between versions.
- **BREAKING** (task behavior): change `cleanup` to preserve every `bluetti.apk` and delete only derived output. Downloaded APKs are precious — Bluetti's endpoint serves only the latest, so older versions cannot be re-downloaded.
- Document that `download-apk` is inherently latest-only (Bluetti exposes no version selector; the version-list endpoints require an access token we do not have). Historical versions come from the local archive via `import-apk`.
- Produce the first comparison report (3.0.9 → 3.0.10) under `docs/source/protocol/`, and assess whether the differences affect `src/voltkeeper` or the existing protocol docs.

## Capabilities

### New Capabilities
- `apk-version-analysis`: a developer workflow to acquire, decompile, and compare versions of the Bluetti Android APK — treating downloaded APKs as precious inputs, supporting import of historical versions, and producing version-to-version protocol diffs that feed our reverse-engineered implementation.

### Modified Capabilities
<!-- No existing spec governs APK tooling; all behavior here is new. -->

## Impact

- `.mise/tasks/`: new `import-apk`, new `diff-apk`, modified `cleanup`; documentation comment on `download-apk`.
- `AGENTS.md`: update the mise task table and the "Bluetti APK Source" section (the documented 3.0.9 decompile no longer exists on disk; `bluetti-files/` is gitignored and regenerable).
- `docs/source/protocol/`: new 3.0.9 → 3.0.10 version-comparison report, published with the Sphinx site.
- `bluetti-apk-archive/`: retain the official `BLUETTI-v3.0.10.apk` so the archive stays the complete version history.
- No change to runtime/library behavior — this is developer tooling plus documentation. If the diff reveals protocol changes that require code edits, those are handled as separate changes.
