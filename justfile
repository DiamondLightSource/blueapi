SESSION := "cm12345-1"

[doc('Start the services and run the blueapi server, Ctrl-C stops both')]
dev-server: init-example-services
    uv run python -m tests.system_tests.stack just serve

[doc('Clone the example-services submodule if needed but leave it alone otherwise')]
init-example-services:
    #!/usr/bin/env bash
    if [[ $(git submodule status example-services) =~ ^- ]]; then
        git submodule update --init example-services
    fi

[doc('Start the services until Ctrl-C: EPICS IOCs via compose, the rest via testcontainers')]
services: init-example-services
    uv run python -m tests.system_tests.stack

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
    just unit "-n logical --cov --cov-report html"
    uv run python -m webbrowser -t htmlcov/index.html

[doc('Start an interactive REPL with an authenticated blueapi client')]
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
