set dotenv-filename := "tests/system_tests/.env"

compose +ARGS="up -d":
    docker compose -f tests/system_tests/compose.yaml {{ARGS}}

configure-adsim: (compose "exec" "numtracker" "/app/numtracker" "client" "configure" "adsim"
        "--directory" '/tmp/'
        "--scan" '{instrument}-{scan_number}'
        "--detector" '{instrument}-{scan_number}-{detector}'
        "--number" "43")

services: compose configure-adsim

blueapi *ARGS="serve":
    uv run blueapi -c tests/system_tests/config.yaml {{ARGS}}

lint:
    uv run ruff check
    uv run pyright

unit:
    uv run pytest tests/unit_tests

system:
    uv run pytest tests/system_tests
