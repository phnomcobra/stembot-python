#!/usr/bin/bash
sudo /usr/bin/bash -c 'source .venv/bin/activate && pytest --maxfail=5 test.py stembot -vv'
