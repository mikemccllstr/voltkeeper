## Why

Voltkeeper's documentation exists as a flat collection of Markdown files in `docs/` with no structure, no site navigation, no search, no versioned publication, and no man page. Users discover the tool through `README.md` but have no discoverable path to deeper material. Adding Sphinx gives the project a proper, themed, searchable documentation site suitable for GitHub Pages.

## What Changes

- Add `sphinx`, `myst-parser`, and `furo` as dev dependencies
- Create `docs/source/` tree with audience-organized content (user-guide, developer, protocol, about)
- Configure Sphinx (`conf.py`) with MyST Markdown parser, Furo theme, and man page builder
- Adapt existing `docs/*.md` content into the Sphinx source tree, restructuring `FINDINGS.md` into multiple pages under `protocol/`
- Add `mise run docs` task for local HTML and man page builds
- Add GitHub Action to build and deploy to `gh-pages` branch on push to main
- Generate a `voltkeeper(1)` man page covering all CLI commands
- Add a placeholder `api/` section for future autodoc integration
- Exclude `IMPLEMENTATION_UNITS.md` and `MULTI_DEVICE_PLAN.md` from the published site (they remain as development artifacts)

## Capabilities

### New Capabilities
- `sphinx-docs`: Sphinx + MyST Markdown documentation site with Furo theme, audience-organized content, and man page generation
- `gh-pages-deploy`: GitHub Actions workflow to build Sphinx docs and deploy to `gh-pages` branch on push to main

### Modified Capabilities
<!-- None - no existing specs to modify -->

## Impact

- New dev dependencies: `sphinx`, `myst-parser`, `furo`
- New file tree: `docs/source/` with subdirectories, `docs/source/conf.py`
- New mise task: `mise run docs`
- New GitHub Action: `.github/workflows/docs.yml`
- Existing `docs/*.md` files remain in place as source material; content is adapted into `docs/source/`
- `docs/build/` added to `.gitignore`
