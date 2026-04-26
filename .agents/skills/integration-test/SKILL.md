---
name: integration-test
description: This skill runs a set of integration tests derived from a set of control forms and a set of agents to direct tickets at. The goal of the tests is to ensure that all tickets get serviced across a variety of agent configurations.
---

Running these test requires that docker is installed and running on your machine.

The test suite is built on pytest and requires a python virtual environment. You can set up the environment and run the tests with the following commands:
```bash
python3 -m venv .venv
```

The project uses poetry to manage dependencies. You can install poetry with pip:
```bash
source .venv/bin/activate && pip install poetry
```

Once poetry is installed, you can install the project dependencies with:
```bash
source .venv/bin/activate && poetry install
```

Running the tests requires elevated permissions to access docker. You can run the tests with the following command:
```bash
sudo /usr/bin/bash -c 'source .venv/bin/activate && python -m pytest --maxfail=5 scripts/test.py -vv'
```
If a connection timeout occurs, retry the command.