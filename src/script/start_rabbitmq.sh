#!/bin/bash
SCRIPT_DIR=$( cd -- "$( dirname -- "$BASH_SOURCE[0]" )" &> /dev/null && pwd )
RABBITMQ_VERSION="rabbitmq:3.13.2-management"
cmd1='run -it --rm --name rabbitmq -v '$SCRIPT_DIR'/rabbitmq_setup/rabbitmq.conf:/etc/rabbitmq/rabbitmq.conf -v '\
$SCRIPT_DIR'/rabbitmq_setup/enabled_plugins:/etc/rabbitmq/enabled_plugins'\
' -p 5672:5672 -p 15672:15672 -p 61613:61613 '$RABBITMQ_VERSION

echo "Checking docker/podman installation"
if command -v docker &> /dev/null; then
    docker $cmd1
elif command -v podman &> /dev/null; then
    podman $cmd1
else
    echo "Docker/Podman installation not found. Please install docker/podman."
    exit 1
fi