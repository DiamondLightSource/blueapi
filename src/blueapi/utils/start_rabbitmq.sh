#!/bin/bash
echo "Checking docker installation"
if command -v docker &> /dev/null; then
    docker run -it --rm --net host rmohr/activemq:5.15.9-alpine
elif command -v podman &> /dev/null; then
    podman run -it --rm --net host rmohr/activemq:5.15.9-alpine
    #rabbitmq-plugins enable rabbitmq_stomp
else
    echo "Docker and Podman installation not found. Please install docker/podman."
    exit 1
fi