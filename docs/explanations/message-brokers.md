# Message Brokers

Blueapi uses a message broker to communicate with certain downstream services such as the Nexus Filewriter, and tools such as the Blueapi CLI client. Blueapi is relatively broker agnostic, communicating via STOMP using the [bluesky-stomp](https://github.com/DiamondLightSource/bluesky-stomp) library. However, RabbitMQ is most commonly used in DLS deployments.

## Messages

When a plan is run, Blueapi broadcasts all worker events, progress events and data events to the configured message broker (see [Events Emitted by the Worker](events.md)). The example below are messages broadcast during a `sleep` plan:
``` sh
 [x] public.worker.event:b'{"state":"RUNNING","task_status":{"task_id":"ebef36e4-47bf-4145-855d-15e343a26424","result":null,"task_complete":false,"task_failed":false},"errors":[],"warnings":[]}'
 [x] public.worker.event:b'{"state":"IDLE","task_status":{"task_id":"ebef36e4-47bf-4145-855d-15e343a26424","result":null,"task_complete":false,"task_failed":false},"errors":[],"warnings":[]}'
 [x] public.worker.event:b'{"state":"IDLE","task_status":{"task_id":"ebef36e4-47bf-4145-855d-15e343a26424","result":{"outcome":"success","result":null,"type":"NoneType"},"task_complete":true,"task_failed":false},"errors":[],"warnings":[]}'
 [x] public.worker.event:b'{"state":"RUNNING","task_status":{"task_id":"a3c51955-943b-4099-85f5-8263a6c02c53","result":null,"task_complete":false,"task_failed":false},"errors":[],"warnings":[]}'
 [x] public.worker.event:b'{"state":"IDLE","task_status":{"task_id":"a3c51955-943b-4099-85f5-8263a6c02c53","result":null,"task_complete":false,"task_failed":false},"errors":[],"warnings":[]}'
 [x] public.worker.event:b'{"state":"IDLE","task_status":{"task_id":"a3c51955-943b-4099-85f5-8263a6c02c53","result":{"outcome":"success","result":null,"type":"NoneType"},"task_complete":true,"task_failed":false},"errors":[],"warnings":[]}'
```

## Topology
The topology of the message broker is decoupled from Blueapi, and entirely deployment-specific. Nonetheless, the following describe how deployments at DLS are generally structured.

RabbitMQ receives messages from Blueapi via its default topic exchange, `amq.topic`. All messages have the routing key `public.worker.event`, so will be forwarded to all queues bound to `amq.topic` with a compatible routing key (eg. `public.worker.event`, `*.*.event` etc.). No default queues exist, meaning that if no downstream services have registered a queue, all messages will be dropped.

In RabbitMQ, different queues can have the same routing key, and consequently receive a copy of the same messages without interfering with each other. In Blueapi a common pair of queues to have is `public.worker.event.nexus` and `stomp-subscription-{random GUID}`, both bound to the `amq.topic` exchange with routing key `public.worker.event`. The prior is for the Nexus Filewriter, and the latter the Blueapi CLI client. In this case both have access to all messages published by Blueapi, but due to automatically declaring seperate queues at subscription, each consumer's message consumption will not deprive the other.

## Subscribing to Blueapi Messages

When Blueapi is configured to use a message broker, any service can subscribe to the broker to receive events generated during plan execution. Due to the dynamic nature of RabbitMQ, new services can subscribe to the exchange at any point, without reconfiguring the server or interfering with other consumer's subscriptions. In general, having services subscribe directly to the message broker is not recommended, as there should be a more appropriate way to access the information you want.

To to connect a consumer to a RabbitMQ topic, follow RabbitMQ's [Tutorial 5: Topics](https://www.rabbitmq.com/tutorials) in your preferred language. Change the exchange name to `amq.topic` and the routing key to `public.worker.event`. For example:

``` python
#!/usr/bin/env python
import pika
import sys

connection = pika.BlockingConnection(
    pika.ConnectionParameters(host='localhost'))
channel = connection.channel()

channel.exchange_declare(exchange='amq.topic', exchange_type='topic', durable=True)

result = channel.queue_declare('', exclusive=True)
queue_name = result.method.queue

binding_keys = sys.argv[1:]
if not binding_keys:
    sys.stderr.write("Usage: %s [binding_key]...\n" % sys.argv[0])
    sys.exit(1)

for binding_key in binding_keys:
    channel.queue_bind(
        exchange='amq.topic', queue=queue_name, routing_key=binding_key)

print(' [*] Waiting for logs. To exit press CTRL+C')


def callback(ch, method, properties, body):
    print(f" [x] {method.routing_key}:{body}")


channel.basic_consume(
    queue=queue_name, on_message_callback=callback, auto_ack=True)

channel.start_consuming()
```

With this script and a local instance of RabbitMQ (see [Run BlueAPI and connect to services locally](../how-to/just-run-blueapi-and-services-locally.md)), the command `python ./client.py public.worker.event` will create a new queue bound to `amq.topic` with routing key `public.worker.event`. When a plan is run, this queue woud be populated with messages, which would in turn be consumed by and printed to console.


The consumer created in this tutorial will capture all messages generated during its runtime. It will not have access to messages that were generated previously. If this is a requirement for your use-case, RabbitMQ can be reconfigured to generate specific queues at startup. This can be achieved through [schema definitions](https://www.rabbitmq.com/docs/definitions).

## Tips

It is important to remember that while all queues are guaranteed to receive the same set of messages in the same order, there is no guarantee that each queue has consumed their messages.

For example, a service listening for a Stop document in order to kick off data analysis may consume events faster than a file writing service, which needs to write each event to disk. Receiving a Stop document would then only guarantee that Blueapi has completed the plan, not that the data is written to disk and ready to be used.
