Run in a Developer Environment 
==============================

Assuming you have setup a developer environment, you can run
a developement version of the bluesky worker.

.. seealso:: `./dev-install`

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


Start Bluesky Worker
--------------------

Ensure you are inside your virtual environment:

.. code:: shell

    source venv/bin/activate

Start the worker from the command line or vscode:

.. tab-set::

    .. tab-item:: Command line

        .. code:: shell

            blueapi worker

    .. tab-item:: VSCode

        1. Navigate to "Run and Debug" in the left hand menu.
        2. Select "Worker Service" from the debug configuration.
        3. Click the green "Run Button"

        .. figure:: ../../images/debug-vscode.png
          :align: center

          debug in vscode
