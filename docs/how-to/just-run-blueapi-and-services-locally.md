# Run BlueAPI and connect to services locally

For development purposes, it can be useful to run BlueAPI and adjacent services (Numtracker, Tiled, OPA etc.) locally, i.e. not in a devcontainer. Following the steps in this page will allow you to launch an instance of NumTracker, RabbitMQ, Keycloak, Tiled, OPA and a number of IOCs, in detached mode. This can be useful for learning about the stack, running system tests checking if changes during development propagate as expected etc. 

Before starting, ensure you have followed the [Installation instructions](../tutorials/1.%20installation.md).

1. Before starting, run: `module load uv just docker-compose/5.4.0`  in the terminal. This will ensure you have the required packages.

2. The default command `just` into the terminal will do the following:
    - A. initialise the example-services repo
    - B. launch an instance of NumTracker, RabbitMQ, Keycloak, Tiled, OPA and a number of IOCs in detached mode
    - C. set required EPICS environmental variables
    - D. start the BlueAPI server using the the config in `tests/system_tests/config.yaml`

3. To run the above separately use the following commands:
    - 2A and 2B: `just compose`
    - 2C and 2D: `just serve`

4. In a new terminal window, to run unit and system tests respectively: `just unit` and `just system`

5. Other commands available (use `just --list` to see them)
    - `just run PLAN PARAMS`: provide session, plan and parameter details to run a plan
    - `just lint`: will run all the precommit checks, update the BlueAPI schema, run pyright
    - `just coverage`: generate code coverage report
    - `just repl`: will give you a repl with pre-configured and logged in client
    - `just compose down`: tear down adjacent services

Channel Access

To log in through the BlueAPI CLI:

1. Run `blueapi login` (if you want to run a plan with stomp config, add the `-c tests/system_tests/config.yaml` parameter)
2. Follow the login prompted to Keycloak, then log in with the username `admin` and password `admin`
3. When prompted by Keycloak, grant BlueAPI access to the listed privileges
4. Run `blueapi controller plans` to check that the log in has succeeded

By default the BlueAPI instance will be available via the OAuth2 proxy at `localhost:4180`, and Tiled through its OAuth2 proxy at `localhost:4181`.
