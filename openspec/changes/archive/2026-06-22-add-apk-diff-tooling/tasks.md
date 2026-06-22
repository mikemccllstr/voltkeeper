## 1. import-apk task (TDD)

- [x] 1.1 Write failing test: `import-apk <archive-apk>` stages the file at `bluetti-files/<version>/bluetti.apk`
- [x] 1.2 Write failing tests: re-import is idempotent (existing APK not overwritten); missing/unreadable path exits non-zero with a message
- [x] 1.3 Implement `.mise/tasks/import-apk` to pass the tests
- [x] 1.4 Run the tests and confirm green

## 2. cleanup task — preserve APKs (TDD)

- [x] 2.1 Write failing test: `cleanup` removes `jadx_out`/`apktool_out`/diff output/logs but preserves every `bluetti.apk`; no-op (exit 0) when `bluetti-files/` is absent
- [x] 2.2 Reimplement `.mise/tasks/cleanup` with the two-pass `find` approach and update its `#MISE description`
- [x] 2.3 Run the tests and confirm green

## 3. diff-apk task (TDD)

- [x] 3.1 Write failing tests for protocol-anchor extraction on small fixtures: BLE UUIDs, numeric/register constants, device-model identifiers
- [x] 3.2 Write failing tests for resource/UI-surface extraction on small fixtures: default `strings.xml`, `res/layout` inventory, drawable/asset inventory, manifest components & permissions, `versionName`/`versionCode`
- [x] 3.3 Write failing tests for backend/cloud API extraction on small fixtures: HTTP endpoint paths, host/base URLs, Retrofit/OkHttp client definitions
- [x] 3.4 Write failing test: `diff-apk` exits non-zero and names the missing version when a referenced version has not been decompiled
- [x] 3.5 Implement `.mise/tasks/diff-apk <verA> <verB>` to extract all three lenses per version and write comparison artifacts under `bluetti-files/` (gitignored)
- [x] 3.6 Run the tests and confirm green

## 4. download-apk documentation

- [x] 4.1 Add a comment to `.mise/tasks/download-apk` documenting that it is latest-only and pointing to `import-apk` for historical versions

## 5. Acquire and decompile both versions

- [x] 5.1 `mise run download-apk` (3.0.10); verify `versionName` with `aapt2`; copy the official APK into `bluetti-apk-archive/`
- [x] 5.2 `mise run import-apk bluetti-apk-archive/BLUETTI-v3.0.9.apk`
- [x] 5.3 `mise run decompile-jadx` and `mise run decompile-apktool` for both versions

## 6. Compare and report

- [x] 6.1 `mise run diff-apk <3.0.9> <3.0.10>` and review the artifacts
- [x] 6.2 Write the 3.0.9 → 3.0.10 comparison report under `docs/source/protocol/`, with a protocol-impact section (code anchors), a release-intent section (resource/UI-surface changes), and a cloud-API section (endpoint/host changes)
- [x] 6.3 Assess impact on `src/voltkeeper` and the existing protocol docs; record findings (and any follow-on changes needed) in the report

## 7. Documentation and task registry

- [x] 7.1 Update `AGENTS.md` — mise task table and the "Bluetti APK Source" section (note `bluetti-files/` is gitignored/regenerable)
- [x] 7.2 Add the new report to the Sphinx protocol toctree

## 8. Quality gate

- [x] 8.1 Run `mise run check` (lint, typecheck, tests, docs lint/format) and fix any failures
- [x] 8.2 Run `mise run docs-format` on changed docs
