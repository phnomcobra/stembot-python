#!/usr/bin/bash
sudo /usr/bin/bash -c 'source .venv/bin/activate && pytest --maxfail=5 scripts/test.py stembot -vv'
