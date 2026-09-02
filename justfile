SESSION := "cm12345-1"
RUNNER := `command -v docker || command -v podman || true`

_check-runner:
    #!/usr/bin/env bash
    if [[ "{{ RUNNER }}" == "" ]]; then
        echo "{{ style('error') }}error{{ NORMAL }}: No container runtime available - either podman or docker is required"
        exit 1
    fi

[doc('Start the example services via compose and run the blueapi server')]
default: compose serve

[doc('Clone the example-services submodule if needed but leave it alone otherwise')]
init-example-services:
    #!/usr/bin/env bash
    if [[ $(git submodule status example-services) =~ ^- ]]; then
        git submodule update --init example-services
    fi

[doc('Bring up the example services with docker/podman compose')]
compose +ARGS="up -d --no-recreate": init-example-services _check-runner
    {{ RUNNER }} compose -f tests/system_tests/compose.yaml {{ ARGS }}

[doc('Run the blueapi server with the system test config')]
serve *OPTS:
    #!/usr/bin/env bash
    source tests/system_tests/.env
    uv run blueapi -c tests/system_tests/config.yaml {{ OPTS }} serve

[doc('Run a plan using the blueapi CLI')]
run PLAN PARAMS:
    uv run blueapi -c tests/system_tests/config.yaml controller run -i {{ SESSION }} {{ PLAN }} '{{ PARAMS }}'

[doc('Regenerate schemas, run pre-commit checks and type checking')]
lint:
    uv run blueapi config-schema -u
    uv run blueapi schema -u
    uv run prek run --all-files
    uv run pyright src tests

[doc('Run the unit test suite')]
unit *OPTS="-n logical":
    uv run pytest tests/unit_tests {{ OPTS }}

[doc('Run the system test suite')]
system *OPTS:
    uv run pytest tests/system_tests {{ OPTS }}

[doc('Run unit tests with coverage and open the HTML report')]
coverage:
    uv run pytest tests/unit_tests --cov --cov-report html
    xdg-open htmlcov/index.html

[doc('Start an interactive REPL with an authenticated blueapi clien')]
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
