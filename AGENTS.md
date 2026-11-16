# AGENTS.md

Guidance for AI coding agents working in this repository. Humans should start with [README.md](README.md) and [.github/CONTRIBUTING.md](.github/CONTRIBUTING.md).

This file holds what you cannot cheaply work out from the code: the checks CI runs, the files that must change together, and the contracts other teams rely on. If it disagrees with the code, the CI config or the tests, those win. Fix this file in the same pull request.

## What blueapi is

blueapi runs [bluesky](https://blueskyproject.io/bluesky) plans as a service. It wraps a `RunEngine` and a registry of plans and [ophyd-async](https://github.com/bluesky/ophyd-async) devices, exposes them over a FastAPI REST and WebSocket API, and publishes progress and data documents to a STOMP message bus (RabbitMQ). It also ships the `blueapi` CLI and a Python client.

It is developed at Diamond Light Source (DLS) and deployed on beamlines from a container image and a Helm chart. The plans and devices it serves live in other repositories and are loaded by configuration.

Every release tag publishes three artefacts: a PyPI package, a container image and a Helm chart. Other teams depend on all three, and also on the REST API, the message bus events, the YAML config format, the CLI and the Python client. Treat each of these as a public contract.

- Python 3.11 is the minimum. CI tests 3.11 to 3.14, and the development default is 3.13 (`.python-version`). Do not use syntax newer than 3.11, such as `type` aliases or `class Foo[T]`.
- Main dependencies: bluesky, ophyd-async, pydantic v2, click, requests and stomp-py. The `server` extra adds FastAPI, uvicorn, aiohttp, httpx and tiled.

## Commands

The recommended developer environment is the devcontainer defined by `.devcontainer/` and the `developer` stage of the `Dockerfile` (see [docs/how-to/run-with-dev.md](docs/how-to/run-with-dev.md)). It provides `uv`, `just` and `helm` with its schema plugin. Creating it runs `uv sync` and installs the prek hooks, and the virtual environment is on `PATH`. Check whether you are inside it with `command -v just helm`.

Inside the devcontainer, run these before you report a change as done. CI runs the same checks.

```sh
just lint     # regenerate both schemas, run prek on all files, run pyright
just unit     # unit tests in parallel: about 1,100 tests, roughly a minute
```

Outside it, do not build or start the devcontainer yourself unless asked. That is the user's decision, because it builds an image, uses host networking and mounts the repository's parent directory. Run the same checks through [uv](https://docs.astral.sh/uv/) instead:

```sh
uv sync                                   # create or refresh .venv with the dev group
uv run blueapi schema -u                  # regenerate docs/reference/openapi.yaml
uv run blueapi config-schema -u           # regenerate helm/blueapi/config_schema.json
uv run prek run --all-files               # ruff lint and format, lock file sync, helm docs and schema, gitleaks
uv run pyright src tests
uv run pytest tests/unit_tests -n logical
```

These work in either environment:

```sh
# Narrower runs while iterating
uv run pytest tests/unit_tests/service/test_rest_api.py
uv run pytest tests/unit_tests/test_config.py::test_config_yaml_parsed
uv run pytest tests/unit_tests/service -k "get_plans"

# Only when docs/ or docstrings changed. Warnings fail the build. Output goes to build/html.
uv run tox -e docs
```

### Things that will trip you up

- **Never run `pytest` without a path.** The configured test paths are `docs`, `src` and `tests`, so a bare run also collects `tests/system_tests`, which need a stack of live services.
- **The devcontainer has no docker or podman.** `just compose` works only on the host, and so does a bare `just`, whose default recipe starts the service stack.
- **Outside the devcontainer, `helm` must be on `PATH` for the full unit suite.** Without it, more than 200 tests in `tests/unit_tests/test_helm_chart.py` and `test_example_config.py` fail with `FileNotFoundError: 'helm'`. That is a missing binary, not a regression. The `helm-schema` pre-commit hook also needs the `helm-values-schema-json` plugin (see `.github/workflows/_tox.yml` for the install line). If you cannot install helm and have not touched `helm/` or `src/blueapi/config.py`, use the commands below and say in your summary that the helm checks were not run:

  ```sh
  uv run pytest tests/unit_tests -n logical \
    --ignore=tests/unit_tests/test_helm_chart.py \
    --deselect tests/unit_tests/test_example_config.py::test_example_helm_is_valid
  uv run prek run --all-files --skip helm-schema --skip helm-docs-built
  ```

- **A local `main` branch must exist and be current.** `test_schema_version_bump_required` reads `main:docs/reference/openapi.yaml` from git. In a fresh worktree or shallow clone run `git branch --track main origin/main`. If the test fails unexpectedly, run `git fetch origin main:main` from your feature branch.
- **Format with prek, not with `uv run ruff format .`.** The ruff in `uv.lock` is newer than the one pinned in `prek.toml`, and CI enforces the pinned one. At the time of writing the newer ruff also rewrites code blocks in `README.md` and `docs/*.md`, which creates unrelated diffs. If you call ruff directly, pass `src tests`.
- **`Required uv version` errors mean your uv is too old.** Upgrade uv. Do not edit `required-version` in `pyproject.toml`.
- **Warnings fail tests.** Pytest runs with `filterwarnings = ["error", "ignore::DeprecationWarning"]`.
- **Async tests need no marker.** `asyncio_mode = "auto"` is set, so write `async def test_...` directly.
- **Do not source `tests/system_tests/.env` in the shell you use for unit tests or the CLI.** It sets EPICS variables, and without the simulated IOCs running the CLI hangs for about 30 seconds on exit (#1397).

### System tests

`tests/system_tests` run end to end against RabbitMQ, Keycloak, numtracker, Tiled, OPA and simulated EPICS IOCs. They need docker or podman compose, the `example-services` git submodule and a Playwright Chromium for the device-flow login.

```sh
just compose      # on the host: start the service stack in the background
just serve        # run the blueapi server with tests/system_tests/config.yaml
just system       # in another terminal
```

See [docs/how-to/just-run-blueapi-and-services-locally.md](docs/how-to/just-run-blueapi-and-services-locally.md) for details. CI runs these tests on every pull request. Most agent sandboxes cannot run them. In that case say you did not run them. If your change affects end-to-end behaviour (authentication, numtracker, Tiled, STOMP or the client), add or update a system test anyway.

## Layout

```text
src/blueapi/
  config.py     ApplicationConfig (root of the YAML config) and REST_API_VERSION
  core/         BlueskyContext: RunEngine, plan and device registries, plan signature to pydantic model
  worker/       TaskWorker (one task at a time, on its own thread), Task, WorkerEvent, ProgressEvent
  service/      Server only: FastAPI app (main.py), subprocess RPC (runner.py, interface.py),
                API models (model.py), WebSocket protocol, OIDC authentication, OPA authorization, numtracker
  client/       BlueapiClient for scripts, BlueapiRestClient, STOMP EventBusClient, login session cache
  cli/          click CLI: serve, controller ..., login, logout, schema, config-schema, setup-scratch
  utils/  log.py  tutorial/
tests/unit_tests/    Mirrors src/. code_examples/, valid_example_config/ and helm_examples/ are included in the docs
tests/system_tests/  Compose stack and end-to-end tests
docs/                Sphinx with MyST Markdown: tutorials, how-to, explanations, reference
helm/blueapi/        Helm chart (StatefulSet). Its values schema is generated from the config model
example-services/    Git submodule from epics-containers, used only by the system test stack
```

Published documentation is at <https://diamondlightsource.github.io/blueapi>. The pages most useful for orientation are `docs/explanations/` (architecture, lifecycle of a plan, type validators, events, API version) and the decision records in `docs/explanations/decisions/`.

## Architecture you need to know before editing

### Two processes

The server is two processes. The main process runs FastAPI under uvicorn. A single subprocess (a `multiprocessing` pool of one, started with `spawn`) holds the `BlueskyContext`, the `TaskWorker`, the `RunEngine`, every device, the STOMP connection and the Tiled writer. Reloading the environment (`DELETE /environment`) stops that subprocess and starts a new one, which is how edited plan code is picked up.

The web process reaches the subprocess only through `WorkerDispatcher.run`, passing a function from `service/interface.py`:

```python
# service/interface.py: runs in the subprocess
def get_worker_state() -> WorkerState:
    """State of the worker"""
    return worker().state


# service/main.py: runs in the web process
@secure_router_v1.get("/worker/state", tags=[Tag.TASK])
@secure_router.get("/worker/state", tags=[Tag.TASK])
@start_as_current_span(TRACER)
def get_state(runner: Annotated[WorkerDispatcher, Depends(_runner)]) -> WorkerState:
    """Get the State of the Worker"""
    return runner.run(interface.get_worker_state)
```

This has consequences that are easy to miss:

- The function must be a named, module-level function. The subprocess finds it by module and name, so lambdas, closures and bound methods fail with `RpcError`.
- Arguments, return values and raised exceptions cross a process boundary, so they must be picklable. A pydantic `ValidationError` is not, which is why `TaskParameterError` in `worker/task.py` defines `__reduce__`.
- The return annotation is used to validate the returned value, so it must be accurate.
- State in the subprocess lives in `@cache`d functions in `interface.py` (`context()`, `worker()`, `stomp_client()` and others). If you add one, clear it in `teardown()`, or it will survive an environment reload.
- Never touch the context, worker or devices directly from `main.py`.

### Plans, devices and tasks

- A plan is a function annotated to return `MsgGenerator`. `BlueskyContext.register_plan` builds a pydantic model from its signature. Parameters typed as bluesky protocols or ophyd-async devices become reference types that accept a device name and resolve it to the live device. Read `docs/explanations/type_validators.md` before changing `core/context.py`.
- Devices come from an object satisfying the `DeviceManager` protocol in `core/protocols.py`. The protocol is structural so that blueapi does not depend on dodal, the DLS device library.
- The worker runs one task at a time and returns HTTP 409 if asked to start another. This is a recorded decision (ADR 0003). Do not add queueing.
- Requests carry an `instrument_session` such as `cm12345-1`, which authorization and data paths depend on.

### API routing and auth

- Existing REST endpoints are registered twice: on `secure_router_v1` (`/api/v1/...`) and on the unprefixed `secure_router`, which is deprecated and kept so that existing clients continue to work. New endpoints go on a versioned router.
- Unauthenticated endpoints (`/healthz`, `/config/oidc`, the root redirect) are on `open_router`. `/api/v2` currently holds only the `run_plan` WebSocket, whose message types are in `service/protocol.py`.
- When `oidc` is configured, every secure route validates a bearer JWT. When `opa` is configured, Open Policy Agent decides who may submit a task, and users who are not admins can see and control only their own tasks.

## Changes that must travel together

CI enforces most of these. Missing one is the most common reason a pull request goes red.

- **Anything that alters the generated OpenAPI schema** (routes, models in `service/model.py`, event models returned by endpoints):
  - Run `uv run blueapi schema -u` and commit `docs/reference/openapi.yaml`.
  - Bump `ApplicationConfig.REST_API_VERSION` in `src/blueapi/config.py` using semver. A test fails if the schema differs from `main` without a higher version.
- **`ApplicationConfig` or any model nested in it:**
  - Run `uv run blueapi config-schema -u`. The `helm-schema` hook then regenerates `helm/blueapi/values.schema.json`.
  - Add any new top-level field to the hand-written `ApplicationConfig.__eq__`.
  - For user-facing options, add an example to `tests/unit_tests/valid_example_config/`. Every file there is loaded by a test and can be included in the docs.
- **`helm/blueapi/values.yaml` or the templates:**
  - Let the hooks regenerate `helm/blueapi/README.md` (from the `# --` comments) and `values.schema.json`.
  - Add a case to `tests/unit_tests/test_helm_chart.py`, which renders the chart with `helm template`.
- **Events sent to the message bus** (`WorkerEvent`, `ProgressEvent`, `DataEvent`): update the hand-maintained `docs/reference/asyncapi.yaml`. Its event-model URLs must match the `event-model==` pin in `pyproject.toml`, so change both together.
- **Dependencies:** edit `pyproject.toml`, then run `uv lock`. CI installs with `--locked`.
- **Renaming or removing anything importable:** beamline repositories import blueapi as a library, so keep the old name working.
  - For module attributes, use a module `__getattr__` that warns (see the end of `src/blueapi/config.py`). For functions, use `@deprecated("alternative")` from `blueapi.utils`.
  - Add a case to `tests/unit_tests/test_deprecation.py` and use the `depr:` commit type. Outright removal waits for 2.0 (#1256).
- **Code shown in the docs:** examples live in `tests/unit_tests/code_examples/` and are pulled in with `literalinclude` and exercised by `test_example_code.py`. Edit the example file, not an inline copy.

### The client must import without the server extra

`pip install blueapi` installs only the client and CLI. FastAPI, uvicorn, aiohttp, httpx, tiled, graypy and aioca arrive only with `blueapi[server]`.

- Never import those packages at module level outside `blueapi/service/`. Inside it, `service/model.py` and `service/protocol.py` are imported by the client, so they must stay free of them too.
- Where the CLI or logging needs a server-only package, import it inside the function, as `serve` and `schema` do in `cli/cli.py`.
- dodal is not a runtime dependency. Only `blueapi/tutorial/` and the tests may import it.
- `tox -e client-system-test` checks this in CI by running the client tests in an environment without the extra.

### Generated files

Do not edit these by hand. Regenerate them.

| File | Produced by |
| --- | --- |
| `docs/reference/openapi.yaml` | `uv run blueapi schema -u` |
| `helm/blueapi/config_schema.json` | `uv run blueapi config-schema -u` |
| `helm/blueapi/values.schema.json` | prek hook `helm-schema` |
| `helm/blueapi/README.md` | prek hook `helm-docs-built` |
| `uv.lock` | `uv lock` |
| `src/blueapi/_version.py`, `docs/_api/` | Build tooling. Both are gitignored |

## Conventions

- **Style:** ruff with rule sets B, C4, E, F, N, W, I, UP, SLF and FAST, line length 88. Pyright runs in standard mode over `src` and `tests`. Annotate everything and use modern syntax (`X | None`, `list[str]`, `collections.abc`).
- **Suppressions are rare.** `src/` has only a handful of `# type: ignore`, `# noqa` and `# pragma: no cover` comments. Add one only with a comment explaining why.
- **Generics:** the code makes heavy use of generics. blueapi declares its own with `TypeVar`, `ParamSpec`, `Generic` and `Protocol`, and builds on parameterised types from bluesky and ophyd-async such as `Movable[float]` and `MsgGenerator[None]`.
  - Decide the variance of every type variable you add or reuse. A type that only produces values of `T` should be covariant in it, one that only consumes them contravariant, and one that does both invariant. Python 3.11 does not infer variance, so declare it with `TypeVar(..., covariant=True)` or `contravariant=True`.
  - Do not assume the variance of a library type. In bluesky, for example, `Movable` is contravariant in its value type and `Readable` is invariant.
  - Add tests that pin the form of genericness you intend, covering what must be rejected as well as what must be accepted. Pyright checks `tests/`, so use `typing.assert_type` or an annotated assignment to test static behaviour.
  - Code that inspects generics at run time is invisible to pyright and needs runtime tests with a subtype, a supertype and an unrelated type. The main case is `is_compatible_args` in `core/context.py`, which decides whether a device satisfies an annotation such as `Movable[int]`. At the time of writing it applies `issubclass(actual, expected)` to every type argument, whatever variance the protocol declares.
- **Exceptions** are named `SomethingError` (ruff N818).
- **Models** extend `BlueapiBaseModel`, which forbids unknown fields. Give fields a `Field(description=...)`, because descriptions flow into the OpenAPI schema, the config schema and the Helm schema. JSON keys are the Python field names with no aliasing (ADR 0004).
- **Logging and tracing:** each module has `LOGGER = logging.getLogger(__name__)`. Public methods in the service, worker and client carry `@start_as_current_span(TRACER, "arg_name")`. Never log tokens or secrets. Secret config fields use `SecretStr`.
- **FastAPI:** dependencies use `Annotated[..., Depends(...)]`. Endpoint docstrings and plan docstrings are shown to users.
- **Docstrings** use Google style.
- **Tests:**
  - Plain pytest functions named `test_<behaviour>`, with heavy use of `pytest.mark.parametrize`. Put them at the path mirroring the source file.
  - Unit tests never start the real subprocess, use the network or touch hardware. Mock the dispatcher with `MagicMock(spec=WorkerDispatcher)`, or patch `interface.context` or `interface.worker`. See the fixtures at the top of `tests/unit_tests/service/test_rest_api.py`.
  - Mock HTTP with `responses` for requests, and `pytest_httpx` or `respx` for httpx. OIDC and JWT fixtures are in `tests/conftest.py`.
  - The Codecov project target is 85%, and coverage should not drop.
- **Docs:**
  - MyST Markdown, organised as tutorials, how-to guides, explanations and reference. The build is nitpicky, so a broken cross-reference fails CI.
  - File names in `docs/how-to/` and `docs/tutorials/` contain spaces and number prefixes. Quote them in the shell and write `%20` in links.
  - New pages are picked up by glob.
  - Architectural decisions get a record in `docs/explanations/decisions/`, copied from `COPYME`.
- **Scope:** reviewers here push for the smallest change that works. Expect "is this needed?" on extra parameters, abstractions and tests that duplicate existing coverage.
- **When code and docs disagree,** trust the code and tests. Fix the doc if it is in scope, otherwise mention it in your summary.

## Git and pull requests

- Branch from `main`. Pull requests are squash-merged through a merge queue, so the pull request title becomes the commit message and the release note.
- The title must be a [Conventional Commit](https://www.conventionalcommits.org/), and CI rejects anything else. Allowed types are `feat`, `fix`, `docs`, `test`, `ci`, `refactor`, `perf`, `chore`, `revert` and `depr`. Mark breaking changes with `!`, as in `chore!: Remove dodal dependency`. Scopes are optional and rarely used apart from `chore(deps)`.
- Write the title so that it makes sense to a user reading release notes: `fix: Ignore missing task ID when removing from _pending`.
- **Disclose agent involvement in the commit message.** Every commit that contains code or text generated with or by an AI agent must end with a footer of the form `Assisted-by: <model name> via <tool name>`, for example `Assisted-by: GLM 4.6 via Claude Code`. Name the model and the tool you are actually running as. Pull requests are squash-merged and the commit message is taken from the pull request title and body, so end the pull request description with the same footer. The convention is described in [Assisted-by footer](https://xeiaso.net/notes/2025/assisted-by-footer/).
- In the body, link the issue with `Fixes #123` and give the reviewer steps to test the change. The template is `.github/PULL_REQUEST_TEMPLATE/pull_request_template.md`.
- Keep each pull request to one concern. For large or design-level changes, CONTRIBUTING asks for an issue first.
- Issues need acceptance criteria. Labels worth checking before starting: `decision pending` (design not agreed), `needs clarification`, `needs investigation` and `external` (depends on another project).
- Releases are made by maintainers pushing a SemVer 2 tag such as `1.22.0` or `1.11.5-a1`. Helm rejects PEP 440 forms such as `1.11.5a1` (#411). The version comes from git tags through setuptools_scm. The `0.1.0` in `helm/blueapi/Chart.yaml` is a placeholder overridden at publish time, so do not bump it.
- Renovate handles dependency updates and lock file maintenance. Much of the scaffolding (the `_*.yml` workflows, `Dockerfile`, devcontainer, `docs/conf.py`, tool settings in `pyproject.toml`) comes from [python-copier-template](https://github.com/DiamondLightSource/python-copier-template). Keep edits there minimal, because template updates will conflict with them.

## Boundaries

**Always**

- Run the lint, type check and unit test commands above before reporting that work is done, and state plainly which checks you could not run.
- Add or update tests with every behaviour change, and regenerate schemas when their sources change.
- End every commit message and pull request description you write with the `Assisted-by` footer described under Git and pull requests.
- Keep the old behaviour working when changing anything public, unless the task says the change is breaking.

**Ask first**

- Changing the shape of a public contract: REST or WebSocket payloads, STOMP destinations or message bodies (`public.worker.event` has downstream consumers), config keys, CLI options, Helm values or `BlueapiClient` methods. Additive, optional changes are usually fine. Removals and renames are not.
- Adding a dependency, especially to the core `dependencies` list. Do not add another HTTP client. Which one to standardise on is undecided (#1069).
- Implementing an issue labelled `decision pending` or `needs clarification`.
- Changing authentication, authorization or token handling (`service/authentication.py`, `service/authorization.py`, `client/session.py`), or the security context in the Helm chart.
- Editing CI workflows, the `Dockerfile` or anything in the release path.
- Updating the `example-services` submodule pointer.

**Never**

- Hand-edit a generated file (see the table above).
- Make a check pass by weakening it: deleting or skipping tests, loosening `filterwarnings`, lowering the coverage target, or adding blanket ignores.
- Commit secrets. The credentials under `tests/system_tests/` are dummy values for local containers and must stay that way. gitleaks runs in pre-commit.
- Write a test that connects to real EPICS or hardware. Use mock or simulated devices, as in `tests/unit_tests/core/fake_device_module.py`.
- Push tags, publish releases or force-push `main`.

## Glossary

- **Plan / stub:** a plan is a complete experiment procedure that opens and closes a run. A stub is a fragment. Both are generator functions yielding bluesky `Msg` objects.
- **Device:** an object implementing bluesky protocols such as `Movable` or `Readable`, normally an ophyd-async device.
- **Task:** one request to run a named plan with parameters. A task is submitted first and started second, or done in one step over the WebSocket.
- **Instrument session:** a DLS visit identifier such as `cm12345-1` (proposal `cm12345`, visit `1`), parsed by `INSTRUMENT_SESSION_RE` in `blueapi/utils`.
- **dodal:** the DLS library of device definitions and common plans. The system tests use its `adsim` beamline.
- **numtracker:** a DLS GraphQL service that issues scan numbers and data directories.
- **Tiled:** the data access service that run documents are written to.
- **OPA:** Open Policy Agent, which makes authorization decisions.
- **Scratch area:** a directory of editable checkouts of plan repositories, set up by `blueapi setup-scratch` so that plans can be edited on a live beamline.

## Direction of travel

This is a snapshot from November 2026. Check an issue with `gh issue view <number>` before relying on it. The aim is to stop you building against the grain.

- **Client and server are being separated** (#1414). Keep the client thin and put server-only code under `blueapi/service/`.
- **WebSocket `run_plan` is the intended replacement** for the submit, start and listen-on-STOMP flow (#1326). STOMP remains supported and in use by other services.
- **Plan argument handling may be redesigned** (#1624). Avoid large investments in the current model-building code in `core/context.py`.
- **Device naming and child devices are in flux** (#1700, #1723, #1726, #1671).
- **Running blueapi as a library** that a beamline application imports is under consideration (#1533).
- **Pause and resume are not properly supported** (#1420). Do not assume they work end to end.
- **A 2.0 release will remove deprecated names** (#1256, #1257). Until then, deprecate and do not delete.
