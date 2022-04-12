from dataclasses import dataclass
from typing import Optional


@dataclass
class MessageContext:
    destination: str
    reply_destination: Optional[str]
