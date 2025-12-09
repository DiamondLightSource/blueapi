#!/bin/sh
/opa build -b /mnt/opa_data -o /mnt/bundle.tar.gz
/opa run --server --addr localhost:8181 -b /mnt/bundle.tar.gz --config-file /mnt/config.yaml
