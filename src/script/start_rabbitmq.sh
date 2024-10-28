#!/bin/bash
SCRIPT_DIR=$( cd -- "$( dirname -- "$BASH_SOURCE[0]" )" &> /dev/null && pwd )
cmd1='build -t rabbitmq-stomp '$SCRIPT_DIR'/rabbitmq_setup/.'
cmd2='run -p 5672:5672 -p 15672:15672 -p 61613:61613 rabbitmq-stomp'

echo "Checking docker/podman installation"
if command -v docker &> /dev/null; then
    docker $cmd1
    docker $cmd2
elif command -v podman &> /dev/null; then
    podman $cmd1
    podman $cmd2
else
    echo "Docker/Podman installation not found. Please install docker/podman."
    exit 1
fi