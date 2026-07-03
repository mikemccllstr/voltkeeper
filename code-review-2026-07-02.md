# Voltkeeper Repository Review — 2026-07-02

A senior-engineer review of the code, specs, docs, and development practices.
Scope: everything tracked in the repo at `bd793b8`, plus test/coverage runs on this
working tree. Recommendations only — no implementation plans.

______________________________________________________________________

## What's strong

**Architecture.** The layering is clean and consistently respected: `core/`
(pure protocol — structs, commands, TLV, device models) knows nothing about BLE;
`bluetooth/` handles transport and the encrypted handshake; `daemon.py` +
`device_manager` + `device_handler` + `bus` + `state_store` compose the service
layer; `cli.py` and `api.py` are thin-ish interface layers. The V1/V2 device
class hierarchy keeps per-model files small (most under 150 lines) with the
shared logic in `v1_base.py` / `v2_base.py`. Capability defaults are chosen so a
new model with nothing overridden still behaves correctly (`WRITABLE_FIELD_NAMES
= []` → clear setter errors).

**Evidence-based protocol work.** Comments cite their sources — APK class names,
method names, even line numbers (`DeviceSettingsWorkingModeActivityV2 line 667`).
The `_checksum` docstring explains *how the claim was proven* ("the challenge
frame proves it"). The pack-voltage-scale comment in `v2_base.py` tells the next
contributor exactly how to verify a new model with a multimeter. This is the
kind of institutional knowledge that usually lives in one person's head.

**Spec discipline.** 29 OpenSpec capability specs with requirement/scenario
structure, plus a dated archive of 31 completed changes. For a solo pre-alpha
project this traceability is exceptional — the ECDH handshake fixes in the git
log each map to a proposal, an implementation, and a spec sync.

**Test and tooling culture.** 714 tests passing in ~17s, branch coverage
enabled, asyncio mode auto, a 5-version CI matrix (3.10–3.14), tox for local
matrix runs, ruff + mypy + sphinx-lint + mdformat all enforced in CI, pre-commit
hooks, mise as the single task runner documented in AGENTS.md. There's even a
test file for the mise tasks themselves. PyPI publishing uses OIDC trusted
publishing (no long-lived tokens) gated behind an environment.

**Docs.** A real Sphinx site with distinct user-guide / protocol / developer
sections, man page builds, auto-deploy to Pages. The protocol docs
(reverse-engineered register maps, encryption details, APK diff reports) are a
genuine asset to anyone else working on Bluetti interop. The README is honest to
a fault about maturity and risk — that candor builds more trust than polish
would.

**API security basics.** Required API key validated with
`hmac.compare_digest`, CIDR allow-list middleware, per-IP rate limiting with a
bounded tracking table. More care than most hobby daemons get.

______________________________________________________________________

## Needs to be addressed (high priority)

### 1. Concurrent `execute()` calls on `BluetoothClient` can cross wires

`DeviceHandler.run()` polls in a loop while `handle_command()` (invoked from the
EventBus when an API/CLI write arrives) calls `self.client.perform_nowait()` on
the **same** `BluetoothClient` (`device_handler.py:97-103`). `execute()`
mutates shared instance state — `_notify_future`, `_current_cmd`,
`_notify_response` (`bluetooth/client.py:60-63`) — with no lock. Both coroutines
run on one event loop, and `execute()` awaits multiple times, so a command
arriving mid-poll will clobber the in-flight poll's future: responses get
matched against the wrong command, producing parse failures, spurious retries,
or (worst case) a write acknowledged against a read's response. An
`asyncio.Lock` around the body of `execute()` is the minimal fix. This matters
most on exactly the path a user cares about — toggling AC output through the
daemon while it's polling.

### 2. Double sleep makes the effective poll interval ~2× the configured value

`_poll_once()` sleeps `interval - elapsed` at its end
(`device_handler.py:128-130`), and then `run()` sleeps `interval` again
(`device_handler.py:90-91`). With `interval: 60` the device is actually polled
roughly every 115–120 seconds. One of the two sleeps should own pacing.
(If this is somehow intentional, it deserves a comment; nothing suggests it is.)

### 3. `voltkeeper --version` reports a hardcoded `0.1.0`

`cli.py:69` pins `click.version_option(version="0.1.0")`, but the project uses
hatch-vcs CalVer (current tag `v2026.05`, PyPI badge on the README). Every bug
report from a user will carry a wrong version string. Read the version from the
generated `voltkeeper._version` (or `importlib.metadata.version("voltkeeper")`)
instead.

### 4. Test coverage is thinnest exactly where the risk is highest

The 69% total hides a sharp split: `core/` is well covered, but the I/O and
action layers are not —

| Module | Coverage | Why it matters |
| --- | --- | --- |
| `bluetooth/client.py` | 34% | retry/notification state machine (see #1) |
| `cli.py` | 39% | the primary user surface |
| `device_handler.py` | 50% | reconnect + poll loop |
| `mqtt_client.py` | 58% | HA integration |
| `shutdown_watch.py` | 61% | **powers off the host** |

`shutdown_watch` is the standout: the one component that takes a destructive
action on someone's machine is among the least tested. Additionally,
`load_test.py` (568 lines) is excluded from coverage entirely via the `omit`
setting — a deliberate choice, but it makes the headline number look better
than reality. Prioritize `shutdown_watch` and the `BluetoothClient`
notification/retry paths; both are testable with fakes (the existing handshake
tests prove the team knows how).

### 5. `cli.py` is a 2,200-line monolith

It mixes command definitions, output formatting (`_print_verbose` alone spans
~280 lines), systemd unit generation, and MQTT orchestration. Its 39% coverage
is a symptom — the formatting and service-file logic is hard to reach through
Click. Split into a `cli/` package (e.g. `scan.py`, `status.py`, `write.py`,
`mqtt.py`, `services.py`, `formatting.py`) with pure, testable formatting
functions. Same story for `tests/test_voltkeeper.py` (3,648 lines, 386 tests) —
split it along the same lines.

______________________________________________________________________

## Opportunities for improvement (medium priority)

### 6. Decide consciously about the embedded Bluetti signing key

`bluetooth/handshake.py:17-23` embeds Bluetti's `LOCAL_AES_KEY` and — more
significantly — the ECDSA **private key** (`PRIVATE_KEY_L1_HEX`) extracted from
the APK, and the package ships to PyPI. Interop projects do this, and MD5/the
key material are protocol-mandated, but redistributing a vendor's private
signing key is the piece most likely to draw a DMCA/trade-secret complaint or a
PyPI takedown. Worth a deliberate decision: keep as-is with a documented
rationale (interoperability under DMCA §1201(f) is the usual argument), or load
key material at runtime from a user-supplied APK. Not a verdict — just make it
a choice rather than a default.

### 7. `config.py` calls `sys.exit(1)` from library code

`load_config()` and `_fail()` print to stderr and exit the process. That's fine
for `voltkeeperd` startup but wrong for every other consumer: the API's reload
handler, tests, and any future library user. Raise a `ConfigError` and translate
to exit-with-message at the CLI/daemon edge. (The `voltkeeperd:` prefix baked
into messages that CLI paths also traverse is a smell from the same root.)

### 8. `docs/findings.html` is load-bearing but orphaned

Code comments cite it by section (`FINDINGS §15.2`, `§15.6`, a TODO about §15.5
vs §15.6 disagreeing) but it's a 60KB raw HTML file outside the Sphinx tree —
not built, not linted, not diffable in review. Much of its content appears to
have migrated to `docs/source/protocol/`. Finish the migration, then update the
code comments to point at the maintained pages, and delete or freeze the HTML.

### 9. API auth/ACL polish

- The bearer token is also accepted as a `?token=` query parameter for
  WebSocket bootstrap — tokens in URLs leak into logs and proxies. Consider
  first-message auth over the socket instead.
- `/` (the web UI) is exempt from auth by path check; fine today since it's a
  static file, but the exemption list will grow — consider an explicit
  public-routes set.
- `_acl_middleware` re-parses every CIDR with `ipaddress.ip_network()` on every
  request even though `ServerConfig.normalized_networks()` exists for exactly
  this. Parse once at startup.

### 10. Keep test output pristine

Two `DeprecationWarning`s from `asyncio.get_event_loop_policy` in
`tests/test_voltkeeper.py` (slated for removal in Python 3.16 — which CI will
adopt). Your own standards call for pristine test output; fix now while it's
two lines.

### 11. CI economics

- The test matrix runs on **every push to every branch** *and* on
  `pull_request` — PRs from branches in this repo run everything twice.
  Restrict `push` to `main` (or add `paths-ignore` for docs-only changes).
- `publish-to-pypi.yml` builds distributions on every push to `main` even
  though publishing only happens on tags; harmless but wasted minutes.

### 12. Small hygiene items

- `cli.py:24` imports `_format_version` — a private name — across module
  boundaries. Rename it public in `core.utils`.
- Two untracked OpenSpec change dirs (`storage-lifecycle-tracking`,
  `storage-prep-command`) are sitting in the working tree; commit the proposals
  so they're versioned like every previous change.
- `BluetoothClient.disconnect()` never calls `stop_notify`, and after a timeout
  retry, stale bytes from the previous attempt can land in a fresh
  `_notify_response`. Mostly masked by CRC validation, but worth tightening
  when you touch #1.
- `scripts/__pycache__` is not gitignored (only the top-level pattern covers
  it — verify) and `htmlcov`/`dist` live in the working tree; fine, just keep
  them out of tar/sdist.

______________________________________________________________________

## Lower priority / strategic

### 13. Define the "supported device" contract

There are ~18 device model files but real-hardware validation on two units
(AC2A, EL100V2 in progress). The register maps for the rest come from APK
analysis. Consider a per-model support tier in the docs (verified-on-hardware /
APK-derived-untested), surfaced in `scan` output. It sets user expectations and
turns "test my device" into a concrete contribution path — which the README
says you want.

### 14. Hardware-in-the-loop test story

Integration tests exist behind a marker, but there's no documented checklist
for what "verified on hardware" means (the `verify` command is a great start).
A short doc — run these commands, expect these outputs, capture a btsnoop —
would let volunteer testers produce actionable reports.

### 15. Release notes

CalVer tags exist and PyPI publishing works, but there's no CHANGELOG or GitHub
release notes. The OpenSpec archive is 90% of the raw material — a small task
that assembles archived change summaries since the last tag would make releases
self-documenting.

______________________________________________________________________

## Prioritized recommendation summary

| # | Recommendation | Effort | Risk addressed |
| --- | --- | --- | --- |
| 1 | Serialize `BluetoothClient.execute()` with an `asyncio.Lock` | S | Command/poll response cross-talk |
| 2 | Remove the double interval sleep in `DeviceHandler` | S | Polling at half the configured rate |
| 3 | Wire `--version` to the real package version | S | Wrong version in every bug report |
| 4 | Test `shutdown_watch`, then `BluetoothClient` retry paths | M | Untested destructive action |
| 5 | Split `cli.py` (and its test file) into a package | M | Untestable formatting/service code |
| 6 | Make an explicit decision on shipping Bluetti key material | S | Takedown exposure |
| 7 | Replace `sys.exit` in `config.py` with a raised error | S | Library usability, reload path |
| 8 | Finish FINDINGS → Sphinx migration; fix code references | M | Orphaned load-bearing doc |
| 9 | API polish: token-in-URL, public-route set, pre-parsed ACL | S | Log leakage, per-request waste |
| 10 | Fix asyncio deprecation warnings in tests | S | Breaks on Python 3.16 |
| 11 | De-duplicate CI triggers | S | Wasted CI minutes |
| 12 | Hygiene batch (private import, untracked specs, stop_notify) | S | Drift |
| 13 | Document per-model support tiers | M | User expectations |
| 14 | Hardware verification checklist for testers | M | Contribution funnel |
| 15 | Release-notes-from-OpenSpec-archive process | S | Release transparency |

Items 1–3 are genuine bugs found during this review and are each small,
verifiable fixes. Items 4–5 are the highest-leverage structural investments.
Everything else can ride along with normal feature work.
