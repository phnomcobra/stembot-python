# stembot-python

## Overview

StemBot is a distributed bot framework for deploying networks of lightweight agents that communicate over HTTP. Each agent runs as a FastAPI server and can connect to peers, route messages across multi-hop networks, execute remote commands, and transfer files.

Key features:
- **Multi-agent networking** — agents discover peers and automatically share routing tables so messages can traverse multi-hop paths
- **Asynchronous tickets** — control requests are wrapped in tickets and delivered asynchronously, with optional path tracing through the network
- **AES-256 encryption** — every request and response is encrypted end-to-end using AES-256 in EAX mode
- **Polling mode** — agents with one-way connectivity can poll their peers rather than relying on inbound connections
- **CLI tools** — `agt-configure` for offline setup and `agt-control` for live agent management
- **Multi-process safe** — document-layer locking uses file-based locks so multiple worker processes share the same SQLite database safely

## Installation

Install the package from a built wheel or directly from source:

```bash
# From a wheel file
pip install stembot-*.whl

# From source (editable, for development)
pip install -e .
```

### Configuring the Agent

There are two ways to configure an agent before starting it.

**Option 1: Environment variables**

Set environment variables and load them with a single command:

```bash
export AGT_UUID="my-agent"
export AGT_PORT="8080"
export AGT_HOST="0.0.0.0"
export AGT_SECRET="mypassword"
export AGT_LOG_PATH="/var/log/stembot"
export AGT_CLIENT_CONTROL_URL="http://127.0.0.1:8080/control"
export AGT_WORKERS="4"
export AGT_LOG_LEVEL_APP="INFO"
export AGT_LOG_LEVEL_API="WARNING"
export AGT_PEER_TIMEOUT_SECS="60"
export AGT_PEER_REFRESH_SECS="30"
export AGT_MAX_WEIGHT="600"
export AGT_TICKET_TIMEOUT_SECS="600"
export AGT_MESSAGE_TIMEOUT_SECS="600"

agt-configure --load-env
```

**Option 2: CLI flags**

Pass all values directly on the command line, then set the client URL to localhost:

```bash
agt-configure --agtuuid my-agent --port 8080 --host 0.0.0.0 --secret mypassword --log-path /var/log/stembot
agt-configure --workers 4 --log-level-app INFO --log-level-api WARNING
agt-configure --peer-timeout-secs 60 --peer-refresh-secs 30 --max-weight 600
agt-configure --ticket-timeout-secs 600 --message-timeout-secs 600
agt-configure --client-local
```

### Peer Discovery

Peer discovery can be scheduled to run after a delay (in seconds) to give other agents time to start:

```bash
# Standard (bidirectional) peer discovery — runs after 10 seconds
agt-control discover http://peer:8080/mpi --delay 10 &

# Polling peer discovery — this agent polls the peer rather than relying on callbacks
agt-control discover http://peer:8080/mpi --polling --delay 10 &
```

Use `--polling` when the remote peer cannot reach this agent directly (e.g. one-way connectivity). For example, if agent c4 can reach c3 but c3 cannot reach c4, c4 should use `--polling` so it initiates all communication.

### Starting the Server

```bash
agt-server
```

### Full Example (single agent)

```bash
pip install stembot-*.whl
agt-configure --agtuuid agent-a --port 8080 --host 0.0.0.0 --secret mypassword --log-path /log
agt-configure --client-local
agt-control discover http://agent-b:8080/mpi --delay 10 &
agt-server
```

## Developer Installation

[Poetry](https://python-poetry.org/) is the recommended tool for managing the development environment and building the package.

```bash
# Install Poetry
pip install poetry

# Install all dependencies (including dev) into a managed virtualenv
poetry install

# Activate the virtualenv
poetry shell
```

### Building a Wheel

```bash
# Build a wheel and sdist into dist/
poetry build
```

The resulting `.whl` file in `dist/` can be installed directly with `pip install dist/stembot-*.whl` or mounted into a Docker container as shown in `docker-compose.yml`.

## Testing and Linting
1. Setup virtual environment
    - `python -m venv venv`
    - `source venv/bin/activate`
    - `pip install -e '.[build]'`

2. Run tests
    - `./scripts/test.sh`

3. Run linter
    - `pylint stembot`

## Protocol Architecture

### Overview

StemBot uses a layered protocol stack for distributed agent communication. The stack consists of three primary message types that work together to enable peer-to-peer network communication with asynchronous request handling and automatic routing.

### Protocol Stack Layers

```
┌─────────────────────────────────────────┐
│      CLI Tools (configure/control)      │
│  - Configure local agent settings       │
│  - Send control requests to agents      │
└──────────────┬──────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────┐
│       ControlForm (Request/Response)    │
│  - CreatePeer, DiscoverPeer             │
│  - DeletePeers, LoadFile, WriteFile     │
│  - SyncProcess, GetConfig, GetRoutes    │
└──────────────┬──────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────┐
│      NetworkMessage (Routing Layer)     │
│  - NetworkTicket (async delivery)       │
│  - Ping, Advertisement, Acknowledgement │
│  - Routes messages between peers        │
└──────────────┬──────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────┐
│    FastAPI HTTP Server (Transport)      │
│  - /control endpoint (ControlForm)      │
│  - /mpi endpoint (NetworkMessage)       │
│  - AES-256 encryption per request       │
└─────────────────────────────────────────┘
```

### Message Schema

#### ControlForm

**Base Class:** `ControlForm`

Base control form for all control message types. Defines common properties for control requests.

**Concrete Types:**
- `CreatePeer` - Establish peer connection with known agent UUID and URL
- `DiscoverPeer` - Discover peer by URL and automatically retrieve its UUID
- `DeletePeers` - Remove one or all peer relationships
- `GetPeers` - Retrieve list of connected peers
- `GetRoutes` - Retrieve routing table (known paths through network)
- `GetConfig` - Retrieve agent configuration (excluding encryption key)
- `SyncProcess` - Execute a command synchronously and retrieve output
- `LoadFile` - Load file from remote agent (compressed and encoded)
- `WriteFile` - Write file to remote agent (compressed and encoded)

**Wrapper Type:** `ControlFormTicket`
- Wraps a ControlForm with ticket metadata for asynchronous delivery
- Tracks UUID (tckuuid), source, destination, and service time
- Supports path tracing through the network

**Example:** Creating a peer connection
```python
from stembot.models.control import CreatePeer
from stembot.executor.agent import ControlFormClient

client = ControlFormClient(url="http://agent.example.com:8080/control")
form = client.send_control_form(CreatePeer(
    agtuuid="agent-b-uuid",
    url="http://agent-b.example.com:8080",
    ttl=60,
    polling=True
))
```

#### NetworkMessage

**Base Class:** `NetworkMessage`

Base class for all inter-agent network messages. Core routing properties.

**Concrete Types:**
- `Ping` - Test connectivity to a peer
- `Advertisement` - Broadcast known routes to peers
- `Acknowledgement` - Confirm receipt of a message (with optional error)
- `NetworkTicket` - Async delivery container for ControlForms
- `NetworkMessagesRequest` - Poll peer for pending messages
- `NetworkMessagesResponse` - Return list of pending messages
- `TicketTraceResponse` - Report ticket hop through this agent

**Key Fields:**
- `type` - Message type enumeration
- `src` - Source agent UUID (originator)
- `isrc` - Immediate source (last agent before this one)
- `dest` - Destination agent UUID (None = broadcast)
- `timestamp` - Unix timestamp of creation

**Example:** Sending a network message
```python
from stembot.models.network import Ping
from stembot.executor.agent import NetworkMessageClient

client = NetworkMessageClient(url="http://peer.example.com:8080/mpi")
response = client.send_network_message(Ping())
# Response is an Acknowledgement
```

### CLI Tools

#### `configure` - Offline Configuration

Pre-configures agent settings before startup. Settings are persisted to the local key-value store.

**Environment Variables:**
```bash
export AGT_UUID="my-agent-123"
export AGT_HOST="0.0.0.0"
export AGT_PORT="8080"
export AGT_LOG_PATH="~/.stembot/logs"
export AGT_SECRET="mypassword"  # Will be hashed to 32 bytes
export AGT_CLIENT_CONTROL_URL="http://localhost:8080"
export AGT_WORKERS="4"
export AGT_LOG_LEVEL_APP="INFO"
export AGT_LOG_LEVEL_API="WARNING"
export AGT_PEER_TIMEOUT_SECS="60"
export AGT_PEER_REFRESH_SECS="30"
export AGT_MAX_WEIGHT="600"
export AGT_TICKET_TIMEOUT_SECS="600"
export AGT_MESSAGE_TIMEOUT_SECS="600"
```

**Usage:**
```bash
# View current configuration
agt-configure --view

# Set individual values
agt-configure --agtuuid my-agent --port 8080

# Load from environment variables
agt-configure --load-env

# Set client URL to localhost
agt-configure --client-local
```

#### `control` - Online Agent Management

Sends control requests to a running agent. Requires the agent to be running and reachable.

**Usage:**

```bash
# Discover a new peer
agt-control discover http://agent-b:8080/mpi

# Manage peers
agt-control delete --agtuuid agent-b-uuid
agt-control delete --all

# Agent statistics
agt-control stat agent-b    # Config, peers, routes, hops

# Execute remote command
agt-control exec agent-b "ls -la"

# File transfer
agt-control put agent-b /local/path /remote/path

# Performance testing
agt-control bench agent-b   # Measure latency/throughput
```

### Encryption and Security

Each request/response pair is encrypted end-to-end using AES-256 in EAX mode:

**Request Headers:**
```
Nonce:        base64(random_nonce)
Tag:          base64(aes_authentication_tag)
Content-Type: application/octet-stream
```

**Payload:**
```
base64(AES.encrypt(json_data))
```

The encryption key is configured via the `key` field in Config (must be exactly 32 bytes for AES-256).
Defaults to SHA256(b'changeme'). **Change this in production.**

### Type Safety

All schemas are defined as Pydantic models with strong type validation:

This ensures:
- Type checking at parse time
- Invalid values rejected with detailed error messages
- JSON serialization/deserialization with validation
- IDE autocomplete and documentation
