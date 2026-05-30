# Handoff: V2 encrypted handshake — bookkeeping reshape + next steps

Status as of this session (nothing pushed; all commits local on branch `elite-100v2`).

## What is DONE and correct (keep it)

- **Implementation commit `82d4871`** — the code is hardware/offline-confirmed, keep it:
  - `handshake.py`: consumes the `2A 2A 03 01 <status>` status-ack as a separate frame; ECDH
    plaintext offsets corrected to pubkey `[4:68]` / signature `[68:132]`.
  - `tests/test_handshake_state_machine.py`, `docs/source/protocol/security.md` updated to match.
  - Full suite: **666 passed**, pre-commit (ruff/mypy/docs) green.
  - NOTE: this commit ALSO contains bookkeeping churn (edits under
    `openspec/changes/fix-v2-handshake-stage2/`). The CODE is what matters; the change-dir edits
    are the part to redo.
- **Proposal commit `805791a`** — created the new change `fix-v2-encrypted-frame-codec` (proposal,
  design, specs, tasks). Validated clean. This is the forward-looking change and is correct.

## Three hardware-confirmed framing facts (the substance — drives the new change)

Captured from live Elite 100 V2 `DC:B4:D9:46:73:96` + APK `net.poweroak` source
(`ConnectManager.bleEncryptedHandle`, `ProtocolParse.buildAESCBCCmd`/`parseAESCBCData`):

1. **2-byte BE length prefix on EVERY encrypted frame**: `[%04X plaintext_len][ciphertext]`.
   The captured ECDH notification is 146 bytes = `00 86`(=134) + 144 ciphertext. Strip prefix
   before decrypt; trim decrypted output to `plaintext_len`. Prepend on outbound.
2. **ECDSA signature message hex-decodes randomMd5**: message = `pubkey(64) || bytes.fromhex(md5)(16)`
   = 80 bytes. Confirmed: 80-byte hex form VERIFIES against K2; 96-byte ASCII form FAILS. Fix BOTH
   `verify_device_pubkey` and `sign_app_pubkey` (currently use `.encode("ascii")`).
3. **Post-handshake frames embed a per-frame IV**: with `bleConnShareKey`, layout is
   `[len][4-byte random seed][ciphertext]`, IV = `MD5(seed)`. Handshake stage (`bleConnAESKey`)
   stays `[len][ciphertext]`, IV = `bytes.fromhex(randomMd5)`, CBC-chained.

All three are written up in `proposal.md` / `design.md` (decisions 1-4) / `specs/.../spec.md`
(3 ADDED requirements) / `tasks.md` (10 task groups, TDD-ordered). Ready for `/opsx:apply`.

## Bookkeeping to REDO (the "fold + reshape" that did not complete cleanly)

User decision: keep implementation, redo bookkeeping. Original intent was "fold into new change."
The session instead committed a trim+separate-change variant and the archive aborted. To reshape:

1. The OLD change `fix-v2-handshake-stage2` still exists as an active change dir. Its status-ack +
   ECDH-offset requirements are the only CORRECT parts; its design D3 (ASCII signature) and D4
   (reset-vs-chained IV) were DISPROVEN this session.
2. Decide: either (a) keep `fix-v2-handshake-stage2` as a thin, now-correct change covering only
   status-ack + offsets and archive it, OR (b) fold those two requirements into
   `fix-v2-encrypted-frame-codec` and delete the old change dir. (User leaned "fold".)
3. The implementation code in `82d4871` stands regardless of which change "owns" it.

## BLOCKER: canonical spec is malformed (pre-existing, independent bug)

`openspec/specs/ble-encrypted-handshake/spec.md` line 1 is `## ADDED Requirements` (a DELTA header
left behind by archive commit `22fa205`). Main specs must use `## Requirements`. This makes its 4
legacy requirements invisible to validate/list/archive and causes `openspec archive` to ABORT.

Fix: change line 1 from `## ADDED Requirements` to `## Requirements` (and confirm the 4 legacy
requirements then parse). This must be fixed BEFORE any `openspec archive` of a change touching
`ble-encrypted-handshake` will succeed. The canonical spec does NOT currently contain the disproven
mutual-auth requirement, so no wrong content to strip — just the header.

## Suggested next-session order

1. Fix the canonical spec header bug (1-line edit) — unblocks archiving.
2. Reshape the old change per the fold decision; commit bookkeeping separately from `82d4871`.
3. `/opsx:apply fix-v2-encrypted-frame-codec` — implement the 3 framing fixes TDD-style, then
   validate on hardware (device in range): full handshake to `2A2A06` + a real Modbus SOC read.
