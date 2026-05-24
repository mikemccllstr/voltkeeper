## Context

GitHub announced deprecation of Node.js 20 for Actions, with Node.js 24 becoming the default on June 2, 2026 and Node.js 20 being removed September 16, 2026. Every action in the three workflow files currently runs on Node.js 20, producing deprecation warnings in the Actions UI. All four affected actions have released Node.js 24-compatible versions.

Additionally, `publish-to-pypi.yml` references `actions/upload-artifact@v5` and `actions/download-artifact@v6` — versions that do not exist. These likely result from a typo or copy-paste error when the workflow was created.

## Goals / Non-Goals

**Goals:**
- Eliminate Node.js 20 deprecation warnings from all three workflow files
- Fix nonexistent action version references in publish-to-pypi.yml
- Preserve identical runtime behavior — no workflow logic changes

**Non-Goals:**
- Refactoring workflow structure
- Adding new CI capabilities
- Changing Python versions or test matrix
- Moving to hash-pinned action references

## Decisions

### Version bumps

| Action | Current | New | Rationale |
|---|---|---|---|
| `actions/checkout` | `@v4` | `@v6` | v6 is the latest major with Node.js 24 |
| `actions/upload-artifact` | `@v4` | `@v7` | v7 is the latest major with Node.js 24 |
| `actions/download-artifact` | `@v4` | `@v8` | v8 is the latest major with Node.js 24 |
| `jdx/mise-action` | `@v2` | `@v4` | v4 is the latest major with Node.js 24 |
| `peaceiris/actions-gh-pages` | `@v4` | `@v4` (stay) | Already on v4; release v4.1.0 updated Node runtime |

All these major version bumps were driven by Node.js runtime migration, not API changes. They are drop-in replacements with no configuration changes required.

### `publish-to-pypi.yml` version fixes

`upload-artifact@v5` and `download-artifact@v6` never existed as stable releases. These are corrected to `@v7` and `@v8` respectively, matching the Node.js 24 upgrade.

### No spec changes

This is a pure infrastructure version bump. No user-facing capabilities change, no requirement changes. No spec files are needed.

## Risks / Trade-offs

- **No breaking changes expected** — these major version bumps were exclusively for Node.js runtime upgrades, not API changes. Verified against each action's changelog.
- **`pypa/gh-action-pypi-publish`** uses a rolling `release/v1` tag and does not document its Node.js runtime. If it produces warnings after other fixes, it can be addressed separately.
- **`peaceiris/actions-gh-pages`** stays at v4. The v4.1.0 release notes mention "update Node runtime" — likely Node.js 24 based on the May 2026 release date. If warnings persist, consider pinning to v4.1.0 explicitly.
