from unittest.mock import patch

from blueapi.utils import handle_all_exceptions


@handle_all_exceptions
def shouldnt_error(): ...


@handle_all_exceptions
def shouldnt_error_with_args(foo: int, bar: int):
    return foo + bar


@handle_all_exceptions
def should_error():
    raise ValueError("Test exception")


def test_no_print_if_no_errors():
    with patch("builtins.print") as mock_print:
        shouldnt_error()
        mock_print.assert_not_called()


def test_prints_errors():
    with patch("builtins.print") as mock_print:
        should_error()
        mock_print.assert_called()


def test_passes_args_and_kwargs():
    assert shouldnt_error_with_args(2, bar=3) == 5
