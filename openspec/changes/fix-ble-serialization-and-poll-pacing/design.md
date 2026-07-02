## Context

`BluetoothClient` (`src/voltkeeper/bluetooth/client.py`) tracks the in-flight command in instance attributes: `_current_cmd`, `_notify_future`, and `_notify_response`. The BLE notification callback `_on_notification` resolves `_notify_future` by matching accumulated bytes against `_current_cmd.response_size()`. This design assumes exactly one command in flight at a time.

`DeviceHandler` (`src/voltkeeper/device_handler.py`) violates that assumption: its `run()` polling loop calls `client.execute()` repeatedly, while `handle_command()` — registered as an EventBus command listener and invoked when an API or CLI write arrives — calls `client.perform_nowait()` (which calls `execute()`) on the same client. Both coroutines run on one event loop, and `execute()` awaits several times (`write_gatt_char`, `wait_for`), so interleaving is real: the second caller overwrites `_notify_future`/`_current_cmd`, orphaning the first caller's future (it times out and retries) or, worse, resolving one command's bytes against another command's parser.

Separately, the poll loop sleeps twice per cycle: `_poll_once()` ends with `await asyncio.sleep(self.interval - elapsed)` and `run()` follows the call with `await asyncio.sleep(self.interval)`. Effective period ≈ 2×interval − elapsed.

## Goals / Non-Goals

**Goals:**
- One command in flight per `BluetoothClient` at any time; concurrent callers queue.
- Effective poll period equals the configured interval, measured start-to-start, with a single pacing point.
- Preserve existing retry, timeout, encryption, and response-validation behavior unchanged.

**Non-Goals:**
- Command prioritization (e.g. letting a user write jump ahead of queued polls).
- Fixing `disconnect()`'s missing `stop_notify` or draining stale notification bytes between retries (tracked separately in the 2026-07-02 review, item 12).
- Any change to polling block selection (time-sliced-polling capability) or to CLI/API surfaces.

## Decisions

**1. Serialize with an `asyncio.Lock` inside `execute()`, not in callers.**
The invariant belongs to the class that owns the state. Guarding in `DeviceHandler` would leave every other `BluetoothClient` user (CLI one-shots, future API paths) unprotected. The lock is created in `__init__` and wraps the entire retry loop body of `execute()`, so a queued command never observes a half-torn-down `_notify_future`.

Alternative considered: an `asyncio.Queue`-based command worker task. Rejected — a materially bigger rewrite of `execute()` for no behavioral gain at this concurrency level (two callers), and it complicates timeout/retry semantics.

**2. Lock scope covers the whole command lifecycle including retries.**
If the lock were acquired per attempt, a queued command could interleave between retries of a failing command and inherit its stale notification bytes. Holding the lock for the full `execute()` call keeps the state machine simple. Worst-case queue delay is bounded by `MAX_RETRIES × RESPONSE_TIMEOUT` (25 s), which is acceptable for a bus-driven write.

**3. `run()` owns pacing; `_poll_once()` loses its sleep.**
Of the two sleeps, keep the one in the loop that also handles reconnect back-off, and make it start-to-start: `run()` records the cycle start time, calls `_poll_once()`, then sleeps `max(0, interval - elapsed)`. `_poll_once()` becomes purely "issue this cycle's commands." This keeps all timing logic in one visible place.

Alternative considered: keep pacing in `_poll_once()` and delete the sleep in `run()`. Rejected — `run()` already sleeps for connect-failure back-off, so timing responsibility would be split across both methods either way; concentrating it in `run()` is clearer.

## Risks / Trade-offs

- [A hung command delays queued commands up to ~25 s] → Bounded by existing `MAX_RETRIES × RESPONSE_TIMEOUT`; unchanged from what a solo caller already experiences. Prioritization is out of scope until it's demonstrably needed.
- [Doubling the real poll rate doubles BLE traffic] → The configured interval was always the intent; users who tuned `interval` around the buggy behavior can halve it. Call this out in the change summary.
- [Timing-sensitive existing tests may assume the double sleep] → Run the full suite; adjust only tests that encoded the buggy period.

## Migration Plan

No config or API migration. Single deployable change; rollback is a revert. Note the effective-poll-rate change in the commit/release message since users may observe more frequent MQTT updates.

## Open Questions

None.
