from .test_templates import *
from blueapi.messaging import AMQPMessagingTemplate, MessagingTemplate
from blueapi.config import AMQPConfig


@pytest.fixture
def disconnected_template() -> MessagingTemplate:
    return AMQPMessagingTemplate.autoconfigured(AMQPConfig())


@pytest.mark.amqp
def test_amqp_send(template: MessagingTemplate, test_queue: str) -> None:
    send(template, test_queue)


@pytest.mark.amqp
def test_amqp_send_to_topic(template: MessagingTemplate, test_topic: str) -> None:
    send_to_topic(template, test_topic)


@pytest.mark.amqp
def test_amqp_send_on_reply(template: MessagingTemplate, test_queue: str) -> None:
    send_on_reply(template, test_queue)


@pytest.mark.amqp
def test_amqp_send_and_recieve(template: MessagingTemplate, test_queue: str) -> None:
    send_and_recieve(template, test_queue)


@pytest.mark.amqp
def test_amqp_listener(template: MessagingTemplate, test_queue: str) -> None:
    listener(template, test_queue)


@pytest.mark.amqp
@pytest.mark.parametrize(
    "message,message_type",
    [("test", str), (1, int), (Foo(1, "test"), Foo)],
)
def test_amqp_deserialization(
    template: MessagingTemplate, test_queue: str, message: Any, message_type: Type
) -> None:
    deserialization(template, test_queue, message, message_type)


@pytest.mark.amqp
def test_amqp_subscribe_before_connect(
    disconnected_template: MessagingTemplate, test_queue: str
) -> None:
    subscribe_before_connect(disconnected_template, test_queue)


@pytest.mark.amqp
def test_amqp_reconnect(template: MessagingTemplate, test_queue: str) -> None:
    reconnect(template, test_queue)


@pytest.mark.amqp
def test_amqp_correlation_id(
    template: MessagingTemplate, test_queue: str, test_queue_2: str
) -> None:
    correlation_id(template, test_queue, test_queue_2)
