## Why

GitHub is deprecating Node.js 20 for Actions. Node.js 24 becomes the default on June 2, 2026, and Node.js 20 will be removed from runners on September 16, 2026. CI runs and publish jobs are currently producing deprecation warnings for every action that uses Node.js 20.

## What Changes

- Bump `actions/checkout` from v4 to v6 (adds Node.js 24 support)
- Bump `actions/upload-artifact` from v4 to v7 (adds Node.js 24 support)
- Bump `actions/download-artifact` from v4 to v8 (adds Node.js 24 support)
- Bump `jdx/mise-action` from v2 to v4 (adds Node.js 24 support)
- Pin `peaceiris/actions-gh-pages` to v4.1.0 (adds updated Node runtime)
- Fix `actions/upload-artifact@v5` (nonexistent version) in publish-to-pypi.yml to @v7
- Fix `actions/download-artifact@v6` (nonexistent version) in publish-to-pypi.yml to @v8

## Capabilities

### New Capabilities

None — this is a pure version bump with no user-facing behavior change.

### Modified Capabilities

None — no spec-level requirements change. The workflows produce identical results.

## Impact

- `.github/workflows/ci.yml` — checkout + mise-action bumps (×2 each)
- `.github/workflows/publish-to-pypi.yml` — checkout + mise-action + upload-artifact + download-artifact bumps, plus fixing nonexistent version refs
- `.github/workflows/docs.yml` — checkout + mise-action bumps, gh-pages pin to v4.1.0
- No Python code, tests, or dependencies affected
