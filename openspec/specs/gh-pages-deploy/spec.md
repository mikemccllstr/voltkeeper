# gh-pages-deploy Specification

## Purpose
TBD - created by archiving change add-sphinx-documentation. Update Purpose after archive.
## Requirements
### Requirement: GitHub Actions workflow for docs deployment
The project SHALL provide a GitHub Actions workflow that builds the Sphinx documentation site and deploys it to the `gh-pages` branch on every push to `main`.

#### Scenario: Push to main triggers deployment
- **WHEN** a commit is pushed to the `main` branch
- **THEN** the workflow builds the Sphinx documentation and deploys HTML output to `gh-pages`

#### Scenario: Deployment is discoverable via GitHub Pages
- **WHEN** the workflow completes successfully
- **THEN** the documentation site is served at the repository's GitHub Pages URL

### Requirement: Build environment consistency
The workflow SHALL use the same Python version and dependency installation method as local development (`uv` via `mise`).

#### Scenario: Build succeeds in CI
- **WHEN** the workflow runs in GitHub Actions
- **THEN** it installs dependencies with `uv sync --group dev` and builds with `mise run docs`

### Requirement: Clean deployment
The workflow SHALL deploy only the built HTML output (`docs/build/html/`) without committing generated files to the `main` branch.

#### Scenario: Generated files are not committed to main
- **WHEN** the workflow completes
- **THEN** `docs/build/` is not present on the `main` branch; the built HTML exists only on `gh-pages`

