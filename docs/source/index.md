# voltkeeper

CLI tool for Bluetti power stations — scan, connect, and read battery data over BLE.

```{toctree}
:maxdepth: 1
:caption: User Guide
:hidden:

user-guide/index
```

```{toctree}
:maxdepth: 1
:caption: Developer Guide
:hidden:

developer/index
```

```{toctree}
:maxdepth: 1
:caption: Protocol Reference
:hidden:

protocol/index
```

```{toctree}
:maxdepth: 1
:caption: About
:hidden:

about/index
```

```{toctree}
:maxdepth: 1
:caption: API Reference
:hidden:

api/index
```

## Install

### Quick run (no clone required)

```bash
uvx --from git+https://github.com/mikemccllstr/voltkeeper voltkeeper --help
```

### From source

```bash
git clone https://github.com/mikemccllstr/voltkeeper
cd voltkeeper
uv run voltkeeper --help
```

## Quick start

```bash
voltkeeper scan              # find nearby Bluetti devices
voltkeeper status            # read battery status
voltkeeper status AA:BB:CC:DD:EE:FF  # connect directly
voltkeeper write AA:BB:CC:DD:EE:FF ac_output on   # toggle AC
```

## Requirements

- Python 3.13+
- Linux with BlueZ, macOS 11+, or Windows 10 build 19041+ (BLE support)
- Bluetooth adapter with scan capability

```{toctree}
:hidden:

man/voltkeeper.1
```
