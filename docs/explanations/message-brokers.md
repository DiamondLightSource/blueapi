# Message Brokers

Blueapi uses a message broker to communicate with downstream services such as the Nexus Filewriter, and tools such as the Blueapi CLI client. Blueapi is broker agnostic, communicating in STOMP via the [bluesky-stomp](https://github.com/DiamondLightSource/bluesky-stomp) library. However, RabbitMQ is most commonly used in DLS deployments.

## Messages

When a plan is run, Blueapi broadcasts all worker events, progress events and data events to the configured message broker. Some example messages can be seen below. These are the messages sent to RabbitMQ during a `sleep` plan (printed with an `[x]` at the start):
```
 [x] public.worker.event:b'{"state":"RUNNING","task_status":{"task_id":"ebef36e4-47bf-4145-855d-15e343a26424","result":null,"task_complete":false,"task_failed":false},"errors":[],"warnings":[]}'
 [x] public.worker.event:b'{"state":"IDLE","task_status":{"task_id":"ebef36e4-47bf-4145-855d-15e343a26424","result":null,"task_complete":false,"task_failed":false},"errors":[],"warnings":[]}'
 [x] public.worker.event:b'{"state":"IDLE","task_status":{"task_id":"ebef36e4-47bf-4145-855d-15e343a26424","result":{"outcome":"success","result":null,"type":"NoneType"},"task_complete":true,"task_failed":false},"errors":[],"warnings":[]}'
 [x] public.worker.event:b'{"state":"RUNNING","task_status":{"task_id":"a3c51955-943b-4099-85f5-8263a6c02c53","result":null,"task_complete":false,"task_failed":false},"errors":[],"warnings":[]}'
 [x] public.worker.event:b'{"state":"IDLE","task_status":{"task_id":"a3c51955-943b-4099-85f5-8263a6c02c53","result":null,"task_complete":false,"task_failed":false},"errors":[],"warnings":[]}'
 [x] public.worker.event:b'{"state":"IDLE","task_status":{"task_id":"a3c51955-943b-4099-85f5-8263a6c02c53","result":{"outcome":"success","result":null,"type":"NoneType"},"task_complete":true,"task_failed":false},"errors":[],"warnings":[]}'
```

## Topology
The topology of the message broker is entirely deployment-specific. Nonetheless, the following details how deployments at DLS are generally structured.


RabbitMQ receives messages from Blueapi via its default topic exchange, `amq.topic`. All messages have the routing key `public.worker.event`, so will be forwarded to all queues bound to `amq.topic` with a compatible routing key (eg. `public.worker.event`, `*.*.event` etc.).

No default queues exist, meaning that if no downstream services have registered a queue, all messages will be dropped.

In RabbitMQ, different queues can have the same routing key, and consequently receive a copy of the same messages without interfering with each other. In Blueapi a common pair of queues to have is `public.worker.event.nexus` and `stomp-subscription-{random GUID}`, both bound to the `amq.topic` exchange with routing key `public.worker.event`. The prior is for the Nexus Filewriter, and the latter the Blueapi CLI client. In this case both have access to all messages published by Blueapi, but due to automatically declaring seperate queues at subscription, each consumer's message consumption will not deprive the other.


## Blueapi Messaging Mechanism

When Blueapi starts up, a `StompClient` is instantiated which registers a callback to each event stream (worker, progress and data). When an event occurs, it will be sent to the broker's default topic exchange with the routing key `public.worker.event`. In RabbitMQ, the default topic exchange is `amq.topic`.


## Subscribing to Blueapi Messages

When Blueapi is configured to use a message broker, services can subscribe to the broker to receive events generated during plan execution. In general, having services subscribe directly to the message broker is not recommended, as there should be a more appropriate way to access the information you want.

Due to the dynamic nature of RabbitMQ, new services can subscribe to the exchange at any point, without reconfiguring the server or interfering with other consumer's subscriptions.

To to connect a consumer to a RabbitMQ topic, follow RabbitMQ's [Tutorial 5: Topics](https://www.rabbitmq.com/tutorials) in your preferred language. Change the exchange name to `amq.topic` and the routing key to `public.worker.event`.

The consumer created in this tutorial will capture all messages generated during its runtime. It will not have access to messages that were generated previously. If this is a requirement for your use-case, RabbitMQ can be reconfigured to generate specific queues at startup. This can be achieved through [schema definitions](https://www.rabbitmq.com/docs/definitions).

## Tips

It is important to remember that while all queues are guaranteed to receive the same set of messages, there is no guarantee that each queue has consumed their messages.

For example, a service listening for a Stop document to kick off data analysis may consume events faster than a file writing service, which needs to write each event to disk. Receiving a Stop document would then only guarantee that Blueapi has completed the plan, not that the data is written to disk and ready for analysis.

The only guarantee we make is that all queues will receive all events in the correct order.
