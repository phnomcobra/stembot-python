#!/usr/bin/bash
set -e
sudo /usr/bin/bash -c 'source .venv/bin/activate && poetry build'
sudo rm -rf log || true
sudo docker-compose down || true
sudo docker-compose up
