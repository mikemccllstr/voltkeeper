## 1. BLE command serialization

- [ ] 1.1 Write failing tests for `BluetoothClient.execute()` serialization: two concurrent `execute()` calls each receive their own response (no cross-matching); the second is not written until the first completes; a queued call runs cleanly after the first exhausts retries; no interleaving between retry attempts
- [ ] 1.2 Add an `asyncio.Lock` to `BluetoothClient.__init__` and acquire it around the full retry loop in `execute()`; confirm tests pass
- [ ] 1.3 Write a failing `DeviceHandler` test: a `CommandMessage` handled mid-poll completes without corrupting the in-flight poll (both get their own responses, no spurious timeouts); confirm it passes with the lock in place

## 2. Poll interval pacing

- [ ] 2.1 Write failing tests for effective poll period: start-to-start period equals the configured interval when a cycle finishes early; a cycle longer than the interval starts the next cycle immediately; interval 0 polls back-to-back
- [ ] 2.2 Remove the trailing sleep from `_poll_once()`; make `run()` record cycle start time and sleep `max(0, interval - elapsed)` once per cycle; confirm tests pass
- [ ] 2.3 Run the full suite; fix any existing tests that encoded the double-sleep period

## 3. Docs and verification

- [ ] 3.1 Check `docs/source/user-guide/daemon.md` and `mqtt.md` for statements about poll interval behavior; update if they describe or work around the old effective rate (no nav changes expected — verify none needed)
- [ ] 3.2 Run `mise run check` (lint, typecheck, tests, docs lint/format) and confirm clean
- [ ] 3.3 Note the user-visible poll-rate change (devices now polled at the configured interval, ~2× the previous effective rate) in the commit message
