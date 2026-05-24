## Context

Voltkeeper currently has a flat `docs/` directory containing 9 Markdown files and 2 SVG assets. There is no build pipeline, no site navigation, no search, and no publication mechanism. The README serves as the only entry point, with cross-references between docs files relying on relative GitHub links that only resolve in the repo browser.

The source code has a convention of `# ABOUTME:` module docstrings on every file, but no Sphinx or autodoc configuration exists. No Python API reference is generated from docstrings.

Constraints:
- Content must remain authorable in Markdown (not reStructuredText)
- Existing docs files stay in place as source material; content is adapted into the Sphinx tree
- `IMPLEMENTATION_UNITS.md` and `MULTI_DEVICE_PLAN.md` are excluded from the published site
- The site must be deployable to GitHub Pages from a GitHub Actions workflow

## Goals / Non-Goals

**Goals:**
- A navigable, searchable, themed documentation site built with Sphinx
- Content migration: adapt existing `docs/*.md` into audience-organized sections
- Break the 1700-line `FINDINGS.md` into topic-specific pages under `protocol/`
- Generate a `voltkeeper(1)` man page from Sphinx source
- `mise run docs` for local builds
- GitHub Actions workflow to deploy to `gh-pages` on push to main

**Non-Goals:**
- API reference generation from docstrings (placeholder only; deferred to future work)
- RestructuredText authoring (MyST Markdown only)
- Read the Docs integration (GitHub Pages only for now)
- Migration of `IMPLEMENTATION_UNITS.md` or `MULTI_DEVICE_PLAN.md` content
- Rewriting or significantly restructuring existing doc content (adaptation, not rewrite)

## Decisions

### Sphinx + MyST parser over MkDocs
MkDocs is simpler for pure Markdown, but Sphinx provides man page generation (via its built-in `man` builder) and a direct path to `sphinx-autodoc` for future API reference. Sphinx also has stronger cross-referencing and the MyST parser handles Markdown as a first-class input format. Given the explicit future need for API docs and man pages, Sphinx is the better foundation.

### Furo theme over Read the Docs or Book theme
Furo is modern, maintained, responsive with built-in dark mode, has excellent search UX, and has become the de facto standard for Python package documentation. Read the Docs theme is older with less polish; Book theme is better suited to long-form tutorial content.

### `docs/source/` source tree, not `docs/` as source root
Using `docs/source/` as the Sphinx source root keeps the existing `docs/*.md` files in place as raw material and creates a clean separation between "source material" and "Sphinx source." The Sphinx build output goes to `docs/build/` (gitignored). This avoids disrupting the existing directory layout and makes it obvious what is Sphinx-authored versus legacy content.

### Content adaptation, not file moves
Rather than moving `docs/ABOUT.md` → `docs/source/about/index.md`, content is adapted from the original files. This preserves the existing files as reference and allows tailoring content for the Sphinx context (adding cross-references, adjusting headings, splitting large files).

### FINDINGS.md split into ~7 pages
The 1700-line monolith has a natural internal structure with clear section breaks. Splitting it into `protocol/ble-communication.md`, `protocol/security.md`, `protocol/modbus-registers.md`, `protocol/device-models.md`, `protocol/encryption-details.md`, `protocol/backend-services.md`, and `protocol/firmware-updates.md` matches the existing headings and makes each page digestible. A `protocol/index.md` serves as a landing page with links to each.

### Single man page covering all CLI
`voltkeeper(1)` covers every subcommand. A single man page is simpler for users (`man voltkeeper`) than multiple scattered pages. Sphinx's built-in `man` builder supports this directly from a single source file.

### GitHub Actions with `peaceiris/actions-gh-pages`
The standard approach for Sphinx-to-GitHub-Pages: build with Python + uv, deploy with `peaceiris/actions-gh-pages@v4` to the `gh-pages` branch. This is battle-tested and minimal configuration.

## Risks / Trade-offs

- **FINDINGS.md split may create orphaned cross-references.** The original file has internal section references. → Mitigation: audit links during adaptation and update to new page targets.
- **MyST parser version compatibility.** MyST and Sphinx versions can drift. → Mitigation: pin known-compatible versions in dev dependencies. The MyST team maintains a compatibility table.
- **Man page accuracy drifts from CLI help text.** The man page is hand-authored, not auto-generated from Click decorators. → Mitigation: scope is small (one page), and CLI help text changes infrequently. Accept the maintenance tax for now.
- **`docs/build/` in `.gitignore` but not `.pre-commit-config.yaml`.** Build artifacts in `docs/build/` could accidentally be checked in. → Mitigation: add `docs/build/` to `.gitignore` and ensure the pre-commit hooks don't touch it.

## Open Questions

- Should the man page source (`docs/source/man/voltkeeper.1.md`) use MyST or native RST syntax? MyST is consistent with the rest of the site, but Sphinx man page docs historically use RST. → TBD during implementation; MyST should work.
