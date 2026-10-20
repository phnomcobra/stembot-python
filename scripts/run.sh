set -e
sudo rm -rf dist/*
sudo bash -c 'source .venv/bin/activate && python -m poetry build'
sudo rm -rf log || true
sudo docker-compose down || true
sudo docker-compose up
