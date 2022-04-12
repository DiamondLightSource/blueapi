from dataclasses import dataclass
from typing import Optional


@dataclass
class MessageContext:
    destination: str
    reply_destination: Optional[str]

    def can_reply(self) -> bool:
        return self.reply_destination is not None
