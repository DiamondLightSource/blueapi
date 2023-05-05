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

The tests for stomp require connection to a live ActiveMQ broker and will fail
if one is not present. This can be inconvenient if you wish to test changes 
that are unrelated to the broker, you can avoid this with::

    $ tox -e pytest -- --skip-stomp

The stomp tests are still run against a live broker in CI to ensure nothing
slips through the cracks.