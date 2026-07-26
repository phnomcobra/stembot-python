# Changelog

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
