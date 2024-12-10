from collections.abc import Mapping
from dataclasses import dataclass
from pprint import pprint
from typing import Any

import h5py as h5
import numpy as np


@dataclass
class ExpectedDataset:
    shape: tuple[int, ...]
    value: np.ndarray | None = None


def validate_data(
    actual_data: h5.HLObject,
    expected: ExpectedDataset | Mapping[str, Any],
    total: bool = False,
) -> None:
    print(f"Validating {actual_data} against the following tree:")
    pprint(expected)

    if isinstance(expected, dict):
        if total:
            assert set(expected.keys()) == set(actual_data.keys())  # type: ignore
        else:
            assert set(expected.keys()).issubset(set(actual_data.keys()))  # type: ignore
        for name, dataset_or_group in actual_data.items():  # type: ignore
            child = expected.get(name)
            if name is not None:
                validate_data(dataset_or_group, child)  # type: ignore
            elif total:
                raise AssertionError(
                    f"{actual_data} has a child called {name} that is not expected"
                )
    elif isinstance(expected, ExpectedDataset):
        name = actual_data.name
        _assert_is_dataset(actual_data, expected)
        assert (
            actual_data.shape == expected.shape  # type: ignore
        ), f"{name}: {actual_data.shape} should be {expected.shape}"  # type: ignore
        if expected.value is not None:
            arr = np.array(actual_data)
            assert np.equal(
                arr, expected.value
            ), f"{name}: {arr} should be {expected.value}"


def _assert_is_dataset(
    maybe_dataset: h5.HLObject, expected_dataset: ExpectedDataset
) -> None:
    valid_types = [h5.Dataset]
    name = maybe_dataset.name
    for t in valid_types:
        if isinstance(maybe_dataset, t):
            return
    raise AssertionError(
        f"{maybe_dataset} of type {type(maybe_dataset)} is"
        f" not one of the valid dataset types: {valid_types}."
        f" The following was expected: {name}: {expected_dataset}"
    )
