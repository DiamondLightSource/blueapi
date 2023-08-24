Use a Message Bus to Access Event Data
======================================

Blueapi generates a number of events documenting the worker's actions and data recorded.
It can be configured to propagate these onto a message bus for downstream applications 
to listen to.

.. seealso:: `../reference/messaging-spec` For full event specification

The events are essential for making use of the data recorded by blueapi, so if you plan to use for more than actuation, this is a necessary step.

Configuration
-------------

.. seealso:: `./configure-app`

Blueapi currently supports ActiveMQ and RabbitMQ with their respective STOMP plugins enabled.
The following config will make it communicate with a message bus on localhost.

.. code:: yaml

    # For ActiveMQ
    stomp:
      host: localhost
      port: 61613

    # For RabbitMQ
    stomp:
      host: localhost
      port: 61613
      auth:
        username: admin
        passcode: admin


Start ActiveMQ
--------------

The simplest message bus to setup for development purposes is ActiveMQ in a container.

.. tab-set::

    .. tab-item:: Docker

        .. code:: shell

            docker run -it --rm --net host rmohr/activemq:5.15.9-alpine

    .. tab-item:: Podman

        .. code:: shell

            podman run -it --rm --net host rmohr/activemq:5.15.9-alpine


Use With the CLI 
----------------

.. seealso:: `./run-cli`

The CLI can be pointed at the same configuration as the worker and talk via the same message bus.
It will then track events from running a plan and provide output.

.. code:: shell

    blueapi -c path/to/config.yaml run count '{"detectors": ["<NAME OF DETECTOR>"]}'

