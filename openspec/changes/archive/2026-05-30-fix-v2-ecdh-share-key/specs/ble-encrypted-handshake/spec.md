## ADDED Requirements

### Requirement: ECDH shared key is the full 32-byte shared secret

After ECDH completes, the post-handshake session key (`bleConnShareKey`) SHALL be the complete 32-byte raw output of the ECDH key agreement on SECP256R1 (the x-coordinate of the shared elliptic-curve point). The system SHALL NOT truncate this value to 16 bytes. Because the key is 32 bytes, all post-handshake AES-CBC operations use AES-256.

#### Scenario: Shared key is not truncated

- **WHEN** the ECDH key agreement completes on SECP256R1
- **THEN** the resulting shared key is exactly 32 bytes
- **THEN** this 32-byte key is used directly as the AES key for `ShareSession` (AES-256-CBC)

#### Scenario: ShareSession accepts a 32-byte key

- **WHEN** a 32-byte key is passed to `ShareSession`
- **THEN** `ShareSession` constructs without error
- **THEN** all encode/decode operations use AES-256-CBC with that key

#### Scenario: 16-byte handshake-stage key is unchanged

- **WHEN** the legacy handshake stage derives `bleConnAESKey` by XOR of `randomMd5` and `LOCAL_AES_KEY`
- **THEN** the key is 16 bytes and uses AES-128-CBC as before
- **THEN** the post-handshake `ShareSession` key derivation is unaffected
