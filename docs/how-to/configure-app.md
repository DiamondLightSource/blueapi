# Configure the Application

Blueapi's default configuration can be overridden
by defining a yaml file which can be passed to the `blueapi` command.

To set your own application configuration create a file and pass it to the CLI:

```
blueapi --config path/to/file.yaml <subcommand>
```

It is also possible to specify the config file via an environment variable to
avoid it having to be passed to every time the cli is used:

```
export BLUEAPI_CONFIG=/path/to/file.yaml
blueapi <subcommand>
```
