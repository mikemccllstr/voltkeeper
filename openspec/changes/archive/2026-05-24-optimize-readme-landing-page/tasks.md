## 1. Rewrite README.md

- [x] 1.1 Write new README.md with landing page structure: wordmark, badges, value proposition, quick demo, capabilities table, install, requirements, links
- [x] 1.2 Add visual identity: HTML `<img>` tag with raw GitHub URL for wordmark SVG, "voltkeeper" alt text
- [x] 1.3 Add badges: PyPI version, Python versions, CI status, license — each linking to relevant page
- [x] 1.4 Write value proposition section (3-4 bullet points: local-first, offline, no cloud, vendor-neutral)
- [x] 1.5 Add terminal recording placeholder as HTML comment
- [x] 1.6 Write quick demo section with 3-command workflow (scan, status, write)
- [x] 1.7 Write capabilities at a glance table (command | one-line description)
- [x] 1.8 Reorder install section: `pip install voltkeeper` first, then uvx, then from source
- [x] 1.9 Write condensed requirements section
- [x] 1.10 Write links section (docs site, contributing, issues)

## 2. Update Sphinx landing page

- [x] 2.1 Remove "Install" and "Requirements" sections from `docs/source/index.md`
- [x] 2.2 Replace with brief orientation text linking to README and user guide

## 3. Verify

- [x] 3.1 Verify README renders correctly (use local markdown preview or check structure manually)
- [x] 3.2 Run `mise run check` to confirm no regressions
- [x] 3.3 Verify all links in README resolve to correct destinations
