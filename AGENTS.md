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
| `mise run download-apk` | Download the **latest** Bluetti APK (Bluetti CDN, latest-only) |
| `mise run import-apk <path>` | Stage an archived APK into `bluetti-files/<filename>/bluetti.apk` |
| `mise run decompile-jadx` | Decompile all staged APKs with jadx |
| `mise run decompile-apktool` | Disassemble all staged APKs with apktool |
| `mise run diff-apk <verA> <verB>` | Compare two decompiled versions; write artifacts to `bluetti-files/diff/` |
| `mise run cleanup` | Remove derived output under `bluetti-files/`; preserves every `bluetti.apk` |

Run `mise run check` before every commit to ensure lint, types, and tests all pass.

## Bluetti APK Source

`bluetti-files/` is **gitignored and regenerable**. Decompiled output is derived from the APKs in
`bluetti-apk-archive/` (outside the repo). To reconstruct:

```bash
mise run import-apk ../bluetti-apk-archive/BLUETTI-v3.0.9.apk
mise run download-apk          # fetches the current latest (3.0.10 as of 2026-06)
mise run decompile-jadx
mise run decompile-apktool
```

Each decompiled version lives under `bluetti-files/<apk-filename>/`:

| Directory | Tool | Contents |
|---|---|---|
| `jadx_out/` | JADX | Java source reconstruction (readable class/method names) |
| `apktool_out/` | apktool | Smali bytecode + resources (AndroidManifest, assets, layouts) |

Use the JADX output (`jadx_out/`) when searching for register definitions, field ranges, enum
values, or protocol constants. Use the apktool output for raw resources or assets not present in
the JADX tree.

**Acquiring historical versions:** Bluetti's CDN serves only the latest APK. For older versions,
use `mise run import-apk` with a file from `bluetti-apk-archive/` (which holds 2.3.29, 3.0.0,
3.0.7, 3.0.8, 3.0.9, 3.0.10). Do not use `download-apk` to try to fetch specific versions — the
version parameter is not supported by the CDN.

**Version comparison:** Use `mise run diff-apk <verA> <verB>` (e.g., `3.0.9` and `3.0.10`) to
produce a semantic diff across three lenses (protocol anchors, resource surface, cloud API). The
first comparison report is at `docs/source/protocol/apk-v3.0.9-vs-v3.0.10.md`.
