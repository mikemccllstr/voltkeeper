## Why

Every push to `main` triggers a TestPyPI publish that fails because hatch-vcs with the `post-release` scheme generates local versions (`+g<commit>`) on non-tagged commits, which PyPI/TestPyPI reject. TestPyPI no longer serves a useful pre-release check and is just noise. Remove it.

## What Changes

- Remove the `publish-to-testpypi` job from `publish-to-pypi.yml`
- The `build` job remains unchanged (runs on every main push and tag push)
- The `publish-to-pypi` job remains unchanged (runs only on tag pushes)

## Capabilities

### New Capabilities

None — this is infrastructure cleanup with no new user-facing behavior.

### Modified Capabilities

None — no spec-level requirements change.

## Impact

- `.github/workflows/publish-to-pypi.yml`: ~24 lines removed (the `publish-to-testpypi` job and its `testpypi` environment dependency)
- No Python code, tests, or dependencies affected
