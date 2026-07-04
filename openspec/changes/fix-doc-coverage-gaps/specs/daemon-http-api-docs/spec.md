## ADDED Requirements

### Requirement: HTTP API reference in daemon docs
The docs/source/user-guide/daemon.md page SHALL include a structured HTTP API
Reference section documenting all daemon REST and WebSocket endpoints, their
methods, paths, auth requirements, request/response formats, and error codes.

#### Scenario: User finds endpoint documentation
- **WHEN** a user reads the daemon documentation page
- **THEN** they can find a table or section listing every available API endpoint with method, path, description, and auth requirement

### Requirement: Authentication documentation
The HTTP API reference SHALL document that all endpoints except / require
authentication via either Authorization: Bearer <token> header or ?token=<token>
query parameter, and that the token is the server.api_key config value.

#### Scenario: User understands how to authenticate
- **WHEN** a user reads the API reference
- **THEN** they see documentation of the two authentication mechanisms (Bearer header and token query param)

### Requirement: Rate limiting documentation
The HTTP API reference SHALL document that the daemon enforces rate limiting of
60 requests per 60 seconds per client IP address.

#### Scenario: User is aware of rate limits
- **WHEN** a user reads the API reference
- **THEN** they see the rate limit documented with the threshold and scope

### Requirement: WebSocket endpoint documentation
The HTTP API reference SHALL document the GET /ws WebSocket endpoint
including connection behavior (initial device_status and state_update messages
cached, then real-time updates from the event bus).

#### Scenario: Developer understands WebSocket protocol
- **WHEN** a developer reads the API reference
- **THEN** they see documentation of the WebSocket endpoint path, initial message format, and that it pushes real-time state_update messages

### Requirement: Fields endpoint documentation
The HTTP API reference SHALL document GET /api/device/{address}/fields
including its response format (list of writable fields with types, enum values, and ranges).

#### Scenario: Developer discovers fields introspection endpoint
- **WHEN** a developer reads the API reference
- **THEN** they see documentation of the fields endpoint with its response schema

### Requirement: Web UI documentation
The daemon.md page SHALL include a section describing the Web UI served at /,
its authentication flow (API key prompt), and its relationship to the HTTP API and WebSocket.

#### Scenario: User understands the Web UI
- **WHEN** a user reads the daemon documentation
- **THEN** they find a description of what the Web UI does and how it connects to the daemon
