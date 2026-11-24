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


def test_prints_message_and_traceback_to_stderr(capsys):
    should_error()
    out, err = capsys.readouterr()
    assert out == ""
    assert err.startswith("Exception in thread: Test exception\n")
    assert "Traceback (most recent call last)" in err
    assert 'raise ValueError("Test exception")' in err


def test_custom_callback_receives_exception():
    def raises():
        raise ValueError("Test exception")

    errors: list[Exception] = []
    wrapped = handle_all_exceptions(raises, errors.append)
    assert wrapped() is None
    assert [str(e) for e in errors] == ["Test exception"]
