#!/usr/bin/bash
sudo /usr/bin/bash -c 'source .venv/bin/activate && python -m pytest --maxfail=5 scripts/test_external.py -vv'
