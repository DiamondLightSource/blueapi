from importlib import import_module

from blueapi.utils import load_module_all


def test_imports_all():
    module = import_module(".hasall", package="tests.unit_tests.utils")
    assert list(load_module_all(module)) == ["hello", 9]


def test_imports_everything_without_all():
    module = import_module(".lacksall", package="tests.unit_tests.utils")
    assert list(load_module_all(module)) == [3, "hello", 9]
