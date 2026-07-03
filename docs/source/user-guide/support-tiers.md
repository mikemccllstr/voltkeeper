# Device Support Tiers

Voltkeeper classifies each supported device model into one of three support tiers.
The tier tells you how much real-world testing the model has received and what to
expect when you connect.

## What "supported" means

A model is **supported** when voltkeeper knows its register map and can communicate
with it at the protocol level. All models listed in the
[device model catalog](../protocol/device-models.md) are supported in this sense
regardless of tier.

The tier describes *verification status* — whether the implementation has been
confirmed to work on real hardware.

## Tier definitions

### Verified on Hardware

`HARDWARE_VERIFIED` — A community member has run `voltkeeper verify` on a physical
unit and all checks passed. This is the highest confidence level. The model's
register map, control commands, and field parsing have been confirmed against live
data from a real device.

### In Testing

`HARDWARE_TESTING` — At least one community member has connected to a physical unit
and confirmed the core flows work: BLE connection, handshake (for encrypted devices),
and live-data parsing. The model has not yet completed a full `voltkeeper verify`
run, so some fields may not behave as expected.

### APK-Derived

`APK_DERIVED` — The model's register map and field definitions were derived from
the official Bluetti Android app (APK decompilation) and have never been tested on
real hardware. Basic communication may work, but there are no guarantees. Field
values, scaling factors, and control commands might produce unexpected results.

## Promotion criteria

A model's tier is promoted when a community member provides hardware evidence.

| Transition                | Criterion                                                                                                                                                                                     |
| ------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `APK_DERIVED` → `TESTING` | Core flows confirmed on a real unit: BLE connect, handshake (if encrypted), live-data parse                                                                                                   |
| `TESTING` → `VERIFIED`    | Verify stages 1–3 pass and stage 4 passes under a connected load on real hardware (stages 5–6 are encouraged but optional). See the [verify reference](verify.md) for what each stage covers. |

Follow the [Test your device](test-your-device.md) walkthrough to produce a report. Then submit
it through the [device report form](https://github.com/mikemccllstr/voltkeeper/issues/new?template=device-report.yml).

## How to check a model's tier

- **Scan output:** `voltkeeper scan` shows the tier next to each discovered device
- **Model catalog:** Each table in the [device model catalog](../protocol/device-models.md) has a Support column
- **Contribution hint:** When `voltkeeper scan` finds a device that is not yet verified,
  it prints a hint pointing back to this page
