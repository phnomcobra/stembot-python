#!/usr/bin/bash
set -e
container_id=$(sudo docker-compose ps -q c1)
sudo docker exec "$container_id" agt-control test c1,c2,c3,c4,c5
