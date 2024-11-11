#!/bin/bash
SCRIPT_DIR=$( cd -- "$( dirname -- "$BASH_SOURCE[0]" )" &> /dev/null && pwd )

echo "Checking docker/podman installation"
if command -v docker &> /dev/null; then
    docker compose -f $SCRIPT_DIR/docker-compose.yml up
elif command -v podman &> /dev/null; then
    podman compose -f $SCRIPT_DIR/docker-compose.yml up
else
    echo "Docker/Podman installation not found. Please install docker/podman."
    exit 1
fi
