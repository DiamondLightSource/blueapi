from dataclasses import dataclass


@dataclass
class MessageContext:
    """
    Context that comes with a message, provides useful information such as how to reply
    """

    destination: str
    reply_destination: str | None
    correlation_id: str | None
