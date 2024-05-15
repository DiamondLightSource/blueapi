Quickstart Guide
================

.. seealso:: Assumes you have completed `./installation`.

Blueapi acts as a worker that can run bluesky plans against devices for a specific
laboratory setup. It can control devices to collect data and export events to tell
downstream services about the data it has collected.


Start ActiveMQ
--------------

The worker requires a running instance of ActiveMQ, the simplest
way to start it is to run it via a container:

.. tab-set::

    .. tab-item:: Docker

        .. code:: shell

            docker run -it --rm --net host rmohr/activemq:5.15.9-alpine

    .. tab-item:: Podman

        .. code:: shell

            podman run -it --rm --net host rmohr/activemq:5.15.9-alpine


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
