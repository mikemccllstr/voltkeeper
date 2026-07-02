## ADDED Requirements

### Requirement: One command in flight per client

`BluetoothClient.execute()` SHALL allow at most one command to be in flight per client instance at any time. A caller invoking `execute()` while another command is pending SHALL wait for the pending command to complete (including its retries) before its own command is sent.

#### Scenario: Concurrent execute calls are serialized
- **WHEN** a second coroutine calls `execute()` while a first command is awaiting its response
- **THEN** the second command is not written to the device until the first command has completed or failed
- **THEN** the first command's response is parsed against the first command and the second command's response against the second command

#### Scenario: Queued command survives the first command's failure
- **WHEN** a pending command exhausts its retries and raises `BadConnectionError`
- **THEN** a queued `execute()` call still runs, starting with fresh notification state (empty response buffer, new future)

### Requirement: Serialization covers the full retry lifecycle

The serialization boundary SHALL span the entire `execute()` call, including all retry attempts, so that no other command's bytes can interleave between retries of a failing command.

#### Scenario: No interleaving between retries
- **WHEN** a command times out and `execute()` begins a retry attempt
- **THEN** no queued command is written to the device between the failed attempt and the retry

### Requirement: Poll loop and bus commands share one client safely

`DeviceHandler` SHALL be able to run its polling loop and execute bus-delivered command messages against the same `BluetoothClient` without response cross-matching.

#### Scenario: Write arrives mid-poll
- **WHEN** a `CommandMessage` is handled while a polling read is awaiting its response
- **THEN** both the read and the write complete with their own responses
- **THEN** neither call observes a timeout caused by the other overwriting its notification future
