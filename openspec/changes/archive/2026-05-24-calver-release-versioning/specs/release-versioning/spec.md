## ADDED Requirements

### Requirement: Version derived from git tags at build time

The project SHALL derive its version from the nearest git tag (reachable from HEAD) at build time,
using the hatch-vcs plugin. The version SHALL NOT be hardcoded in pyproject.toml or any source file.

#### Scenario: Tagged commit build

- **WHEN** `uv build` runs from a commit that has a tag `v2026.5` pointing to it
- **THEN** the built package version is `2026.5`

#### Scenario: Commit after tag

- **WHEN** `uv build` runs from a commit 3 revisions after tag `v2026.5`
- **THEN** the built package version is `2026.5.dev3+g<hash>` (development version with commit offset and hash)

#### Scenario: No git metadata available

- **WHEN** `uv build` runs outside a git repository (e.g., from extracted sdist)
- **THEN** the built package version falls back to `0.0.0`

### Requirement: CalVer tag format

Release tags SHALL follow the pattern `vYYYY.MM` (e.g., `v2026.5`).
A second release in the same month SHALL use `vYYYY.MM.1`, `vYYYY.MM.2`, etc.

#### Scenario: First release in a month

- **WHEN** a release is made in May 2026
- **THEN** the tag is `v2026.5`

#### Scenario: Second release in same month

- **WHEN** a second release is made in May 2026
- **THEN** the tag is `v2026.5.1`

### Requirement: PyPI publish gated on tagged releases

The publish workflow SHALL only publish to PyPI when a `v*` tag is pushed.
Pushes to the `main` branch (without a tag) SHALL publish to TestPyPI only.

#### Scenario: Tag push triggers full publish

- **WHEN** a commit with tag `v2026.5` is pushed
- **THEN** the workflow builds the package and publishes to both TestPyPI and PyPI

#### Scenario: Main push publishes to TestPyPI only

- **WHEN** a commit is pushed to the `main` branch without a tag
- **THEN** the workflow builds the package and publishes to TestPyPI, but NOT to PyPI

#### Scenario: Feature branch push does not trigger publish

- **WHEN** a commit is pushed to a branch other than `main` (and without a tag)
- **THEN** the publish workflow does not run
