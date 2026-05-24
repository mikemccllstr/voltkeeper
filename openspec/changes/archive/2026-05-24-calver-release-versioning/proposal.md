## Why

The project has no versioning strategy. Version is hardcoded at `0.1.0` in `pyproject.toml`, no git tags exist, and the PyPI publish workflow fires on every branch push — not just releases. We need a deliberate release process with CalVer versioning so releases are conscious decisions, not side effects of every commit.

## What Changes

- Adopt CalVer (`YYYY.MM`) versioning, derived from git tags via hatch-vcs
- Remove hardcoded version from `pyproject.toml`; let git tags be the single source of truth
- Narrow publish workflow trigger to `main` pushes (TestPyPI) and `v*` tag pushes (TestPyPI + PyPI)
- Add `hatch-vcs` as a build dependency
- Configure hatch-vcs in `pyproject.toml` for CalVer tag format

## Capabilities

### New Capabilities

- `release-versioning`: Version derived from git tags; CalVer format; publish workflow gated on tagged releases

### Modified Capabilities

<!-- No existing specs to modify -->

## Impact

- `pyproject.toml`: version field, build dependencies, hatch-vcs config
- `.github/workflows/publish-to-pypi.yml`: trigger conditions
- Build process: `uv build` will now read version from git tags
