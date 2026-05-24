## Why

The README.md is the project's home page on both GitHub and PyPI. The current README (262 lines) functions as a full reference manual — listing every subcommand with every option — rather than a landing page that helps someone quickly understand what voltkeeper does and why they'd want it. The "why" (local-first, offline control, no cloud required) doesn't appear at all.

## What Changes

- Reorganize README.md around a landing page structure: what → why → demo → capabilities → install → requirements → links
- Add the voltkeeper visual identity (shield logo + wordmark) with graceful degradation on PyPI
- Add standard badges: PyPI version, supported Python versions, CI status, license
- Add a compact "Capabilities at a Glance" table replacing the 120-line subcommand reference
- Add a placeholder for future terminal recording screenshots
- Move the "Testing" and "Development" sections out of README (developer guide covers them)
- Remove the LICENSE section (GitHub and PyPI both surface it separately)
- Reorder install methods, prioritizing `pip install voltkeeper` (it's on PyPI)
- Strip the duplicated install/requirements content from `docs/source/index.md` so the Sphinx landing page doesn't compete with README

## Capabilities

### New Capabilities
- `readme-landing-page`: The README.md SHALL serve as an effective landing page, communicating the project's value proposition, providing a quick-start path, and linking to full documentation.

### Modified Capabilities
None.

## Impact

- `README.md` — major rewrite (structure, content, visual identity, badges)
- `docs/source/index.md` — minor change (remove duplicated install/requirements content, link to user guide)
