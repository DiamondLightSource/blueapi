SESSION := "cm12345-1"

compose +ARGS="up -d":
    docker compose -f tests/system_tests/compose.yaml {{ARGS}}

configure-adsim: (compose "exec" "numtracker" "/app/numtracker" "client" "configure" "adsim"
        "--directory" '/tmp/'
        "--scan" '{instrument}-{scan_number}'
        "--detector" '{instrument}-{scan_number}-{detector}'
        "--number" "43")

services: compose configure-adsim

serve *OPTS:
    #!/usr/bin/env bash
    source tests/system_tests/.env
    uv run blueapi -c tests/system_tests/config.yaml {{OPTS}} serve

run PLAN PARAMS:
    uv run blueapi -c tests/system_tests/config.yaml controller run -i {{ SESSION }} {{ PLAN }} '{{ PARAMS }}'

lint:
    uv run blueapi config-schema -u
    uv run blueapi schema -u
    uv run prek run --all-files
    uv run pyright src tests

unit:
    uv run pytest tests/unit_tests

system:
    uv run pytest tests/system_tests
