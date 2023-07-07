Run the tests using pytest
==========================

Testing is done with pytest_. It will find functions in the project that `look
like tests`_, and run them to check for errors. You can run it with::

    $ tox -e pytest

It will also report coverage to the commandline and to ``cov.xml``.

.. _pytest: https://pytest.org/
.. _look like tests: https://docs.pytest.org/explanation/goodpractices.html#test-discovery


Skip the message bus tests
--------------------------

The tests for stomp require connection to a live broker and will fail
if one is not present. This can be inconvenient if you wish to test changes
that are unrelated to the broker, you can avoid this with::

    $ tox -e pytest -- --skip-stomp

The stomp tests are still run against a live broker in CI to ensure nothing
slips through the cracks.

Configure message busses
------------------------

The tests for communicating with a message bus over stomp support either ActiveMQ or RabbitMQ
with the ```rabbitmq_stomp``` plugin installed. The tests assume that such a broker is available
on ```localhost:61613```: if you require a different host or port, edit StompConfig in config.py
or set the ```BLUEAPI_TEST_STOMP_PORTS``` environment variable: this variable is a list of values
so the tests can be run against multiple brokers::

    # Default behaviour
    $ export BLUEAPI_TEST_STOMP_PORTS="[61613]"

    # Broker is running on a different port
    $ export BLUEAPI_TEST_STOMP_PORTS="[61614]"

    # Multiple brokers are running on multiple ports, the tests will be run once per broker
    $ export BLUEAPI_TEST_STOMP_PORTS="[61613, 61614]"

ActiveMQ:
For testing and development purposes, the outdated and unmaintained ActiveMQ community image is sufficient
if you do  not already have an ActiveMQ installation, but it is **not recommended** for deployment or long term use.

Running the ActiveMQ container image with stomp port 61613 and management port 8161 forwarded to localhost::

    $ docker run -p 61613:61613 -p 8161:8161 rmohr/activemq

RabbitMQ:
As the RabbitMQ container image is actively maintained and packaged into a Helm chart, this is the recommended
message bus for active deployments. For testing and deployment it does require that the ```rabbitmq_stomp```
plugin is enabled, and that StompConfig in config.py has Authentication enabled.

Running the RabbitMQ container image with stomp port 61613 and management port 15672 forwarded::

    $ docker run -p 61613:61613 -p 15672:15672 --name rabbitmq rabbitmq/management

Enabling the rabbitmq_stomp plugin::

    $ docker exec rabbitmq rabbitmq-plugins enable rabbitmq_stomp

