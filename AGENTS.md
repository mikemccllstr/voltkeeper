# Standard Practices

## Test-Driven Development

When writing or changing code, always follow TDD:
1. Write failing tests first
2. Implement the fix
3. Confirm tests pass

## Commit Workflow

Always allow the human to review the proposed commit before committing to git. Present changes for review rather than committing directly.

## Mise Tasks

This project uses [mise](https://mise.jdx.dev/) to define developer tasks. Always prefer `mise run <task>` over invoking tools directly. Available tasks:

| Task | Purpose |
|---|---|
| `mise run lint` | Ruff linter (`ruff check src/ tests/`) |
| `mise run format` | Ruff formatter — applies changes |
| `mise run format-check` | Ruff formatter — check only, no changes (used in CI) |
| `mise run typecheck` | Mypy type checker |
| `mise run test` | Pytest with branch coverage report |
| `mise run test-fast` | Pytest without coverage overhead |
| `mise run coverage` | Pytest + open HTML coverage report |
| `mise run setup` | Install pre-commit hooks (run once after cloning) |
| `mise run check` | Full quality gate: lint + typecheck + test |
| `mise run docs` | Build Sphinx documentation (HTML + man pages) |
| `mise run docs-serve` | Build and serve docs locally (default: http://127.0.0.1:3000) |
| `mise run docs-lint` | Lint docs with sphinx-lint |
| `mise run docs-format` | Format docs with mdformat — applies changes |
| `mise run docs-format-check` | Format check only, no changes (used in CI) |

Run `mise run check` before every commit to ensure lint, types, and tests all pass.

## Bluetti APK Source

The Bluetti Android app v3.0.9 APK has been decompiled and is available under `bluetti-files/BLUETTI-v3.0.9.apk/`:

| Directory | Tool | Contents |
|---|---|---|
| `jadx_out/` | JADX | Java source reconstruction (readable class/method names) |
| `apktool_out/` | apktool | Smali bytecode + resources (AndroidManifest, assets, layouts) |

Use the JADX output (`jadx_out/`) when searching for register definitions, field ranges, enum values, or protocol constants. Use the apktool output for raw resources or assets not present in the JADX tree.
