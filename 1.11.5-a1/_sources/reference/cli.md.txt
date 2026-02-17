# Command-Line Interface

Full reference for the CLI:

Options for each command can also be set via environment variables to avoid them
having to be set for every call. The variable to set should be `BLUEAPI`
followed by the name of each subcommand, and then the name of the option all
made upper-case and joined with underscores. For example, to set the `--output`
option to the `controller` subcommand to 'full', you would need to set the
environment variable `BLUEAPI_CONTROLLER_OUTPUT=full`.

```{eval-rst}
.. click:: blueapi.cli:main
   :prog: blueapi
   :show-nested:
```
