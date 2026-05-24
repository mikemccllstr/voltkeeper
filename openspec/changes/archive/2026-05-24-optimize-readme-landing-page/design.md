## Context

The README.md serves as the project's landing page on both GitHub and PyPI. The current README is 262 lines of reference documentation — listing every subcommand with every option. This is useful for users who already know the tool, but ineffective for discovery. A landing page needs a different structure: what, why, demo, install, then links to full docs.

The project already has a Sphinx documentation site (`docs/source/`) with a full user guide, developer guide, and protocol reference. The detailed subcommand documentation lives there and does not need to be duplicated in README.

## Goals / Non-Goals

**Goals:**
- README communicates what voltkeeper is, why someone would want it, and how to get started — within a single screen of content
- Visual identity (shield logo + wordmark) appears in README, degrading gracefully on PyPI
- Standard project badges (PyPI version, Python versions, CI, license) appear below the logo
- Detailed subcommand reference moves out of README, replaced by a compact capabilities table linking to the docs site
- Testing and development sections move to the developer guide (already exists)
- `docs/source/index.md` is updated to remove content duplicated from the new README

**Non-Goals:**
- Adding terminal recording screenshots (placeholder only)
- Changing the Sphinx site structure or navigation
- Rewriting or moving content in `docs/FINDINGS.md`, `docs/ABOUT.md`, or the Sphinx protocol reference
- Changing any application code

## Decisions

### 1. README content structure

The new structure, in order:

1. **Logo/wordmark** — `<img>` with raw GitHub URL, alt text "voltkeeper"
2. **Badges** — PyPI version, Python versions, CI, license
3. **What** — one-line description (kept from current README)
4. **Why** — 3-4 bullet points on value proposition (local-first, offline, no cloud, vendor-neutral)
5. **Screenshot placeholder** — commented-out Markdown section for future terminal recording
6. **Quick demo** — 3-command workflow (scan → status → write)
7. **Capabilities at a Glance** — compact table with command names and one-line descriptions
8. **Install** — `pip install voltkeeper` first, then uvx quick run, then from source
9. **Requirements** — Python version, BLE adapter, OS support (condensed)
10. **Links** — documentation site, contributing guide, issue tracker

Sections removed: LICENSE (GitHub/PyPI surface it), Testing, Development, full subcommand reference.

**Rationale**: Show the value first (demo + capabilities), then the call to action (install). Removes everything that a landing page visitor doesn't need to decide whether to try the tool.

### 2. Visual identity integration

Use an HTML `<img>` tag pointing to the raw GitHub URL of the wordmark SVG:

```html
<img src="https://raw.githubusercontent.com/mikemccllstr/voltkeeper/main/docs/voltkeeper-wordmark.svg" alt="voltkeeper" height="60">
```

- GitHub renders the SVG inline with `currentColor` adapting to dark/light mode automatically
- PyPI may render the SVG or may fall back to alt text "voltkeeper" — either is acceptable
- A plain `# voltkeeper` heading is NOT used; the wordmark replaces it
- The shield logo is omitted from README — the wordmark alone is cleaner for the landing page context, and the shield would make the header section too tall

**Alternatives considered:**
- Markdown `![voltkeeper](url)` — renders smaller on GitHub, can't control height
- HTML `<picture>` with dark/light variants — unnecessary since the wordmark's `currentColor` handles this automatically
- Inline SVG — rejected; GitHub's Markdown renderer strips `<svg>` tags from markdown

### 3. Badges

Four badges in order: PyPI version, Python versions, CI status, license.

```markdown
[![PyPI](https://img.shields.io/pypi/v/voltkeeper.svg)](https://pypi.org/project/voltkeeper/)
[![Python](https://img.shields.io/pypi/pyversions/voltkeeper.svg)](https://pypi.org/project/voltkeeper/)
[![CI](https://github.com/mikemccllstr/voltkeeper/actions/workflows/ci.yml/badge.svg)](https://github.com/mikemccllstr/voltkeeper/actions/workflows/ci.yml)
[![License](https://img.shields.io/pypi/l/voltkeeper.svg)](https://github.com/mikemccllstr/voltkeeper/blob/main/LICENSE)
```

All badges link to relevant pages (PyPI project, CI runs, license file).

### 4. Capabilities table

A compact Markdown table with two columns: `Command` and `What it does`. Each entry is a one-line description. The detailed option reference lives in the Sphinx user guide. Structured as:

| Command | What it does |
|---|---|
| `scan` | Discover nearby Bluetti devices and show connect commands |
| `status` | Read battery SOC, voltage, load, and charging status |
| `write` | Toggle AC/DC output, change charging mode, adjust settings |
| `mqtt-publish` | Stream device telemetry to MQTT (Home Assistant auto-discovery) |
| `mqtt-listen` | Watch battery SOC over MQTT and shut down host on low battery |
| `load-test` | Run a controlled battery discharge test with CSV logging |
| `probe` | Sweep register blocks for reverse-engineering device support |
| `annotate` | Live-poll and interactively label register fields |

### 5. docs/source/index.md cleanup

Remove the "Install" and "Requirements" sections from `docs/source/index.md`. Replace with a brief "Getting Started" section linking to the README or user guide, plus the existing toctree structure. This avoids the Sphinx landing page competing with the README landing page.

## Risks / Trade-offs

- [Risk] PyPI doesn't render the SVG wordmark → Mitigation: alt text "voltkeeper" is sufficient; the project name still appears
- [Risk] Badges don't render on PyPI → Mitigation: `img.shields.io` badges are widely used and PyPI's renderer handles them; if they fail, the linked text remains clickable
- [Trade-off] Removing the full subcommand reference from README means someone who just cloned the repo needs to follow a link to the docs site or run `--help` → Acceptable; the README's job is conversion, not comprehensive documentation
