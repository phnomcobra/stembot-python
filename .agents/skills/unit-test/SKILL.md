---
name: unit-test
description: This skill runs a set of unit tests.
---

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

You can run the tests with the following command:
```bash
sudo /usr/bin/bash -c 'source .venv/bin/activate && python -m pytest stembot -vv'
```
