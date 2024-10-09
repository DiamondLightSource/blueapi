from typing import Any, LiteralString


def format_errors(errors: list[Any]) -> LiteralString:
    formatted_errors: list[LiteralString] = []
    for error in errors:
        loc = " -> ".join(
            map(str, error["loc"])
        )  # Create a string path for the location
        message = f"Type: {error['type']}, Location: {loc}, Message: {error['msg']}"
        if "input" in error:
            message += f", Input: {error['input']}"
        if "url" in error:
            message += f", Documentation: {error['url']}"
        formatted_errors.append(message)

    return "\n".join(formatted_errors)
