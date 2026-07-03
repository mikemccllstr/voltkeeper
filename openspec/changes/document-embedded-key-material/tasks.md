## 1. Confirmation-status diagnostic (code + spec)

- [ ] 1.1 Write a failing unit test: given a decrypted `2A 2A 06 01 01` confirmation frame, `HandshakeSession` (or the confirmation-check path) raises an error whose message identifies status `0x01` as the device rejecting the app-pubkey signature; a `0x00` frame does not raise; another non-zero status raises with the raw value included
- [ ] 1.2 Enrich the confirmation-failure message in `handshake.py` to decode `0x01` (app-pubkey signature rejected → L1/K2 mismatch for this model) while keeping the generic branch for other non-zero statuses; confirm tests pass

## 2. Provenance and rationale (code + docs)

- [ ] 2.1 Add an evergreen comment block above the key constants in `handshake.py`: each constant's exact APK source (`ConnConstantsV2.LOCAL_AES_KEY`, `SignatureCrypt.PRIVATE_KEY_L1`, `SignatureCrypt.PUBLIC_KEY_K2`), that they are public constants in the shipped app, the interoperability basis for embedding them, and that L1 is hardware-confirmed required (EL100V2, 2026-07-03). No temporal phrasing.
- [ ] 2.2 Add a "Key material provenance and rationale" subsection to `docs/source/protocol/security.md` (near "Complete Crypto Material"): same provenance table, why voltkeeper embeds the keys, and the keep-baked-in decision

## 3. Hardware finding in protocol docs

- [ ] 3.1 In `docs/source/protocol/security.md` Step 3c, state that the device *enforces* the app-pubkey signature (not merely that the app sends one) and document the ECDH confirmation status semantics (`0x00` accept, `0x01` app-signature rejected), citing the 2026-07-03 EL100V2 test
- [ ] 3.2 Add a cross-reference from `docs/source/protocol/encryption-details.md` to the finding so both crypto docs stay consistent

## 4. Key-location guide for future APKs

- [ ] 4.1 Add a "Locating encryption keys in a new APK" subsection to the "Encryption notes" section of `docs/source/developer/contributing-devices.md`: the jadx grep recipe (by key hex or by field name), the two class locations, mapping each field to its `handshake.py` constant, and the caveat that a new model may use different keys — detectable via a `0x01` confirmation status

## 5. Verification

- [ ] 5.1 Check docs nav/toctree — confirm the edited pages are already included (no new files added); update if needed
- [ ] 5.2 Run `mise run check` (lint, typecheck, tests, docs lint/format) and confirm clean
