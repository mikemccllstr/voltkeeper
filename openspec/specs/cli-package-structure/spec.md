## Requirements

### Requirement: CLI entry point stability across the package split

The console entry point `voltkeeper.cli:cli` and the import `from voltkeeper.cli import cli` SHALL continue to resolve to the root Click group after `cli.py` becomes the `cli/` package. Importing `voltkeeper.cli` SHALL register every command exactly once.

#### Scenario: Installed entry point resolves
- **WHEN** `voltkeeper --help` runs from an installed environment after the split
- **THEN** it exits 0 and lists the same commands as before the split

#### Scenario: Programmatic import resolves
- **WHEN** test code executes `from voltkeeper.cli import cli`
- **THEN** the imported object is the root Click group with all commands and groups (`daemon`, `config`) attached

### Requirement: Command surface unchanged by the split

The package split SHALL NOT change any command name, option, default value, help text, output format, or exit code. Function bodies SHALL move without modification; only import statements and module headers may differ.

#### Scenario: Help output identical
- **WHEN** `voltkeeper --help`, `voltkeeper daemon --help`, and `voltkeeper config --help` are captured before and after the split
- **THEN** the outputs are identical

#### Scenario: Existing test suite passes unmodified in behavior
- **WHEN** the full test suite runs after the source split with only import paths and patch targets updated
- **THEN** every test passes without any assertion change

### Requirement: One module per command group

The `cli/` package SHALL contain one module per command group (scan, status, write, mqtt, services, load-test, verify, daemon, config), a shared helpers module, and an `__init__` that exposes the root group. A helper function used by a single command module SHALL live in that module; helpers used by more than one SHALL live in the shared helpers module.

#### Scenario: Helper placement follows usage
- **WHEN** a helper (e.g. `_make_unit_file`) is used only by commands in one module (here, `daemon install`)
- **THEN** it is defined in that command module, not in the shared helpers module
