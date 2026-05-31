## ADDED Requirements

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

After ECDH completes and traffic is encrypted with `bleConnShareKey`, each frame SHALL use the layout `[2-byte length][4-byte random IV seed][ciphertext]`, where the AES-CBC IV is the MD5 of the 4 random seed bytes. This differs from the handshake stage (encrypted with `bleConnAESKey`), which uses `[2-byte length][ciphertext]` with the IV derived once from `randomMd5` and chained across blocks.

#### Scenario: Post-handshake Modbus frame decodes with its embedded IV
- **WHEN** a `bleConnShareKey`-encrypted frame is received as `[length][4-byte seed][ciphertext]`
- **THEN** the IV is computed as `MD5(seed)` and used to decrypt the ciphertext
- **THEN** the decrypted output is trimmed to the prefixed plaintext length

#### Scenario: Post-handshake outbound frame generates a fresh IV seed
- **WHEN** the system sends a `bleConnShareKey`-encrypted command
- **THEN** it generates 4 random seed bytes, sets the IV to `MD5(seed)`, and transmits `[length][seed][ciphertext]`
