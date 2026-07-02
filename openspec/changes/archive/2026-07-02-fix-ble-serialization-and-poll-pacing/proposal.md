## Why

Two live bugs sit on the daemon's main path. First, `DeviceHandler`'s polling loop and its EventBus command listener both call `execute()` on the same `BluetoothClient`, which mutates shared per-command state (`_notify_future`, `_current_cmd`, `_notify_response`) with no serialization — a write arriving mid-poll can clobber the in-flight poll's future, causing responses to be matched against the wrong command (spurious retries, parse failures, or a write acknowledged against a read's response). Second, both `DeviceHandler.run()` and `_poll_once()` sleep the poll interval, so a configured 60-second interval actually polls roughly every 115–120 seconds.

## What Changes

- `BluetoothClient.execute()` serializes concurrent callers: only one command is in flight per client at a time; a command issued while another is pending waits for it to complete rather than corrupting its state.
- `DeviceHandler` paces polling from a single point: the effective poll period equals the configured interval (measured start-to-start, i.e. sleep `interval - elapsed`), removing the duplicate sleep.
- No CLI, API, or config surface changes.

## Capabilities

### New Capabilities

- `ble-command-serialization`: One-command-in-flight guarantee for a `BluetoothClient` shared between the polling loop and bus-driven command execution.
- `poll-interval-pacing`: The device polling loop honors the configured interval as the actual start-to-start poll period.

### Modified Capabilities

<!-- none — time-sliced-polling covers register-block selection per cycle, not loop pacing; no existing spec covers command execution concurrency -->

## Impact

- `src/voltkeeper/bluetooth/client.py` — serialize `execute()` (asyncio.Lock around the command lifecycle).
- `src/voltkeeper/device_handler.py` — remove the duplicate interval sleep in `run()`; `_poll_once()` owns pacing.
- Tests: new unit tests for concurrent `execute()` interleaving and for effective poll period; existing `device_handler`/client tests may need timing adjustments.
- Behavior change users will notice: devices polled at the configured rate (roughly twice as often as before); MQTT/HA data freshness improves accordingly.
