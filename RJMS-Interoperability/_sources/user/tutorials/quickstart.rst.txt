Quickstart Guide
================

.. seealso:: Assumes you have completed `./installation`.


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


.. seealso:: Full CLI reference: `../reference/cli`
