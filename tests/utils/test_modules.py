from importlib import import_module

import pytest

from blueapi.utils import load_module_all


def test_imports_all():
    module = import_module(".hasall", package="utils")

    assert list(load_module_all(module)) == ["hello", 9]


def test_rejects_module_without_all():
    module = import_module(".lacksall", package="utils")

    with pytest.raises(TypeError):
        next(load_module_all(module))
