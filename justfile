set dotenv-filename := "tests/system_tests/.env"

compose +ARGS="up -d":
    podman compose -f tests/system_tests/compose.yaml {{ARGS}}

blueapi *ARGS="serve":
    uv run blueapi -c tests/system_tests/config.yaml {{ARGS}}

lint:
    uv run ruff check
    uv run pyright

unit:
    uv run pytest tests/unit_tests

system:
    uv run pytest tests/system_tests
