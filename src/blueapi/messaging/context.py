from dataclasses import dataclass
from typing import Optional


@dataclass
class MessageContext:
    """
    Context that comes with a message, provides useful information such as how to reply
    """

    destination: str
    reply_destination: Optional[str]
    task_id: Optional[str]
