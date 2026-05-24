## ADDED Requirements

### Requirement: README landing page structure
The README.md SHALL follow a landing page structure oriented toward project discovery: what, why, demo, capabilities, install, requirements, links. Sections suitable only for contributors (testing, development) SHALL NOT appear.

#### Scenario: User visits GitHub repo page
- **WHEN** a user navigates to the GitHub repository
- **THEN** they see the wordmark, badges, value proposition, a quick demo, a capabilities table, install instructions, and links to full documentation — all within a single screen of content

#### Scenario: User visits PyPI project page
- **WHEN** a user navigates to the PyPI project page
- **THEN** the README renders with the project name visible (either via rendered wordmark or alt text), badges to establish credibility, and a clear path from "what is this" to "how do I try it"

#### Scenario: Testing and development sections are absent
- **WHEN** a contributor reads README.md
- **THEN** no sections titled "Testing" or "Development" appear; those topics are covered in the developer guide linked from README

#### Scenario: LICENSE section is absent
- **WHEN** a user reads README.md
- **THEN** no LICENSE section appears; GitHub and PyPI both surface license information separately

### Requirement: Visual identity
The README SHALL incorporate the voltkeeper visual identity using the wordmark SVG. The wordmark SHALL degrade gracefully when SVG rendering is unavailable by showing "voltkeeper" as alt text.

#### Scenario: Wordmark renders on GitHub
- **WHEN** README.md is viewed on GitHub
- **THEN** the voltkeeper wordmark SVG is displayed with the "volt" half in amber and the "keeper" half adapting to the page's text color via `currentColor`

#### Scenario: Wordmark degrades on PyPI
- **WHEN** README.md is viewed on PyPI and SVG rendering is unavailable
- **THEN** the alt text "voltkeeper" is visible, preserving the project name

### Requirement: Standard project badges
The README SHALL display badges for PyPI version, supported Python versions, CI status, and license. Each badge SHALL link to its relevant page (PyPI project, GitHub Actions CI runs, LICENSE file).

#### Scenario: Badges display on GitHub
- **WHEN** README.md is viewed on GitHub
- **THEN** four badges (PyPI version, Python versions, CI, license) are visible and clickable above the content

#### Scenario: Badges on PyPI
- **WHEN** README.md is viewed on PyPI
- **THEN** badge images or their alt text are visible, providing version and status information

### Requirement: Quick demo section
The README SHALL include a Quick Demo section demonstrating the core workflow (scan, status, write) with code blocks.

#### Scenario: User reads the quick demo
- **WHEN** a user opens README.md
- **THEN** a Quick Demo section shows the three most common commands with brief output descriptions, such that a user can understand the tool's workflow without scrolling past detailed option lists

### Requirement: Capabilities at a Glance
The README SHALL include a Capabilities at a Glance section formatted as a two-column Markdown table (Command | What it does) listing all CLI subcommands with one-line descriptions. The full option reference SHALL link to the Sphinx user guide.

#### Scenario: User scans the capabilities table
- **WHEN** a user reads the Capabilities table
- **THEN** they see each subcommand name and a single-sentence description of its purpose, with a link to the full user guide for detailed options

#### Scenario: Full option reference is not in README
- **WHEN** a user reads README.md
- **THEN** no per-subcommand option flags (e.g., `--timeout`, `--broker`, `--port`) appear; those details are accessible via the linked documentation

### Requirement: Install section with PyPI priority
The install section SHALL list `pip install voltkeeper` as the primary install method, followed by `uvx` quick run and from-source instructions.

#### Scenario: User installs via pip
- **WHEN** a user reads the install section
- **THEN** `pip install voltkeeper` is the first and most prominent install method

### Requirement: Terminal recording placeholder
The README SHALL include a placeholder for future terminal recording screenshots, formatted as an HTML comment so it is invisible in rendered output but discoverable by contributors.

#### Scenario: Placeholder is invisible to readers
- **WHEN** README.md is rendered on GitHub or PyPI
- **THEN** the placeholder does not produce visible content but is present in the raw Markdown source

### Requirement: Sphinx landing page de-duplication
`docs/source/index.md` SHALL NOT duplicate the install or requirements content from README.md. It SHALL provide a brief orientation and rely on the README for installation guidance.

#### Scenario: Sphinx landing page does not duplicate README
- **WHEN** a user opens the Sphinx documentation site
- **THEN** the landing page does not contain an "Install" or "Requirements" section that mirrors README content; instead it provides a brief orientation and links to the user guide
