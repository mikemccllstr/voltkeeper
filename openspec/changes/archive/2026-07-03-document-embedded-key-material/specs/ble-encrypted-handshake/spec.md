## ADDED Requirements

### Requirement: ECDH confirmation frame status handling

After the app sends its signed ECDH reply (`2A 2A 05`), the device SHALL respond with an encrypted confirmation frame `2A 2A 06 01 <status>`. The system SHALL consume this frame, decode it, and inspect the status byte. A status of `0x00` indicates the device accepted the app's public key and signature; any non-zero status SHALL abort the handshake with a descriptive error. The system SHALL treat status `0x01` as rejection of the app-pubkey signature and its error SHALL say so, so that when onboarding a new encrypted model the operator can recognize a mismatched `PRIVATE_KEY_L1_HEX` / `PUBLIC_KEY_K2_DER_HEX`.

#### Scenario: Confirmation accepted
- **WHEN** the decrypted confirmation frame carries status byte `0x00`
- **THEN** the handshake proceeds to derive the ECDH shared key

#### Scenario: Signature rejected
- **WHEN** the decrypted confirmation frame carries status byte `0x01`
- **THEN** the handshake aborts with an error identifying the cause as the device rejecting the app-pubkey signature (a key mismatch for this device model)

#### Scenario: Other non-zero status aborts
- **WHEN** the decrypted confirmation frame carries a non-zero status other than `0x01`
- **THEN** the handshake aborts with a descriptive error that includes the raw status value
