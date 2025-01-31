from importlib import import_module

from blueapi.utils import is_sourced_from_module, load_module_all


def test_imports_all():
    module = import_module(".hasall", package="tests.unit_tests.utils")
    assert list(load_module_all(module)) == ["hello", 9]


def test_imports_everything_without_all():
    module = import_module(".lacksall", package="tests.unit_tests.utils")
    assert list(load_module_all(module)) == [3, "hello", 9]


def test_source_is_in_module():
    module = import_module(".functions_b", package="tests.unit_tests.utils")
    assert is_sourced_from_module(module.__dict__["c"], module)


def test_source_is_not_in_module():
    module = import_module(".functions_b", package="tests.unit_tests.utils")
    assert not is_sourced_from_module(module.__dict__["a"], module)


def test_source_check_on_non_function():
    module = import_module(".functions_b", package="tests.unit_tests.utils")
    assert not is_sourced_from_module(module.__dict__["e"], module)
