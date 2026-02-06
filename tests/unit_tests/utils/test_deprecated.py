import warnings

import pytest

from blueapi.utils import deprecated


def test_deprecated_annotation():
    @deprecated("bar")
    def foo():
        return 1

    with pytest.warns(DeprecationWarning, match="Function foo is deprecated - use bar"):
        assert foo() == 1

    # The second time a function is called, the warning should not be raised
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        assert foo() == 1
