# Probe and Annotate

Reverse-engineering tools for new device models.

## probe

Connects to the device, sweeps all known register blocks, and writes a
YAML profile. Useful for device reverse-engineering and new-model support.

```bash
voltkeeper probe AA:BB:CC:DD:EE:FF -o device.yaml
```

## validate-profile

Parses the register blocks in a probe YAML and flags fields with suspect
values (stuck-at-zero, all-0xFFFF, out of range).

```bash
voltkeeper validate-profile device.yaml
```

## annotate

Live-polls the device and highlights byte-level changes in real time.
Prompts for field names at each changed offset, saving annotations
incrementally to a YAML draft. Press Ctrl-C to stop.

```bash
voltkeeper annotate AA:BB:CC:DD:EE:FF -o draft.yaml
```

## Workflow

These three commands form a pipeline for adding support for an unfamiliar
Bluetti device:

1. **probe** — capture raw register data
2. **validate-profile** — check for obviously invalid values
3. **annotate** — identify fields that change during operation

See [Contributing Devices](../developer/contributing-devices.md) for the
full step-by-step guide.
