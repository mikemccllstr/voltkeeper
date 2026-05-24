# sphinx-docs Specification

## Purpose
TBD - created by archiving change add-sphinx-documentation. Update Purpose after archive.
## Requirements
### Requirement: Sphinx site with MyST Markdown parser
The project SHALL provide a Sphinx documentation site configured to parse Markdown files via MyST parser, so that existing and new content can be authored in Markdown rather than reStructuredText.

#### Scenario: Sphinx build succeeds from Markdown source
- **WHEN** `mise run docs` is executed
- **THEN** Sphinx builds HTML output from `docs/source/**/*.md` files without errors

#### Scenario: MyST parser handles cross-references in Markdown
- **WHEN** a Markdown page contains `[](../page.md)` or `[](ref:some-label)` syntax
- **THEN** Sphinx resolves the reference to the correct target page in the output

### Requirement: Furo theme
The documentation site SHALL use the Furo theme with responsive layout, dark/light mode toggle, and left-sidebar navigation.

#### Scenario: Responsive layout on mobile
- **WHEN** the site is viewed on a device with viewport width under 768px
- **THEN** the left sidebar collapses into a hamburger menu and content remains readable

#### Scenario: Dark mode toggle available
- **WHEN** the site loads
- **THEN** a theme toggle control is visible in the header

### Requirement: Audience-organized content structure
The documentation SHALL be organized into sections targeting different audiences: user-guide (CLI users), developer (contributors/maintainers), protocol (reverse-engineering reference), and about (project story).

#### Scenario: User arrives at the landing page
- **WHEN** a user navigates to the documentation site root
- **THEN** the page presents an overview linking to all major sections

#### Scenario: User navigates to the user guide
- **WHEN** a user clicks "User Guide" in the navigation
- **THEN** they see installation instructions, CLI command reference, MQTT configuration, and load test documentation

#### Scenario: Developer navigates to protocol reference
- **WHEN** a user clicks the protocol section in the navigation
- **THEN** they see pages covering BLE communication, security handshakes, Modbus register maps, device models, encryption details, backend services, and firmware update flows

### Requirement: Content migration from existing docs
The Sphinx source tree SHALL adapt content from the existing `docs/*.md` files, with `FINDINGS.md` broken into multiple pages under the protocol section.

#### Scenario: User reads ABOUT content in the published site
- **WHEN** a user navigates to the About section
- **THEN** they see pages covering project origins, the naming process, and brand assets

#### Scenario: User reads developer content in the published site
- **WHEN** a user navigates to the Developer section
- **THEN** they see the contributing-devices guide and maintainer guide

#### Scenario: Protocol reference is split into navigable pages
- **WHEN** a user opens the protocol section
- **THEN** they see an index page with links to individual topic pages (BLE communication, security, registers, etc.) rather than one 1700-line page

### Requirement: Excluded development artifacts
`IMPLEMENTATION_UNITS.md` and `MULTI_DEVICE_PLAN.md` SHALL NOT appear in the published documentation site.

#### Scenario: Archived plans are not discoverable from the doc site
- **WHEN** a user browses or searches the documentation site
- **THEN** no content from IMPLEMENTATION_UNITS.md or MULTI_DEVICE_PLAN.md appears

### Requirement: API documentation placeholder
The Sphinx site SHALL include an `api/` section with a placeholder page indicating that API reference documentation will be added when the public API stabilizes.

#### Scenario: User navigates to API docs
- **WHEN** a user clicks the API section in the navigation
- **THEN** they see a page stating API documentation is planned for a future release

### Requirement: Man page generation
The Sphinx build SHALL generate a `voltkeeper(1)` man page covering all CLI-accessible subcommands.

#### Scenario: Man page is built alongside HTML
- **WHEN** `mise run docs` completes
- **THEN** `docs/build/man/voltkeeper.1` exists and can be viewed with `man -l docs/build/man/voltkeeper.1`

#### Scenario: Man page covers all CLI commands
- **WHEN** a user views `voltkeeper(1)`
- **THEN** all accessible subcommands (scan, status, write, mqtt-publish, mqtt-listen, mqtt-publish-service, mqtt-listen-service, probe, annotate, validate-profile, load-test) are documented with their options

### Requirement: Mise docs task
The project SHALL provide a `mise run docs` task that builds both HTML and man page output from the Sphinx source.

#### Scenario: First build succeeds
- **WHEN** a developer runs `mise run docs` on a fresh checkout after installing dev dependencies
- **THEN** `docs/build/html/index.html` and `docs/build/man/voltkeeper.1` are produced without errors

