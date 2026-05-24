## 1. Dependencies and scaffolding

- [x] 1.1 Add `sphinx`, `myst-parser`, and `furo` to `dev` dependency group in `pyproject.toml`
- [x] 1.2 Run `uv sync` to install new dependencies
- [x] 1.3 Create `docs/source/` directory and subdirectories: `user-guide/`, `developer/`, `protocol/`, `about/`, `api/`, `man/`
- [x] 1.4 Create `docs/source/_static/` for custom CSS and logo assets
- [x] 1.5 Add `docs/build/` to `.gitignore`

## 2. Sphinx configuration

- [x] 2.1 Create `docs/source/conf.py` with MyST parser extension, Furo theme, and man page builder configuration
- [x] 2.2 Configure `conf.py` to suppress `.venv` and `__pycache__` from any future autodoc path resolution

## 3. Landing page and navigation

- [x] 3.1 Create `docs/source/index.md` as the root toctree with links to all major sections (User Guide, Developer Guide, Protocol Reference, About, API Reference)
- [x] 3.2 Verify `mise run docs` produces a working HTML site with the root page and correct toctree

## 4. User Guide content

- [x] 4.1 Create `docs/source/user-guide/index.md` adapting installation, requirements, and quickstart content from `README.md` and `docs/ABOUT.md`
- [x] 4.2 Create `docs/source/user-guide/scan.md` from README scan documentation
- [x] 4.3 Create `docs/source/user-guide/status.md` from README status documentation
- [x] 4.4 Create `docs/source/user-guide/write.md` from README write documentation
- [x] 4.5 Create `docs/source/user-guide/mqtt.md` from README mqtt-publish and mqtt-listen documentation
- [x] 4.6 Create `docs/source/user-guide/load-test.md` from README load-test documentation
- [x] 4.7 Create `docs/source/user-guide/probe-annotate.md` from README probe, annotate, and validate-profile documentation
- [x] 4.8 Create `docs/source/user-guide/systemd.md` from README systemd service generation documentation

## 5. Developer Guide content

- [x] 5.1 Create `docs/source/developer/index.md` with architecture overview, repository structure, and development workflow (TDD, `mise run check`)
- [x] 5.2 Create `docs/source/developer/contributing-devices.md` adapted from `docs/CONTRIBUTING_DEVICES.md`
- [x] 5.3 Create `docs/source/developer/maintaining.md` adapted from `docs/MAINTAINING.md`

## 6. Protocol Reference content (split FINDINGS.md)

- [x] 6.1 Create `docs/source/protocol/index.md` as a landing page with overview of the protocol section
- [x] 6.2 Create `docs/source/protocol/ble-communication.md` from FINDINGS.md sections on GATT service, characteristics, and scan data patterns
- [x] 6.3 Create `docs/source/protocol/security.md` from FINDINGS.md sections on legacy challenge-response and ECDH+ECDSA handshake
- [x] 6.4 Create `docs/source/protocol/modbus-registers.md` from FINDINGS.md sections on V1 and V2 register maps and address ranges
- [x] 6.5 Create `docs/source/protocol/device-models.md` from FINDINGS.md sections listing supported models and protocol generations
- [x] 6.6 Create `docs/source/protocol/encryption-details.md` from FINDINGS.md sections on AES-128-CBC, IV chaining, and hardcoded keys
- [x] 6.7 Create `docs/source/protocol/backend-services.md` from FINDINGS.md sections on microservice architecture, endpoints, and MQTT broker
- [x] 6.8 Create `docs/source/protocol/firmware-updates.md` from FINDINGS.md sections on BLE local transfer, MQTT OTA, and broadcast upgrades

## 7. About section content

- [x] 7.1 Create `docs/source/about/index.md` adapted from `docs/ABOUT.md`
- [x] 7.2 Create `docs/source/about/naming.md` adapted from `docs/NAMING.md`
- [x] 7.3 Create `docs/source/about/brand.md` adapted from `docs/BRAND.md`

## 8. API placeholder

- [x] 8.1 Create `docs/source/api/index.md` with a stub page indicating API reference is planned for a future release

## 9. Man page

- [x] 9.1 Create `docs/source/man/voltkeeper.1.md` documenting all CLI subcommands and their options
- [x] 9.2 Verify man page output is generated alongside HTML when `mise run docs` runs

## 10. Mise task

- [x] 10.1 Add `[tasks.docs]` to `mise.toml` with description and run command to build Sphinx HTML and man pages into `docs/build/`

## 11. GitHub Actions deployment

- [x] 11.1 Create `.github/workflows/docs.yml` to build Sphinx docs and deploy to `gh-pages` on push to `main`
- [x] 11.2 Configure workflow to use `uv sync --group dev` for dependency installation and `mise run docs` for the build step
- [x] 11.3 Configure `peaceiris/actions-gh-pages@v4` to deploy `docs/build/html/` to `gh-pages` branch

## 12. Verification

- [x] 12.1 Run `mise run docs` and confirm zero Sphinx warnings
- [x] 12.2 Open `docs/build/html/index.html` in a browser and verify all pages render correctly with navigation
- [x] 12.3 Verify all internal cross-references resolve (no broken links in build output)
- [x] 12.4 Run `man -l docs/build/man/voltkeeper.1` and confirm all commands appear
- [x] 12.5 Run `mise run check` to ensure no regressions in existing quality gates
