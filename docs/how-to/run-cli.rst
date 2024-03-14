Control the Worker via the CLI
==============================

The worker comes with a minimal CLI client for basic control. It should be noted that this is 
a test/development/debugging tool and not meant for production!

.. seealso:: 
    You must have access to the ``blueapi`` command either via the container or pip installing.
    `./run-container` and `../tutorials/installation`


.. seealso:: 
    In a developer environment, the worker can also be run from vscode: `../tutorials/dev-run`.


Basic Introspection
-------------------

The worker can tell you which plans and devices are available via:

.. code:: shell

    blueapi controller plans
    blueapi controller devices

By default, the CLI will talk to the worker via a message broker on ``tcp://localhost:61613``,
but you can customize this.

.. code:: shell

    blueapi controller -h my.host -p 61614 plans

Running Plans
-------------

You can run a plan and pass arbitrary JSON parameters.

.. code:: shell

    # Run the sleep plan
    blueapi controller run sleep '{"time": 5.0}'

    # Run the count plan
    blueapi controller run count '{"detectors": ["current_det", "image_det"]}'

The command will block until the plan is finished and will forward error/status messages 
from the server.

.. seealso:: Full reference: `../reference/cli`
