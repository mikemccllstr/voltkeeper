## ADDED Requirements

### Requirement: LAN binding via --lan install flag
When `voltkeeper daemon install --lan` is used, the generated config SHALL set `server.host: "0.0.0.0"` and `server.mdns: true`. The command SHALL print the API key prominently with a security note explaining it is the only access control on the network. When the daemon starts with `server.host: "0.0.0.0"`, it SHALL bind on all network interfaces.

#### Scenario: Install with --lan
- **WHEN** the user runs `voltkeeper daemon install --lan`
- **THEN** config is written with `host: "0.0.0.0"` and `mdns: true`, the API key is printed with a security warning, and the daemon is installed and started

#### Scenario: Install without --lan (default)
- **WHEN** the user runs `voltkeeper daemon install` without `--lan`
- **THEN** config is written with `host: "127.0.0.1"` (or the existing host value is preserved), mDNS is not enabled, and the daemon only binds on loopback

### Requirement: mDNS service advertisement
When the daemon starts with a non-loopback binding (`server.host` is not `127.0.0.1`) and `server.mdns: true`, it SHALL advertise itself via mDNS using `python-zeroconf`. The service SHALL be advertised as `_http._tcp.local.` with the name `voltkeeper-{hostname}` where `{hostname}` is the machine's short hostname. The advertised port SHALL match `server.port`. The advertisement SHALL be withdrawn cleanly on daemon shutdown.

#### Scenario: mDNS advertisement on LAN start
- **WHEN** the daemon starts with `server.host: "0.0.0.0"` and `server.mdns: true`
- **THEN** the daemon registers a mDNS service record as `voltkeeper-{hostname}._http._tcp.local.` on the configured port

#### Scenario: mDNS not advertised on loopback
- **WHEN** the daemon starts with `server.host: "127.0.0.1"` (default)
- **THEN** no mDNS service record is registered, regardless of `server.mdns` value

#### Scenario: mDNS withdrawn on shutdown
- **WHEN** the daemon shuts down gracefully
- **THEN** the mDNS service record is unregistered before the process exits

### Requirement: CLI resolves mDNS-style hostnames
The `--daemon` flag in `voltkeeper status`, `voltkeeper write`, and `voltkeeper daemon status/stop` SHALL accept `voltkeeper.local`-style hostnames (any `.local` suffix) and pass them through to the HTTP client without adding `http://` prefix mangling. The CLI already expands bare hostnames to `http://{host}:8080`; this SHALL work correctly with `.local` names.

#### Scenario: CLI with .local hostname
- **WHEN** the user runs `voltkeeper status --daemon voltkeeper-homelab.local`
- **THEN** the CLI constructs `http://voltkeeper-homelab.local:8080` and queries the daemon successfully

### Requirement: Config mdns field
The `ServerConfig` dataclass and YAML config SHALL support a boolean `mdns` field (default: `false`). The daemon reads this field at startup to determine whether to register mDNS.

#### Scenario: mdns field defaults to false
- **WHEN** a config file has no `mdns` field under `server:`
- **THEN** the daemon starts without mDNS advertising

#### Scenario: mdns field set to true
- **WHEN** a config file has `server.mdns: true` and the host is non-loopback
- **THEN** the daemon starts and registers the mDNS service
