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

unit *OPTS:
    uv run pytest -n logical tests/unit_tests {{ OPTS }}

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
