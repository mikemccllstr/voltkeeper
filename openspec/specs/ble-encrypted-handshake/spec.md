## ADDED Requirements

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
