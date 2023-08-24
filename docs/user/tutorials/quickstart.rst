Quickstart Guide
================

.. seealso:: Assumes you have completed `./installation`.

Blueapi acts as a worker that can run bluesky plans against devices for a specific
laboratory setup. It can control devices to collect data and export events to tell
downstream services about the data it has collected.


Start Worker
------------

To start the worker:

.. code:: shell

    blueapi serve


The worker can also be started using a custom config file:

.. code:: shell

    blueapi --config path/to/file serve


Test that the Worker is Running
-------------------------------

Blueapi comes with a CLI so that you can query and control the worker from the terminal.

.. code:: shell

    blueapi controller plans

The above command should display all plans the worker is capable of running.

.. seealso:: Full CLI reference: `../reference/cli`
