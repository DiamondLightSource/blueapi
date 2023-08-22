Add Plans and Devices to your Blueapi Environment
=================================================

Custom plans and devices, tailored to individual experimental environments, can be added via configuration. In both cases the relevant code must be in your Python path, for example, part of a library installed in your Python environment. For editing and tweaking you can use an editable install, see below.

Home of Code
------------

The code can be in any pip-installable package, such as:

* A package on pypi
* A Github repository
* A local directory with a ``pyproject.toml`` file or similar.

The easiest place to put the code is a repository created with the `python skeleton`_. Which can then become any of the above.

For development purposes this code should be installed into your environment with 

.. code:: shell

  pip install -e path/to/package

Format
------

Plans in Python files look like this:

.. note:: The type annotations (e.g. ``: str``, ``: int``, ``-> MsgGenerator``) are required as blueapi uses them to generate an API!

You can define as many plans as you like in a single Python file or spread them over multiple files.

.. code:: python

    from bluesky.protocols import Readable, Movable
    from blueapi.core import MsgGenerator
    from typing import Mapping, Any

    def my_plan(
        detector: Readable, 
        motor: Movable, 
        steps: int, 
        sample_name: str, 
        extra_metadata: Mapping[str, Any]) -> MsgGenerator:
        
        # logic goes here
        ...


Devices are made using the dodal_ style available through factory functions like this:

.. note:: The return type annotation ``-> MyTypeOfDetector`` is required as blueapi uses it to determine that this function creates a device. Meaning you can have a Python file where only some functions create devices and they will be automatically picked up.

Similarly, these functions can be organized per-preference into files.

.. code:: python

    from my_facility_devices import MyTypeOfDetector

    def my_detector(name: str) -> MyTypeOfDetector:
        return MyTypeOfDetector(name, {"other_config": "foo"})


.. seealso:: dodal_ for many more examples

An extra function to create the device is used to preserve side-effect-free imports. Each device must have its own factory function.


Configuration
-------------

.. seealso:: `./configure-app`

First determine the import path of your code. If you were going to import it in a Python file, what would you put?
For example:

.. code:: python

    import my_plan_library.tomography.plans

You would add the following into your configuration file:

.. code:: yaml

    env:
      sources:
        - kind: dodal
          # note, this code does not have to be inside dodal just because it uses
          # the dodal kind. The module referenced contains a dodal-style function
          # for initializing a particular device e.g. MyTypeOfDetector in my_lab.
          module: dodal.my_beamline  
        - kind: planFunctions
          module: my_plan_library.tomography.plans


You can have as many sources for plans and devices as are needed.


.. _dodal: https://github.com/DiamondLightSource/dodal
.. _`python skeleton`: https://diamondlightsource.github.io/python3-pip-skeleton/main/index.html
