# blueapi

Bluesky-as-a-service: wraps bluesky plans/devices in a FastAPI server, publishes
events over STOMP (RabbitMQ). Also usable as a client library/CLI. Python >=3.13.

## Layout

- `src/blueapi/cli/` – click CLI (`blueapi serve`, `controller`, `login`, `schema`, ...)
- `src/blueapi/client/` – `BlueapiClient` (REST + STOMP event bus); must work **without** the `server` extra
- `src/blueapi/service/` – FastAPI app (`main.py`), authn/authz, numtracker, `runner.py`
  (RunEngine lives in a **spawned subprocess**; main process holds the REST API)
- `src/blueapi/worker/` – `TaskWorker`, task lifecycle and worker events
- `src/blueapi/core/` – `BlueskyContext` (plan/device registry), bluesky types
- `src/blueapi/config.py` – `ApplicationConfig` (pydantic)
- `helm/blueapi/` – Helm chart; `example-services/` – git submodule for local services
- `docs/` – Sphinx (MyST); architecture notes in `docs/explanations/`

## Commands

Use `uv` for everything. Never `pip install` (denied in settings).

```sh
uv run pytest tests/unit_tests -n logical   # unit tests (just unit)
uv run pyright src tests                     # type check (tox -e type-checking)
uv run prek run --all-files                  # ruff, uv-sync, helm-docs, gitleaks...
just lint                                    # regen schemas + prek + pyright
just compose && just serve                   # local services + server (system test config)
just system                                  # system tests, needs `just compose` up
tox -e client-system-test                    # client tests with no server deps
```

pytest runs with `filterwarnings = error` and `--doctest-modules` over `docs src tests`,
so new warnings and broken doc examples fail the suite.

## Generated files — don't hand-edit (a hook blocks it)

| File | Regenerate with |
| --- | --- |
| `docs/reference/openapi.yaml` | `uv run blueapi schema -u` |
| `helm/blueapi/config_schema.json` | `uv run blueapi config-schema -u` |
| `helm/blueapi/values.schema.json` | `uv run prek run helm-schema --all-files` |
| `helm/blueapi/README.md` | edit `README.md.gotmpl` / `values.yaml` comments, then `uv run prek run helm-docs-built --all-files` |
| `uv.lock` | `uv add` / `uv remove` / `uv lock` |
| `src/blueapi/_version.py` | setuptools_scm, on install |

Change the REST API or `ApplicationConfig` → regenerate the matching schema in the same change.

## Conventions

- Ruff (line length 88; B, C4, E, F, N, W, I, UP, SLF, FAST). Private access allowed in tests only.
- Hooks auto-run `ruff check --fix` + `ruff format` after edits and pyright on Stop.
- Server-only deps go in the `server` extra; don't import them from `client/` or `cli/`
  paths used by the client.
- REST API is versioned (see `docs/explanations/api-version.md`).
- PR titles/commits: Conventional Commits (`feat:`, `fix:`, `chore(deps):` ...),
  enforced in CI; releases via release-please. Never `--no-verify`.
