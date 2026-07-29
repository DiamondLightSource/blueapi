from unittest.mock import Mock, patch

import pytest

from blueapi.metrics import TaskWorkerMetrics


def mock_task_worker_metrics_init(self):
    self._task_success_counter = Mock()
    self._task_failure_counter = Mock()
    self._task_duration_histogram = Mock()


@pytest.fixture()
def task_worker_metrics():
    """Replace metrics with Mocks, retain class methods"""
    with patch(
        "blueapi.metrics.TaskWorkerMetrics.__init__", new=mock_task_worker_metrics_init
    ):
        return TaskWorkerMetrics()


@pytest.mark.parametrize("success", (True, False))
def test_success_counter(success, task_worker_metrics):
    task_worker_metrics.observe_task("foo", success, 5.0)

    metric: Mock = task_worker_metrics._task_success_counter.labels().inc

    if success:
        metric.assert_called_once()
    else:
        metric.assert_not_called()


@pytest.mark.parametrize("success", (True, False))
def test_failure_counter(success, task_worker_metrics):
    task_worker_metrics.observe_task("foo", success, 5.0)

    metric: Mock = task_worker_metrics._task_failure_counter.labels().inc

    if not success:
        metric.assert_called_once()
    else:
        metric.assert_not_called()


@pytest.mark.parametrize("success", (True, False))
def test_histogram(success, task_worker_metrics):
    task_worker_metrics.observe_task("foo", success, 5.0)

    task_worker_metrics._task_duration_histogram.labels().observe.assert_called_once_with(
        5.0
    )
