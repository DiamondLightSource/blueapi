import json
from typing import Tuple
from unittest.mock import MagicMock

from blueapi.messaging import MessagingTemplate, StompMessagingTemplate


def test_send() -> None:
    template, conn = _mock_template()
    template.send("test", "test_message")
    conn.send.assert_called_once_with(
        body=json.dumps("test_message"),
        destination="test",
        headers={},
    )


def _mock_template() -> Tuple[MessagingTemplate, MagicMock]:
    conn = MagicMock()
    return StompMessagingTemplate(conn), conn
