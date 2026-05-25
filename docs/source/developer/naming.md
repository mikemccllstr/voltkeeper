# Project Naming

This document captures the research and reasoning that informed the project's
name. It exists so contributors can understand why the project is called what
it is, what alternatives were considered, and what risks were identified.

## The brief

We needed a name for a Python package that:

- Manages one or more Bluetti power stations over Bluetooth Low Energy (BLE)
- Exposes a CLI for scanning, connecting, reading status, sending commands,
  and running long-lived service modes
- Aspires to grow a web UI, NUT/UPS integration, and tighter Home Assistant
  integration
- May eventually support adjacent vendors (Anker Solix, Jackery, EcoFlow)

Hard constraints:

1. **Must not infringe Bluetti's trademark**
1. **Must be available on PyPI** and GitHub
1. Should not collide with prominent existing brands, software projects,
   or trademarks in adjacent domains

## The short-list

Five names were short-listed:

| Name             | Verdict      | Key Issue                                     |
| ---------------- | ------------ | --------------------------------------------- |
| `kilowatch`      | Ruled out    | Registered US trademark in our exact category |
| **`voltkeeper`** | **Selected** | Clean across all dimensions                   |
| `wattling`       | Ruled out    | Means wickerwork or poultry anatomy           |
| `jouled`         | Backup       | Pronunciation ambiguity ("joold" vs "jowld")  |
| `amperage`       | Ruled out    | Too generic, SEO competition                  |

## Why voltkeeper

- PyPI: free
- USPTO: no exact match in adjacent classes
- GitHub: no squatter
- Domains: `.com` is parked-for-sale, others free
- Internet: low noise, no competing product or brand
- Friendly cross-language profile
- Unambiguous pronunciation and spelling
- Aligns with the project's ambition — NUT/UPS mode, shutdown watchdog
- Vendor-neutral: survives expansion beyond Bluetti

### Residual risks

- `VoltKeep` Tesla telemetry iOS app (no trailing `-er`) — different product space
- "Volt" is a heavily-used stem (Chevy Volt, VoltDB, Volt Europa) — users need to
  search for "voltkeeper" specifically

## Fallback names

If `voltkeeper` is ever blocked:

1. `jouled` — accept the pronunciation tax
1. A fresh round focused on invented words (`voltique`, `voltify`, `amperic`)

## Methodology

Trademark searches: Justia Trademarks, Trademarkia, USPTO public records.
PyPI availability: HTTP 404 check. Domain availability: HTTP probe + search
cross-reference. No paid trademark searches were performed.
