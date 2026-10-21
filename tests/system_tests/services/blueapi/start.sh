#!/bin/sh
# dodal is not in the image, setup-scratch clones and installs it from config-scratch.yaml
set -e
mkdir -p /tmp/scratch/blueapi
blueapi -c /blueapi/config.yaml -c /blueapi/config-scratch.yaml setup-scratch
exec blueapi -c /blueapi/config.yaml -c /blueapi/config-scratch.yaml serve
