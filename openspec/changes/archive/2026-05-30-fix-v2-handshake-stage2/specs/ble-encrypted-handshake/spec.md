## ADDED Requirements

### Requirement: Post-reply status-ack frame

The system SHALL consume the device's status-ack frame `2A 2A 03 01 <status> <checksum>` — sent after the legacy challenge reply and before the encrypted ECDH block — as a separate frame, and SHALL NOT include its bytes in the buffer collected for the ECDH block. A status byte of `00` indicates acceptance; any non-zero status SHALL abort the handshake with a descriptive error.

#### Scenario: Ack frame consumed before the ECDH block
- **WHEN** the device sends `2A 2A 03 01 00 00 04` followed by a 144-byte encrypted ECDH block
- **THEN** the handshake reads the 7-byte ack frame separately
- **THEN** the buffer decrypted as the ECDH block is exactly the 144 encrypted bytes (a multiple of 16)
- **THEN** decryption does not raise a length/alignment error

#### Scenario: Non-OK ack status aborts
- **WHEN** the device sends a `2A 2A 03 01 <status>` frame with a non-zero status byte
- **THEN** the handshake raises an error identifying the rejected status

### Requirement: ECDH message field offsets

The system SHALL read the 64-byte device public key from byte offset 4 through 67 inclusive, and the 64-byte ECDSA signature from byte offset 68 through 131 inclusive, of the decrypted ECDH message. The message is framed as `2A 2A 04`, a length byte at offset 3, the public key, the signature, then a checksum — the same length-prefixed framing as the stage-1 challenge.

#### Scenario: Pubkey and signature read after the length field
- **WHEN** a decrypted ECDH message begins `2A 2A 04 80` followed by a 64-byte public key and 64-byte signature
- **THEN** the device public key MUST be taken from bytes 4 through 67
- **THEN** the signature MUST be taken from bytes 68 through 131
