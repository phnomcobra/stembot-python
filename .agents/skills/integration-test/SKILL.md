---
name: integration-test
description: This skill runs a set of integration tests derived from a set of control forms and a set of agents to direct tickets at. The goal of the tests is to ensure that all tickets get serviced across a variety of agent configurations.
---

Running these test requires that docker and docker-compose are installed and running on your machine.

### 1. Start the deployment

Build the wheel and bring up the agent containers (c1-c5) defined in `docker-compose.yml`:
```bash
./scripts/run.sh
```
This runs in the foreground. Wait for each container's startup logs to show it has configured itself and created its user key (`agt-configure --user-key-objuuid ...` / `set-user-key`) before it starts `agt-server` — agents cannot securely talk to each other until they've keyed themselves.

### 2. Run tests against the deployment

Once all containers are up and keyed, use `./scripts/agt-control.sh` from a separate terminal as a passthrough into c1's container to drive `agt-control` against any agent in the deployment:
```bash
# Agent statistics (config, peers, routes, hops)
./scripts/agt-control.sh stat c1

# Run the synthetic control-form/ticket test suite against one or more agents
./scripts/agt-control.sh test c1,c2,c3,c4,c5

# Benchmark throughput to a specific agent
./scripts/agt-control.sh bench c1
```
If a connection timeout occurs, retry the command.

# Notes
Keys are resolved per-peer via each agent's `KeyManager` (see `stembot/crypto.py`), so every agent must have completed its own key setup (via environment variables, `agt-configure --user-key-objuuid/--user-key-passphrase`, or `agt-control set-user-key`) before it can service tickets from or to other agents.

