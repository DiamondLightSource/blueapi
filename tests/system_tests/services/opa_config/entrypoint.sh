#!/bin/sh
/opa build -b /mnt/opa_data -o /tmp/bundle.tar.gz
/opa run --server --addr localhost:8181 -b /tmp/bundle.tar.gz --config-file /mnt/config.yaml
