# Run Auth Locally

BlueAPI can be secured using OIDC authenticaiton. For development it can be useful to run a containerised version of the OIDC stack, to serve a local instance of BlueAPI.

To run the stack:

1. In the root directory run `git submodule update --init --recursive` to initialise the example-services repo
2. Run `docker compose -f tests/system_tests/compose.yaml up -d` to launch an instance of NumTracker, RabbitMQ, Keycloak, Tiled, OPA and a number of IOCs, in detached mode
3. Run `source tests/system_tests/.env` which will set required EPICS environmental variables
4. Run `blueapi -c tests/system_tests/config.yaml serve` to launch BlueAPI configured to use the launched stack. This may take a while, as BlueAPI will attempt to connect to a number of devices via Channel Access

To log in through the BlueAPI CLI:

1. Run `blueapi -c tests/system_tests/config.yaml login`
2. Follow the login prompted to Keycloak, then log in with the username `admin` and password `admin`
3. When promped by Keycloak, grant BlueAPI access to the listed privileges
4. Run `blueapi controller plans` to check that the log in has succeeded
