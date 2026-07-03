## Context

`bluetooth/handshake.py` hardcodes three constants copied from the official Bluetti Android app:

| voltkeeper constant | APK source (v3.0.9, jadx) | Kind |
| --- | --- | --- |
| `LOCAL_AES_KEY` | `ConnConstantsV2.LOCAL_AES_KEY` (line 98) | symmetric, legacy stage |
| `PRIVATE_KEY_L1_HEX` | `SignatureCrypt.PRIVATE_KEY_L1` (line 34) | ECDSA private (app identity) |
| `PUBLIC_KEY_K2_DER_HEX` | `SignatureCrypt.PUBLIC_KEY_K2` (line 35) | ECDSA public (device auth) |

voltkeeper's names mirror the APK's own field names, and all three are `public static final String` constants — public in the sense of "plainly present in the shipped app," not secret. `SignatureCrypt` exposes `sign`, `verifyForECDSA256`, `getPrivateKeyL1`, `getPublicKeyK2`, confirming the L1/K2 roles.

The 2026-07-03 hardware test (real EL100V2, `DC:B4:D9:46:73:96`) swapped `sign_app_pubkey` to a freshly generated key, leaving the ECDH ephemeral key untouched. Result: the device returned ECDH confirmation frame `2a2a0601010008` — status byte `0x01` — and the handshake never completed; with the real L1 key it completes (status `0x00`) and reads live data every run. Conclusion: the device verifies the app-pubkey signature against L1's firmware-embedded counterpart. L1 is load-bearing.

This exposed a spec gap: `openspec/specs/ble-encrypted-handshake/spec.md` has a requirement for the `2A 2A 03` status-ack but none for the `2A 2A 06` ECDH confirmation, even though `handshake.py` checks `conf_plaintext[4] != 0` (commit `8f3a5e9`).

## Goals / Non-Goals

**Goals:**
- Record the keep-baked-in decision with a defensible, discoverable rationale (code + docs).
- Document the hardware-confirmed signature enforcement and the `0x00`/`0x01` status semantics.
- Close the confirmation-status spec gap and make the `0x01` failure actionable.
- Leave a repeatable recipe for finding these keys in a future APK.

**Non-Goals:**
- No runtime key extraction (that was the alternative to this decision; not pursued).
- No change to handshake logic, key values, frame formats, or the connection flow.
- No legal opinion beyond stating the interoperability basis; this is documentation, not counsel.
- Not reviving or editing `docs/findings.html` (retired per review #8).

## Decisions

**1. Rationale lives in two places, kept short and evergreen.**
An in-code comment block at the top of `handshake.py`'s key definitions (so a reader of the source sees provenance + basis immediately) and a prose subsection in `protocol/security.md` (so it's discoverable without reading code). Both state: what each constant is, its exact APK origin, that these are constants shipped in the public app, that voltkeeper embeds them solely to interoperate with hardware the user owns, and that L1 is hardware-confirmed required. No temporal phrasing ("recently", "now") per repo comment rules — the comment describes the code as it stands.

**2. The only behavioral change is the diagnostic message; everything else is docs/comments.**
`handshake.py` raises `ECDH confirmation failed with status 0x{status:02x}` today. Enrich it: on `0x01`, state that the device rejected our app-pubkey signature and that, for a newly added encrypted model, this means `PRIVATE_KEY_L1_HEX`/`PUBLIC_KEY_K2_DER_HEX` don't match that model's firmware. Keep the generic wording for other non-zero statuses (we've only decoded `0x00` and `0x01`; don't invent meanings for codes we haven't observed).

**3. Spec: ADD, not MODIFY.**
Since no requirement covers the `2A 2A 06` confirmation frame, add one to the `ble-encrypted-handshake` delta describing: the confirmation is consumed as its own frame; `0x00` = accepted; non-zero aborts with a descriptive error; `0x01` specifically indicates app-pubkey signature rejection. This documents observed behavior only.

**4. Key-location guide sits with device contribution, not protocol reference.**
`developer/contributing-devices.md` already has an "Encryption notes" section — the natural home for "your new model advertises `BLUETTE`/`BLUETTF`, here's how to pull its keys." The guide gives the jadx grep recipe (search the key hex or the field names `LOCAL_AES_KEY`/`PRIVATE_KEY_L1`/`PUBLIC_KEY_K2`), the two class locations, and how each maps to a `handshake.py` constant — plus the caveat that a different model may use different keys, detectable via the `0x01` confirmation status.

## Risks / Trade-offs

- [Publishing the "how to extract Bluetti's private key" recipe increases visibility of the sensitive act] → The keys are already in the shipped code and the APK is public; the guide documents provenance we already rely on and is scoped to interoperability with owned hardware. Net transparency helps the rationale more than obscurity would.
- [Stating an interoperability/legal basis could read as legal advice] → Phrase as the project's rationale and factual provenance, not as a legal conclusion; keep it brief and cite that the material is public-APK-derived.
- [Documenting status `0x01` might be model-specific] → It's the only encrypted device we can test; the guide and spec say "observed on EL100V2," not "universal," and the generic-status branch stays for unknown codes.

## Migration Plan

Docs- and comment-only except the single error-string change and its test. One commit; rollback is a revert. No user-facing or API impact.

## Open Questions

None. (A future second encrypted model would let us confirm whether `0x01` semantics generalize; noted in the guide, not blocking.)
