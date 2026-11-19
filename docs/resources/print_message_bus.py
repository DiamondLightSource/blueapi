"""Print every message blueapi publishes to the message bus (raw JSON).

Usage: uv run python docs/resources/print_message_bus.py [host] [port]
"""

import json
import sys
import time

from bluesky_stomp.messaging import MessageContext, StompClient
from bluesky_stomp.models import Broker, MessageTopic

host = sys.argv[1] if len(sys.argv) > 1 else "localhost"
port = int(sys.argv[2]) if len(sys.argv) > 2 else 61613


def on_message(body: object, context: MessageContext) -> None:
    print(f"--- {context.destination}", flush=True)
    print(json.dumps(body, indent=2, default=str), flush=True)


client = StompClient.for_broker(Broker(host=host, port=port))
client.connect()
# blueapi publishes worker, progress and bluesky document events to this topic
client.subscribe(MessageTopic(name="public.worker.event"), on_message)
try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    client.disconnect()
