# stembot-python

## Testing and Linting
1. Setup virtual environment
    - `python -m venv venv`
    - `source venv/bin/activate`
    - `pip install -e '.[build]'`

2. Run tests
    - `./test.sh`

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

### Agent Interaction Flow

#### Direct Message Flow (Synchronous)

```
Client Agent                    Server Agent
     │                               │
     │ POST /control                 │
     ├─ ControlForm (encrypted)─────→│
     │  (CreatePeer, GetRoutes)      │
     │                               │
     │                      Processes│
     │                    ControlForm│
     │                               │
     │ POST /control                 │
     │← (encrypted response)─────────┤
     │                               │
```

#### Routed Message Flow (Asynchronous via NetworkTicket)

```
Sender                 Peer 1                Peer 2               Destination
  │                    (Router)               (Router)                 │
  │                      │                       │                     │
  │ NetworkTicket        │                       │                     │
  ├─ ControlForm────────→│                       │                     │
  │  (to Destination)    │                       │                     │
  │                      │ (broadcasts per route)│                     │
  │                      ├──────────────────────→│                     │
  │                      │                       │ (delivers to dest)  │
  │                      │                       ├────────────────────→│
  │                      │                       │                     │
  │                      │                       │      Response       │
  │                      │                       │← (via peer polling) │
  │                      │                       │                     │
  │ (polls for response) │                       │                     │
  │← (via peer polling)──┤                       │                     │
  │                      │                       │                     │
```

#### Polling Pattern

For agents without direct connectivity, the polling mechanism keeps peers synchronized:

```
Agent A (polls)        Agent B (polled)
    │                       │
    │ POST /mpi             │
    ├── NetworkMessagesRequest────────→│
    │                                  │
    │                    Returns queued│
    │                   NetworkMessages│
    │← NetworkMessagesResponse─────────┤
    │                                  │
    (repeats every 1 second)           │
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
```

**Usage:**
```bash
# View current configuration
python -m stembot.configure --view

# Set individual values
python -m stembot.configure --agtuuid my-agent --port 8080

# Load from environment variables
python -m stembot.configure --load-env

# Set client URL to localhost
python -m stembot.configure --client-local
```

#### `control` - Online Agent Management

Sends control requests to a running agent. Requires the agent to be running and reachable.

**Usage:**

```bash
# Discover a new peer
python -m stembot.control discover http://agent-b:8080/mpi

# Manage peers
python -m stembot.control delete --agtuuid agent-b-uuid
python -m stembot.control delete --all

# Agent statistics
python -m stembot.control stat agent-b    # Config, peers, routes, hops

# Execute remote command
python -m stembot.control exec agent-b "ls -la"

# File transfer
python -m stembot.control put agent-b /local/path /remote/path

# Performance testing
python -m stembot.control bench agent-b   # Measure latency/throughput
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

