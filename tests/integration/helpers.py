# Copyright 2021 Canonical Ltd.
# See LICENSE file for licensing details.

import json
import logging
import urllib.parse

import jubilant
from tenacity import (
    before_sleep_log,
    retry,
    retry_if_exception_type,
    retry_if_result,
    stop_after_delay,
    wait_fixed,
)

log = logging.getLogger(__name__)

PROMETHEUS_PORT = 9090


def query_prometheus(juju: jubilant.Juju, promql: str, prometheus_unit: str) -> list:
    """Run an instant PromQL query against Prometheus via juju exec and return the result list."""
    encoded = urllib.parse.quote(promql)
    url = f"http://localhost:{PROMETHEUS_PORT}/api/v1/query?query={encoded}"
    task = juju.exec(f"curl -sS '{url}'", unit=prometheus_unit)
    data = json.loads(task.stdout)
    assert data["status"] == "success", f"Prometheus query failed: {data}"
    return data["data"]["result"]


def assert_metrics_found(
    juju: jubilant.Juju,
    promql: str,
    *,
    prometheus_app: str = "prometheus",
    timeout: int = 300,
    interval: int = 15,
) -> list:
    """Poll Prometheus until the given PromQL query returns at least one result.

    Raises AssertionError if no results are found within the timeout.
    """
    prometheus_unit = f"{prometheus_app}/0"
    log.info("Polling Prometheus at %s for query: %s", prometheus_unit, promql)

    @retry(
        retry=retry_if_result(lambda result: not result) | retry_if_exception_type(Exception),
        stop=stop_after_delay(timeout),
        wait=wait_fixed(interval),
        before_sleep=before_sleep_log(log, logging.DEBUG),
        retry_error_callback=lambda retry_state: (
            retry_state.outcome.result()  # type: ignore[union-attr]
            if not retry_state.outcome.failed  # type: ignore[union-attr]
            else []
        ),
    )
    def _poll() -> list:
        return query_prometheus(juju, promql, prometheus_unit)

    result = _poll()
    if not result:
        raise AssertionError(
            f"Timed out after {timeout}s waiting for Prometheus results for query: {promql}. "
            f"Last result: {result}"
        )
    log.info("Prometheus returned %d result(s) for: %s", len(result), promql)
    return result
