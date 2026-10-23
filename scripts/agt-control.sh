set -e
service="$1"
shift
container_id=$(sudo docker compose ps -q "$service")
if [ -z "$container_id" ]; then
    echo "No running container found for service '$service'" >&2
    exit 1
fi
sudo docker exec "$container_id" agt-control "$@"
