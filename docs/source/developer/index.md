# Developer Guide

```{toctree}
:hidden:

contributing-devices
maintaining
```

## Setup

```bash
git clone https://github.com/mikemccllstr/voltkeeper
cd voltkeeper
uv sync --group dev
mise run setup
```

Installs dependencies, then sets up pre-commit hooks (lint, format, typecheck) that
run automatically on every commit. The CI will catch it if you skip this step, but
you'll save yourself a round-trip.

## Architecture

voltkeeper is organized into three main packages under `src/voltkeeper/`:

| Package | Purpose |
|---|---|
| `bluetooth/` | BLE client, scan, device factory, encryption, handshake |
| `core/` | Modbus commands, field struct definitions, device model hierarchy |
| `core/devices/` | Per-model device classes (V1 and V2 protocol) |

Top-level modules handle CLI commands (`cli.py`), device polling (`device_handler.py`),
MQTT integration (`mqtt_client.py`), load testing (`load_test.py`), probe and
annotation (`probe.py`, `annotate.py`), validation (`validate.py`), the background
daemon (`daemon.py`, `device_manager.py`), the HTTP API (`api.py`), and the web
UI (`webui/`).

## Development workflow

All work follows test-driven development. The full quality gate is:

```bash
mise run check
```

This runs lint, typecheck, and tests. Individual checks:

| Task | What it runs |
|---|---|
| `mise run lint` | Ruff linter |
| `mise run typecheck` | Mypy type checker |
| `mise run test` | Pytest with branch coverage |
| `mise run test-fast` | Pytest without coverage overhead |
| `mise run format` | Ruff formatter (applies changes) |
| `mise run setup` | Install pre-commit hooks (run once after cloning) |
| `mise run format-check` | Ruff formatter (check only) |

## Building documentation

```bash
mise run docs
```

Builds both HTML and man page output from the Sphinx source tree.

## Commit style

Lowercase imperative, single line, no period:

```
add cipher module: aes-128-cbc with chained iv per FINDINGS §15.8
```

## Adding a new device

See [Contributing Devices](contributing-devices.md) for the contributor guide
and [Maintainer Guide](maintaining.md) for merging submissions.
