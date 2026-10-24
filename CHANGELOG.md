# Changelog

## [3.0.1] - 2026-10-24

### Changed
- Added Python 3.14 support — Docker base image bumped to `python:3.14-slim`, `Python :: 3.14` classifier added, and `pydantic` bumped from `2.10.6` to `2.14.1` (pulling in a `pydantic-core` release with prebuilt Python 3.14 wheels) while keeping the existing `>=3.10` floor.
- Hardened `ControlForm`/`NetworkMessage` model discrimination: every control-form subtype's `type` field is now `Literal[...]` pinned to its own enum value (rather than the plain `ControlFormType`/`NetworkMessageType`), and `ControlFormTicket.form`/`NetworkTicket.form` now declare `Field(discriminator='type')`, so pydantic always resolves the wrapped form to the correct subtype instead of relying on left-to-right union matching.

### Fixed
- `Document.__init__` and `dao/utils.py`'s in-memory lock no longer pass deprecated positional arguments to `sqlite3.connect()` / `threading.RLock()`, eliminating `DeprecationWarning`s under Python 3.14.

## [3.0.0] - 2026-10-19

### Changed
- **Breaking: removed the shared encryption secret** — `Config.key`, `AGT_SECRET`, and `agt-configure --secret` are gone. Control forms and network messages are no longer secured by a single shared key.
- Every request now carries a `Key-UUID` header; `AgentClient` resolves a per-peer key via `KeyManager.resolve_key_objuuid()` (preferring `DIST` > `USER` > `AUTO`, longer TTL breaking ties) instead of using one static key for all peers.
- `KeyManager`'s keyring store is now configured once per process at import time rather than on every `KeyManager()` instantiation, removing a hot-path race on the native/file-backed credential store.
- `bench` combines the `OUT`/`IN` rows into a single row per size/concurrency, showing paired `out / in` values for Elapsed, Success, and Bandwidth.

### Added
- `stembot/crypto.py` — `KeyManager` lifecycle for `USER` (passphrase-derived), `AUTO` (random fallback), and `DIST` (peer-exchanged) keys, including expiration, rotation, and deprecation handling.
- `ExchangeKeys` network message and `rotate_and_exchange_keys` scheduled task for automatic key exchange between peers.
- `agt-control set-user-key` — remotely bootstrap a passphrase-derived user key on an agent.
- `agt-control test` — generates and runs a synthetic `unittest` suite that exercises control forms/tickets against one or more agents.
- `--user-key-objuuid`/`--user-key-passphrase`/`--user-key-agtuuid` options on `agt-configure`, and matching `AGT_USER_KEY_OBJUUID`/`AGT_USER_KEY_PASSPHRASE`/`AGT_USER_KEY_AGTUUID` environment variables.
- `scripts/agt-control.sh` — passthrough script to run `agt-control` inside the deployed c1 container; `scripts/stat.sh` now accepts an optional `agtuuid` argument.
- Unit tests covering `stembot/crypto.py`, `stembot/models/crypto.py`, `ExchangeKeys` serialization, and the updated `AgentClient` key-resolution/401 behavior.

### Fixed
- `AgentClient` deletes a rejected distributed key on a `401` response so a fresh key is resolved on the next request, instead of retrying the same doomed request.
- `resolve_agent_key()` now wraps `KeyManager.decrypt_key()`'s `KeyError` as `ValueError`, matching its documented exception contract.

## [2.1.1] - 2026-08-01

### Changed
- Bumped project version from `2.1.0` to `2.1.1`.
- Separated filtering functionality from `pull_network_messages`.
- Added `pull_filtered_network_messages` and `filter_network_messages` to messaging.

## [2.1.0] - 2026-07-25

### Added
- `network_whitelist` and `control_whitelist` fields on `NetworkMessagesRequest` for server-side filtering of polled messages.
- Unit tests for whitelist handling in `pull_network_messages`.

### Changed
- `pull_network_messages` now applies whitelist filtering using filtered lists rather than in-place removal during iteration.

### Fixed
- Conversion of queued ticket-request messages to `NetworkTicket` now validates from model data before generating whitelist rejection responses.
- Serialization/deserialization tests for `NetworkMessagesRequest` now cover the new whitelist fields.

## [2.0.0] - 2026-05-18

### Changed
- **Breaking: binary transport encoding** — HTTP bodies are now raw binary (`Content-Type: application/binary`). `Nonce` and `Tag` headers are hex strings (`.hex()` / `bytes.fromhex()`), replacing the previous base64 encoding.
- **`bench` command rewritten** — Benchmarks now use the `Benchmark` control form with server-side payload generation. Output rows match the Rust implementation format: `Dir`, `Elapsed (s)`, `Total Bytes`, `Success`, `Bytes/Op`, `Bandwidth`. Combined bidirectional pass removed; only directional `OUT` and `IN` passes are reported.
- **CLI modularized** — `agt-control` subcommands (`bench`, `delete`, `discover`, `put`, `run`, `stat`) extracted to individual modules under `stembot/cli/`. `stembot/control.py` is now a thin entry-point shim.

### Added
- `Benchmark` control form (`stembot/models/control.py`) with `outbound_size`, `inbound_size`, and `payload` fields.
- `stembot/cli/utils.py` — shared `format_bytes` and `format_bandwidth` formatting helpers and `KB`/`MB`/`GB` constants.
- `limit` reserved attribute name in `Document.find_objuuids` — `limit=N` kwparam caps result count; passing `limit` as a positional param string or to `create_attribute` raises `ValueError`.
- `limit` field on `NetworkMessagesRequest` for server-side message fetch limiting.
- Serialization/deserialization tests for `Benchmark` in `stembot/models/test_control.py`.
- Reserved-attribute and limit-behavior tests in `stembot/dao/test_collection.py`.

### Fixed
- Binary content-type padding errors in `send_control_form` and `send_network_message` caused by applying base64 decoding to a raw binary body.
- `test_agent.py` updated to use hex headers and raw binary body/response, removing stale `b64decode`/`b64encode` usage.

## [1.0.0]

Initial release.
