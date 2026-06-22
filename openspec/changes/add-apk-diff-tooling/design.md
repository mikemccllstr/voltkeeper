## Context

`voltkeeper` is reverse-engineered from the Bluetti Android app. The repo already has file-based mise tasks (`download-apk`, `decompile-jadx`, `decompile-apktool`, `prepare-all`, `cleanup`) that operate on APKs under `bluetti-files/` (gitignored). Current constraints discovered while scoping this change:

- `download-apk` hits Bluetti's CDN endpoint `/api/midpmdata/app/version/v1/android/apk/latest`, which serves **only the latest** build. The sibling list/history endpoints require an access token we do not have; a `version` query param is ignored. So specific historical versions are not retrievable from Bluetti.
- The decompile tasks glob `bluetti-files/*/bluetti.apk`, so any APK staged in that layout is processed unchanged.
- `bluetti-files/` is gitignored and currently empty — the 3.0.9 decompile referenced in `AGENTS.md` no longer exists on disk, and `bluetti-files` was a broken circular symlink (since removed).
- `cleanup` does `rm -rf bluetti-files`, destroying irreplaceable APKs.
- The local `bluetti-apk-archive/` holds historical APKs (2.3.29, 3.0.0, 3.0.7, 3.0.8, 3.0.9). The latest from Bluetti is `BLUETTI-v3.0.10.apk`.

## Goals / Non-Goals

**Goals:**
- A repeatable acquire → decompile → diff workflow expressed as mise tasks.
- Treat downloaded APKs as precious; never destroy them in `cleanup`.
- Bring historical versions from the local archive into the workflow.
- Produce a semantic, anchor-based protocol diff between versions.
- Deliver the first 3.0.9 → 3.0.10 comparison report and assess code impact.

**Non-Goals:**
- Downloading arbitrary versions from Bluetti (not possible) or via third-party mirrors / `apkeep` (deferred until a needed version is neither archived nor latest).
- Dynamic analysis (Frida hooks, btsnoop capture, live-hardware validation) — deferred.
- Auto-updating `src/voltkeeper` from diffs, or extracting this tooling into a separate repo.

## Decisions

**1. Stage historical APKs via a new `import-apk <path>` task, rather than generalizing `download-apk`.**
Bluetti exposes no version selector, and the decompile tasks already glob `bluetti-files/*/bluetti.apk`, so import is the minimal seam. *Alternative considered:* `apkeep` from APKPure — rejected for now due to repackaging/provenance concerns and YAGNI.

**2. Anchor-based semantic diff along three lenses, not a raw tree diff.**
R8/ProGuard renames classes between versions, so `diff -r` of the jadx trees is noise. `diff-apk` extracts and compares three complementary lenses: (a) **protocol anchors** from the jadx code (BLE UUIDs, numeric/register constants, crypto-class usage, device-model identifiers) — the "does this affect our implementation" view; (b) the **resource / user-facing surface** from the apktool output (default `strings.xml`, `res/layout`, the drawable/asset inventory, manifest components & permissions, and `versionName`/`versionCode`) — the "what is this release about" view, which often reveals new device support or features more readably than code; and (c) the **backend / cloud API surface** from the jadx code (Retrofit/OkHttp endpoint paths, host/base URLs, hardcoded URLs) — the "did the cloud contract change" view. *Alternative considered:* `jadx --deobf` for stable names — rejected; generated names are still not stable across versions, whereas string/UUID literals are reliable anchors. No off-the-shelf tool fits: Diffuse/apkdiff/dex-diff/apkanalyzer are size/metric oriented, and online "decompile + unified diff" is exactly the noisy text diff we reject.

**3. `cleanup` preserves APKs via a two-pass `find`.**
First pass deletes every file that is not named `bluetti.apk`; second pass prunes empty directories. A directory still holding an APK is non-empty and survives. *Alternative considered:* enumerating derived dir names — rejected as brittle when new artifact types are added.

**4. Diff artifacts are gitignored under `bluetti-files/`; only the curated report goes to `docs/`.**
Artifacts are bulky and regenerable; the human-reviewable report is the durable output, published with the Sphinx site. Structured artifacts are primary for tooling; the report is the human view.

**5. Decompile both versions with the same pinned toolchain in one pass.**
jadx (via mise) and apktool (system) versions must match across the two versions being compared, so differences reflect the APKs, not the tools.

## Risks / Trade-offs

- **Anchor set misses a semantically relevant change** → Anchors target our known protocol surface; the report states coverage, and the anchor set is easy to extend when a gap is found.
- **Archive APK is a repackaged third-party build** → Prefer official-named archive entries; record provenance per version; note when a comparison uses a mirror build.
- **`download-apk` may already serve something newer than 3.0.10** → Verify `versionName` with `aapt2` after download and archive the exact file used.
- **`cleanup` regression could delete an APK** → The first `find` pass excludes `bluetti.apk` by name and the second only removes empty dirs; covered by an automated test.

## Open Questions

- Whether to later add an `apkeep`-based fetch for un-archived versions, and the dynamic-analysis rungs (Frida/btsnoop/hardware). Both are explicitly deferred and out of scope for this change. Note: the established community method for this device family (e.g. `bluetti_mqtt`) is packet capture (btsnoop + Wireshark), not decompilation — which reinforces capture as the eventual path for protocol *discovery*, with `diff-apk` serving the "what changed in a release" question.
- **Anchor-matching ceiling.** If literal anchors (especially `register_constants`) prove too noisy across obfuscated versions, the escalation path is structural class signatures — Quarkslab-style SimHash over method/field counts and abstracted opcodes — or DalvikFLIRT + LLM-assisted renaming. It is explicitly **not** `jadx --deobf`, whose generated names are not stable across versions. Deferred until the simple anchors prove insufficient.
- **Official Bluetti crypt library as a validation oracle (future spike).** `bluetti-official/bluetti-bluetooth-lib` ships `bluetti_crypt.py` plus a compiled `_bluetti_crypt.so` exposing `ble_crypt_link_handler`, `encrypt_data`, `decrypt_data`. It is a closed binary with no protocol spec, so it does not feed `diff-apk`. But it could serve as a *sanctioned* oracle for validating our reimplemented encryption/handshake (the area behind the `fix-v2-ecdh-*` / `fix-v2-encrypted-handshake` work) — cleaner than decompiling or Frida-hooking because it is an official artifact rather than extracted code. Worth a future spike; out of scope here.
