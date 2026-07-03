## Why

voltkeeper embeds three pieces of Bluetti key material in `bluetooth/handshake.py` — a symmetric legacy AES key, an ECDSA private key (`PRIVATE_KEY_L1`), and an ECDSA public key (`PUBLIC_KEY_K2`) — all lifted verbatim from the decompiled official APK. Shipping a vendor's private signing key is the single most likely trigger for a takedown or PyPI complaint, yet the repo currently offers no stated rationale for why it's there or evidence that it's necessary. Hardware testing on 2026-07-03 against a real Elite 100 V2 settled the necessity question: the device verifies our app-pubkey signature and rejects a substitute key (ECDH confirmation status `0x01`), so the private key cannot be removed or self-generated. This change records that decision and its evidence, closes a spec gap the test exposed, and captures how to find these keys again for the next encrypted model.

## What Changes

- **Provenance + rationale, in code and docs**: A durable comment block in `handshake.py` naming each constant's exact APK source (class + field) and stating the interoperability basis for embedding them; a matching rationale section in the protocol security docs. Decision: keep the keys baked in.
- **Hardware finding documented**: The protocol docs record that the device *enforces* the app-pubkey signature (not just that the app sends one), with the confirmed ECDH confirmation status semantics (`0x00` accept, `0x01` app-signature rejected) and a reference to the 2026-07-03 test.
- **Diagnostic + spec gap closed**: The ECDH confirmation frame (`2A 2A 06`) status handling gains a spec requirement (none exists today, though the code checks it). The failure message is enriched to explain that `0x01` means the device rejected our app-pubkey signature — the actionable signal when onboarding a new encrypted model with an unverified key.
- **Key-location guide**: A developer-doc section on locating the three constants in a decompiled APK (`ConnConstantsV2`, `SignatureCrypt`, jadx grep recipe, mapping into `handshake.py`).
- No change to handshake behavior, key values, or the connection flow.

## Capabilities

### New Capabilities

<!-- none -->

### Modified Capabilities

- `ble-encrypted-handshake`: Add a requirement covering the ECDH confirmation frame (`2A 2A 06`) status byte — currently checked in code but unspecified — including the decoded status semantics and a descriptive, actionable error on rejection.

## Impact

- `src/voltkeeper/bluetooth/handshake.py` — provenance comment block; enriched confirmation-failure error message. No logic or key changes.
- `docs/source/protocol/security.md` — signature-enforcement finding + status semantics in the handshake flow; key-material provenance/rationale subsection.
- `docs/source/protocol/encryption-details.md` — cross-reference the confirmed finding.
- `docs/source/developer/contributing-devices.md` — "Locating encryption keys in a new APK" guide.
- Tests — unit test asserting the enriched `0x01` confirmation error.
- Not touched: `docs/findings.html` (orphaned, being retired per the 2026-07-02 review item #8 — new findings land in the Sphinx protocol docs).
