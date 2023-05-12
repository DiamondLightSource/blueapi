ActiveMQ Specification
======================

The blueapi worker publishes bluesky documents onto activemq, such that it can
keep track of the status of plans and to provide an easy way for external
services to listen to events. This page documents all the possible topics that
can be listened to by a client.

.. literalinclude:: ./asyncapi.yaml
   :language: yaml
