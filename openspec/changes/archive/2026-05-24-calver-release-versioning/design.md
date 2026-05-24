## Context

Current state: version `0.1.0` hardcoded in `pyproject.toml`, no git tags exist, publish workflow triggers on every branch push (`on: push`). The project is moving toward occasional deliberate releases using CalVer.

## Goals / Non-Goals

**Goals:**
- Derive version from git tags at build time (single source of truth)
- CalVer format: `YYYY.MM` with optional `.PATCH` for multiple releases in a month
- Releases are a conscious decision — PyPI publish only on tagged pushes
- Developer builds from untagged commits get informative dev version strings (e.g., `2026.5.dev3+g1a2b3c4`)

**Non-Goals:**
- Conventional commit parsing or auto-bumping
- Automated GitHub Releases (can layer on later)
- Changing TestPyPI publish behavior (stays on main pushes, intentional noise)
- Changing CI or Docs workflows

## Decisions

**1. Use hatch-vcs for version derivation**

`hatchling` (used in pyproject.toml via `build-system`) has a `hatch-vcs` plugin that derives the version from git metadata at build time. No other tool (setuptools-scm, versioneer) is needed since the project already uses hatchling.

**2. CalVer tag format: `vYYYY.MM`**

Tags use the pattern `v2026.5`, `v2026.5.1`, etc. The `v` prefix is conventional and the regex `^v(?P<version>.*)$` in hatch-vcs strips it for the PyPI version string (`2026.5`).

**3. Workflow trigger: `branches: [main]` + `tags: ['v*']`**

```
on:
  push:
    branches: [main]
    tags: ['v*']
```

This replaces the bare `on: push`. Feature-branch pushes only trigger CI, not the publish workflow.

**4. PyPI job stays gated on `startsWith(github.ref, 'refs/tags/')`**

Already correct — the `if` on the `publish-to-pypi` job keeps it tag-only.

**5. Remove `version` from `pyproject.toml`**

The `[project] version` field conflicts with hatch-vcs. Removing it and configuring the plugin lets hatch-vcs supply the version. If a build runs without git history (should not happen in CI), it falls back to `0.0.0`.

## Risks / Trade-offs

**[R] Tagging the wrong commit** — Pushes a release tag pointing to a broken commit.
→ **Mitigation:** CI must be green on that commit before tagging. Could enforce via branch protection, but for now it's a manual discipline.

**[R] Build without git metadata** — If someone runs `uv build` outside a git repo, version becomes `0.0.0`.
→ **Mitigation:** Acceptable. This is a development edge case, not a production path.

**[R] hatch-vcs dependency** — Adds a build dependency that must be available in CI.
→ **Mitigation:** Listed as a build dependency in pyproject.toml, resolved by hatchling's plugin system. Already works in the mise/uv environment used by CI.
