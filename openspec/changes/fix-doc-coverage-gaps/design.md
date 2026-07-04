## Context

A spec-vs-docs review identified 19 documentation gaps. The docs are the user-facing
surface of voltkeeper -- the man page is the primary CLI reference, the README is the
landing page, and the Sphinx site is the comprehensive reference. Gaps in these
sources mean users cannot discover features that exist in the code.

The changes fall into three categories: (1) adding missing CLI entries to the man
page and README, (2) creating an HTTP API reference section, and (3) filling in
missing flag/feature documentation in existing user-guide pages.

## Goals / Non-Goals

**Goals:**
- Cover every CLI command and option in the man page
- Cover every CLI command in the README capabilities table
- Provide a structured reference for the daemon HTTP API
- Create the GitHub issue template that users are already being linked to
- Fill in missing CLI flag docs (--help-field, --device-type, --daemon, --no-restart-on-source-change)
- Document the Web UI and software versions in status output
- Update backend-services.md with 3.0.10 endpoint additions

**Non-Goals:**
- Rewrite or restructure existing docs
- Add Python API reference (still deferred per api/index.md note)
- Add new documentation pages beyond the HTTP API reference section
- Change CLI behavior or flags
- Fix the load-test hardcoded AC2A filename (separate concern)

## Decisions

### HTTP API reference location
**Decision:** Add a "## HTTP API Reference" section to the existing daemon.md
user-guide page. Do not create a new standalone page.

**Rationale:** The daemon page already describes the daemon architecture and CLI
management commands. Adding the API reference there keeps the daemon topic
self-contained. A separate page would fragment the daemon documentation across
two files for a topic that is still relatively small (~8 endpoints).

### Man page structure for new commands
**Decision:** Follow the existing pattern -- each command gets a ### subsection
with a synopsis line, brief description, and an options table.

### Issue template format
**Decision:** Use the standard GitHub YAML issue form format matching the
structure described in test-your-device.md (model, firmware, voltkeeper
version, OS, adapter, verify report, claimed tier).

### Software versions section in status.md
**Decision:** Add a short subsection describing the software versions available
in verbose mode (ARM, DSP, BMS, IOT, HMI1, HMI2), explaining how they are
parsed from the MCU firmware entries per the software-version-display spec.

## Risks / Trade-offs

- **API reference staleness risk**: The HTTP API reference is now a second
  source of truth alongside the api.py source. However, the reference is
  intentionally kept at a user-facing level (endpoint paths, methods, params)
  rather than implementation detail, reducing staleness.
- **Man page maintenance burden**: Adding 3 new command groups increases the
  man page from 163 to approximately 250+ lines. Each future CLI change now
  has more surface area to update. Mitigation: The man page already covered 10
  commands; adding 3 follows the same pattern and test coverage can verify
  consistency.
