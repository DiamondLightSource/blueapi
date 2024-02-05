Configure the application
=========================

By default, configuration options are ingested from pydantic BaseModels,
however the option exists to override these by defining a yaml file which
can be passed to the ``blueapi`` command.

An example of this yaml file is found in ``config/defaults.yaml``, which follows
the schema defined in ``src/blueapi/config.py`` in the ``ApplicationConfig`` 
object.

To set your own application configuration, edit this file (or write your own)
and simply pass it to the CLI by typing::

    $ blueapi --config path/to/file.yaml

where ``path/to/file.yaml`` is the relative path to the configuration file you
wish to use.

Note: child commands
--------------------
Configuration options need to be passed down to child commands. For example,
if you start the server with::
    $ blueapi --config path/to/file.yaml

And then use the CLI to discover the devices with::
    $ blueapi controller devices

The configuration for the second command will be different to the first. You
must supply the correct configuration in this case::
    $ blueapi --config path/to/file.yaml controller devices
