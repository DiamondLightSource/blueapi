from blueapi.utils import BlueapiBaseModel


class FooBar(BlueapiBaseModel):
    hello: str = "hello"
    hello_world: str = "hello world"


def test_snake_case_constructor() -> None:
    FooBar(
        hello="hello",
        hello_world="hello world",
    )


def test_camel_case_parsing() -> None:
    assert FooBar.parse_obj(
        {
            "hello": "hello",
            "helloWorld": "hello world",
        }
    ) == FooBar(
        hello="hello",
        hello_world="hello world",
    )
