SESSION := "cm12345-1"
RUNNER := `command -v docker || command -v podman`

default: compose serve

init-example-services:
    #!/usr/bin/env bash
    # Clone the example-services submodule if needed but leave it alone otherwise
    if [[ $(git submodule status example-services) =~ ^- ]]; then
        git submodule update --init example-services
    fi

compose +ARGS="up -d --no-recreate": init-example-services
    {{ RUNNER }} compose -f tests/system_tests/compose.yaml {{ARGS}}

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

unit *OPTS="-n logical":
    uv run pytest tests/unit_tests {{ OPTS }}

system *OPTS:
    uv run pytest tests/system_tests {{ OPTS }}

coverage:
    uv run pytest tests/unit_tests --cov --cov-report html
    xdg-open htmlcov/index.html

repl:
    #!/usr/bin/env bash
    uv run --with ptpython ptpython -i <(cat << EOF
    from blueapi.client import BlueapiClient
    from blueapi.client.rest import ServiceUnavailableError
    bc = BlueapiClient.from_config_file("tests/system_tests/config.yaml").with_instrument_session("cm12345-1")
    try:
        bc.login()
    except KeyboardInterrupt:
        print("Login cancelled")
    except ServiceUnavailableError:
        print("Couldn't access blueapi server to log in")
    except Exception as e:
        import traceback
        print("Couldn't log in")
        traceback.print_exception(e, chain=False)
    EOF
    )
