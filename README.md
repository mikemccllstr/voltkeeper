<img src="https://raw.githubusercontent.com/mikemccllstr/voltkeeper/main/docs/voltkeeper-wordmark.svg" alt="voltkeeper" height="60">

[![PyPI version](https://img.shields.io/pypi/v/voltkeeper.svg)](https://pypi.org/project/voltkeeper/)
[![Python versions](https://img.shields.io/pypi/pyversions/voltkeeper.svg)](https://pypi.org/project/voltkeeper/)
[![CI](https://github.com/mikemccllstr/voltkeeper/actions/workflows/ci.yml/badge.svg)](https://github.com/mikemccllstr/voltkeeper/actions/workflows/ci.yml)
[![License](https://img.shields.io/pypi/l/voltkeeper.svg)](https://github.com/mikemccllstr/voltkeeper/blob/main/LICENSE)

PC-based tooling for Bluetti power stations that replaces the official mobile app: scan, connect, and control your equipment locally. No cloud account required.

> **Not affiliated with or endorsed by Bluetti.** Built by reverse-engineering the official Android app for interoperability research purposes.

## Why voltkeeper?

- **Local-first, offline control** — talk directly to your power station(s) over Bluetooth. No internet connection, no cloud account, no vendor API.
- **Your hardware, your data** — nothing leaves your local network.
- **Cross-platform** — runs on Linux, macOS, and Windows with a BLE adapter.
- **Multiple interfaces and integrations** — Control your devices from the CLI, a local web interface, and a local HTTP-based API. The future roadmap includes integration with Home Assistant and NUT.

<!-- TODO: add terminal recording screenshot -->

<!-- ![voltkeeper demo](docs/demo.svg) -->

## Why **NOT** voltkeeper?

> ⚠️⚠️ **WARNING** This application is currently **pre-ALPHA** quality. ⚠️⚠️

- Most of the code was written by a [clanker](https://en.wikipedia.org/wiki/Clanker) (AI-based coding agents).
- We figured out how to control Bluetti devices by reverse-engineering the official mobile app, but there is no official documentation to work from.
- This tool has only been tested by a single user, on a single AC2A device. I bought the AC2A for less than $150, and the test load is a $15 box fan.

Your use of this app is at your own risk. If you doubt me, see the [LICENSE](https://github.com/mikemccllstr/voltkeeper/blob/main/LICENSE) file, which reads in part:

> THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
> IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
> FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
> AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
> LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
> OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
> SOFTWARE.

If you have an expensive Bluetti device, connected to expensive battery packs, supplying critical loads, that keep people alive (or maybe just happy), maybe you should avoid being first in line to test this new thing I told a clanker to create.

## How this got built

My name is Mike McCallister. I'm a US-based IT guy who likes Python, Linux, and Home Assistant. I have several decades of experience with everything from microcontrollers to global enterprise technology. I am interested in solar, EVs, batteries, and electrical power, but I have a very modest understanding of these topics.

I currently own a Bluetti AC2A, and I "needed" (wanted) a way to control it from a PC instead of a mobile phone. My initial needs were simple: I wanted to be able to cleanly shut down a Linux PC when the Bluetti device that was powering it began to run low on juice.

I looked around on the internet and didn't find anything that quite fit my needs. Since 2026 is the first calendar year after the inflection point where AI coding agents (clankers) began to make software creation both easy and difficult in new ways, I thought this would be a good way to experiment and see whether they could solve my Bluetti-control problem in a way I found useful.

Since the early experiment was successful, I began to get more excited about the possibilities. Using clankers like Claude Code (expensive) and DeepSeek via OpenCode (really cheap) helps me create seemingly well-engineered software quickly, without all the typing. I can ask the robot to do research while I sleep that would take me hours. I can "code" from my phone using a SSH session into a remote machine, answering questions to keep the clanker chugging while I do other things. I can make mistakes or poor choices and tell the robot to fix them just as easily.

I have evolved the early work into this new application (voltkeeper) which I hope to continue developing to become the best way to control and integrate Bluetti devices in "offline mode" into an open source eco-system. I expect to use this software personally with my existing AC2A, plus an Elite 100V2 that I have on the way. I would like to find other users who are willing to test this device with their hardware and to share what they find, so we can eventually remove the "alpha" status from this software.

## Quick demo

Run voltkeeper in standalone mode to make sure it can detect your device and read its status:

```bash
voltkeeper scan                          # discover nearby Bluetti devices
voltkeeper status                        # auto-detects device, shows battery SOC and load
voltkeeper write AA:BB:CC:DD:EE:FF ac_output on   # toggle AC output
```

If this works, you know it's fundamentally working. If you run into an error with the steps above, let's troubleshoot before you move on to experimenting with daemon mode or integrations.

## Capabilities

| Command                | What it does                                                          |
| ---------------------- | --------------------------------------------------------------------- |
| `scan`                 | Discover nearby Bluetti devices and show exact connect commands       |
| `status`               | Read battery SOC, pack voltage, load, and charging status             |
| `write`                | Toggle AC/DC output, change charging mode, adjust device settings     |
| `mqtt-publish`         | Stream device telemetry to MQTT with Home Assistant auto-discovery    |
| `mqtt-listen`          | Watch battery SOC over MQTT and shut down host on low battery         |
| `load-test`            | Run a controlled battery discharge test with CSV logging              |
| `probe`                | Sweep register blocks for reverse-engineering device support          |
| `annotate`             | Live-poll and interactively label register fields                     |
| `mqtt-publish-service` | Generate systemd unit file for MQTT publishing                        |
| `mqtt-listen-service`  | Generate systemd unit file for MQTT listen watchdog                   |
| `daemon`               | Start/manage a persistent background service with HTTP API and Web UI |

See the [User Guide](https://mikemccllstr.github.io/voltkeeper/user-guide/) for full command reference, or run `voltkeeper <command> --help`.

## Requirements

- Python 3.10+
- Linux with BlueZ, macOS 11+, or Windows 10 build 19041+ (BLE support)
- Bluetooth adapter with scan capability

On Linux, the BLE adapter may require elevated privileges (`CAP_NET_ADMIN` or `sudo`). Encrypted Bluetti devices (AES-CBC over BLE) are supported — the handshake is handled automatically.

## Tested devices

- **Bluetti AC2A:** seemingly works successfully for the author, one user.

Devices not listed above have not been tested. If you are feeling adventurous, please consider testing your device and letting us know how it goes.

## Install

The application is available as a Python package. Python tools like uv, pip, and pipx should be able to install this on most Linux, Windows, and macOS systems.

```bash
pip install voltkeeper
```

Or try it without installing:

```bash
uvx --from git+https://github.com/mikemccllstr/voltkeeper voltkeeper --help
```

Or from source:

```bash
git clone https://github.com/mikemccllstr/voltkeeper
cd voltkeeper
uv run voltkeeper --help
```

## Daemon (long-running service)

For monitoring multiple devices simultaneously, a persistent Web UI, or avoiding repeated BLE scans, run `voltkeeperd` as a background service.

**Config file** — create `~/.config/voltkeeper/config.yaml`:

```yaml
server:
  api_key: "your-secret-key"

devices:
  - address: "AA:BB:CC:DD:EE:FF"
    name: "Living Room AC2A"

scan:
  interval: 60       # seconds between reconciliation scans
  timeout: 10.0      # BLE scan timeout
```

Config is searched in order: `./voltkeeper.yaml`, `~/.config/voltkeeper/config.yaml`, `/etc/voltkeeper/config.yaml`.

**Start the daemon:**

```bash
voltkeeper daemon start          # runs in foreground
```

**Query the daemon from the CLI:**

```bash
voltkeeper status --daemon localhost           # show all devices
voltkeeper status AA:BB:CC:DD:EE:FF --daemon localhost   # single device detail
voltkeeper write AA:BB:CC:DD:EE:FF ac_output on --daemon localhost
```

**Web UI** — open `http://localhost:8080` in a browser. Enter your API key when prompted.

**Systemd unit** (for production use):

```ini
[Unit]
Description=voltkeeperd
After=bluetooth.target network.target

[Service]
ExecStart=/usr/bin/voltkeeperd
Restart=always
RestartSec=30
User=your-user
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
```

Save as `/etc/systemd/system/voltkeeperd.service`, then `systemctl enable --now voltkeeperd`.

The daemon can also be secured with network ACLs by adding to `server.allowed_networks`:

```yaml
server:
  api_key: "your-secret-key"
  allowed_networks: ["192.168.1.0/24", "127.0.0.0/8"]
```

## Links

- [Documentation](https://mikemccllstr.github.io/voltkeeper/)
- [Contributing a new device](https://mikemccllstr.github.io/voltkeeper/developer/contributing-devices/)
- [Issue tracker](https://github.com/mikemccllstr/voltkeeper/issues)
