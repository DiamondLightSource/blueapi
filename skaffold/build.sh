#!/bin/bash

# This script is called by skaffold in order to build the container and, if required push it to the
# Google Cloud repo specifed in the skaffold.yaml file (nomally gcr.io/diamond-privreg/athena-dev).
# It received the following environment variables from skaffols:
#   $IMAGE          The name of the image to build including the cloud repo e.g. gcr.io/diamond-privreg/athena-dev/<NAME>
#   $PUSH_IMAGE     Whether the build image should be pushed to the repo (true by default unless disbled in the skaffold.yaml file)
#   $BUILD_CONTEXT  Absolute path to the project directory
#   $PLATFORMS      Comma separated string of platforms to build the image for e.g. linusx/amd64
#   $SKIP_TEST      Whether to skip the test after building the image
#   
#   All current local environment variables such as $HOST, $PATH etc are also passed in

podman build . --file .devcontainer/Dockerfile -t $IMAGE --platform $PLATFORMS
if [[ "${PUSH_IMAGE}" == "true" ]]; then
  podman push $IMAGE
fi
