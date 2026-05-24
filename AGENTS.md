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

Run `mise run check` before every commit to ensure lint, types, and tests all pass.
