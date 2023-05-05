blueapi
===========================

|code_ci| |docs_ci| |coverage| |pypi_version| |license|

Lightweight library for creating Bluesky-as-a-service applications. 

============== ==============================================================
PyPI           ``pip install blueapi``
Source code    https://github.com/DiamondLightSource/blueapi
Documentation  https://DiamondLightSource.github.io/blueapi
Releases       https://github.com/DiamondLightSource/blueapi/releases
============== ==============================================================

By default, configuration options are ingested from pydantic BaseModels,
however the option exists to override these by defining a yaml file which
can be passed to the `blueapi` command.

An example of this yaml file is found in `config/defaults.yaml`, which follows
the schema defined in `src/blueapi/config.py` in the `ApplicationConfig` 
object.

To set your own application configuration, edit this file (or write your own)
and simply pass it to the CLI by typing::

    $ blueapi --config path/to/file.yaml

where `path/to/file.yaml` is the relative path to the configuration file you
wish to use. Then, any subsequent calls to child commands of blueapi will
use this file.


TODO: Talk about automagic plan endpoints

.. |code_ci| image:: https://github.com/DiamondLightSource/blueapi/actions/workflows/code.yml/badge.svg?branch=main
    :target: https://github.com/DiamondLightSource/blueapi/actions/workflows/code.yml
    :alt: Code CI

.. |docs_ci| image:: https://github.com/DiamondLightSource/blueapi/actions/workflows/docs.yml/badge.svg?branch=main
    :target: https://github.com/DiamondLightSource/blueapi/actions/workflows/docs.yml
    :alt: Docs CI

.. |coverage| image:: https://codecov.io/gh/DiamondLightSource/blueapi/branch/main/graph/badge.svg
    :target: https://codecov.io/gh/DiamondLightSource/blueapi
    :alt: Test Coverage

.. |pypi_version| image:: https://img.shields.io/pypi/v/blueapi.svg
    :target: https://pypi.org/project/blueapi
    :alt: Latest PyPI version

.. |license| image:: https://img.shields.io/badge/License-Apache%202.0-blue.svg
    :target: https://opensource.org/licenses/Apache-2.0
    :alt: Apache License

..
    Anything below this line is used when viewing README.rst and will be replaced
    when included in index.rst

See https://DiamondLightSource.github.io/blueapi for more detailed documentation.
