## Requirements

### Requirement: Legacy challenge frame parsing

The device opens the encrypted handshake by sending a legacy challenge as a 10-byte frame `2A 2A 01 04 <4 random bytes> <2-byte checksum>`. The byte at offset 3 (`0x04`) is a length field indicating four random bytes follow. The system SHALL extract the random value from `challenge[4:8]` (the four bytes after the length field), NOT from `challenge[3:7]`.

#### Scenario: Random bytes read after the length field
- **WHEN** the device sends challenge `2A 2A 01 04 3D 96 87 E0 02 3F`
- **THEN** the parsed random value is `3D 96 87 E0`
- **THEN** the `0x04` length byte at offset 3 is not included in the random value

#### Scenario: Challenge prefix validated
- **WHEN** a received handshake frame does not begin with `2A 2A 01`
- **THEN** the handshake raises an error rather than proceeding

### Requirement: Legacy challenge reply construction

The system SHALL reply to the legacy challenge with a symmetric 10-byte frame `2A 2A 02 04 <4 token bytes> <2-byte checksum>`. The token SHALL be the four bytes obtained by hex-decoding `randomMd5[16:24]` (where `randomMd5` is the lowercase MD5 hex digest of the reversed random value), NOT the eight ASCII bytes of that hex substring. The checksum SHALL be the big-endian two-byte sum of exactly the bytes `02 04` followed by the four token bytes (the leading `2A 2A` is excluded from the sum).

#### Scenario: Reply matches the captured hardware test vector
- **WHEN** the device challenge is `2A 2A 01 04 3D 96 87 E0 02 3F`
- **THEN** `randomMd5` is `a0ce9adc2c5341f1d271d0518c4e7773`
- **THEN** the token bytes are `D2 71 D0 51` (hex-decoded from `d271d051`)
- **THEN** the checksum is `02 6A` (big-endian sum of `02 04 D2 71 D0 51`)
- **THEN** the reply frame written to the device is `2A 2A 02 04 D2 71 D0 51 02 6A`

#### Scenario: Reply is ten bytes, not fourteen
- **WHEN** any legacy challenge reply is built
- **THEN** the reply is exactly 10 bytes long
- **THEN** the four token bytes are not ASCII-encoded hex characters

### Requirement: Legacy session key derivation

After replying, the system decrypts the device's ECDH block using a legacy AES-128 session key (`bleConnAESKey`). The key SHALL be the 16-byte result of XOR-ing, byte for byte, the decoded `randomMd5` digest (16 bytes) with the decoded `LOCAL_AES_KEY` (16 bytes). The system SHALL NOT XOR the ASCII codes of the hex digit characters.

#### Scenario: Key is a byte-wise XOR of decoded values
- **WHEN** `randomMd5` is `a0ce9adc2c5341f1d271d0518c4e7773` and `LOCAL_AES_KEY` is `459FC535808941F17091E0993EE3E93D`
- **THEN** the session key is the byte-wise XOR `decode(randomMd5) XOR decode(LOCAL_AES_KEY)`
- **THEN** the key is 16 bytes long

### Requirement: Legacy CBC initialization vector derivation

The CBC initialization vector for the legacy-key-encrypted stage SHALL be the 16 bytes obtained by hex-decoding `randomMd5` (the raw MD5 digest). The system SHALL NOT take a second MD5 of the `randomMd5` hex string.

#### Scenario: IV is the decoded digest
- **WHEN** `randomMd5` is `a0ce9adc2c5341f1d271d0518c4e7773`
- **THEN** the CBC IV equals the 16 bytes `a0 ce 9a dc 2c 53 41 f1 d2 71 d0 51 8c 4e 77 73`
- **THEN** the IV is not `md5(randomMd5_ascii)`

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

### Requirement: Encrypted frame length prefix

Every AES-CBC encrypted frame SHALL carry a 2-byte big-endian plaintext-length prefix before the ciphertext. When receiving, the system SHALL read this prefix, decrypt the ciphertext that follows, and trim the decrypted output to exactly the prefixed number of plaintext bytes (discarding zero padding). When sending, the system SHALL prepend the prefix as `%04X` of the plaintext byte length.

#### Scenario: Inbound ECDH block decrypts after stripping the prefix
- **WHEN** the device sends a 146-byte frame whose first two bytes are `00 86` (134) followed by 144 ciphertext bytes
- **THEN** the system strips the 2-byte prefix, decrypts the 144 ciphertext bytes, and trims to 134 plaintext bytes
- **THEN** the decrypted plaintext begins `2A 2A 04 80` and decryption does not raise a length/alignment error

#### Scenario: Outbound reply carries the prefix
- **WHEN** the system sends its `2A 2A 05` ECDH reply with an N-byte plaintext
- **THEN** the transmitted frame begins with the 2-byte big-endian value N followed by the ciphertext

### Requirement: ECDSA signature message uses hex-decoded randomMd5

The system SHALL build the ECDSA signature message as the byte concatenation of the 64-byte public key and the 16-byte hex-decoded `randomMd5` digest (80 bytes total), for both verifying the device signature against `PUBLIC_KEY_K2` and signing the app's own public key. The system SHALL NOT use the ASCII hex form of `randomMd5`.

#### Scenario: Device signature verifies with the hex-decoded message
- **WHEN** the device's ECDH message carries a signature over `(devicePubKey || hex_decode(randomMd5))`
- **THEN** verification against `PUBLIC_KEY_K2` over the 80-byte message succeeds
- **THEN** verification over the 96-byte ASCII-hex form would fail and is not used

#### Scenario: App reply signs the hex-decoded message
- **WHEN** the system signs its ephemeral public key
- **THEN** the signed message is `(appPubKey || hex_decode(randomMd5))`, 80 bytes

### Requirement: Post-handshake frames embed a per-frame IV seed

After ECDH completes and traffic is encrypted with `bleConnShareKey`, each frame SHALL use the layout `[2-byte length][4-byte random IV seed][ciphertext]`, where the AES-CBC IV is the MD5 of the 4 random seed bytes. This differs from the handshake stage (encrypted with `bleConnAESKey`), which uses `[2-byte length][ciphertext]` with the IV reset to `decode(randomMd5)` for each frame (not chained across frames).

#### Scenario: Post-handshake Modbus frame decodes with its embedded IV
- **WHEN** a `bleConnShareKey`-encrypted frame is received as `[length][4-byte seed][ciphertext]`
- **THEN** the IV is computed as `MD5(seed)` and used to decrypt the ciphertext
- **THEN** the decrypted output is trimmed to the prefixed plaintext length

#### Scenario: Post-handshake outbound frame generates a fresh IV seed
- **WHEN** the system sends a `bleConnShareKey`-encrypted command
- **THEN** it generates 4 random seed bytes, sets the IV to `MD5(seed)`, and transmits `[length][seed][ciphertext]`

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
