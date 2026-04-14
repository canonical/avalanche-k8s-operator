# Copyright 2021 Canonical Ltd.
# See LICENSE file for licensing details.

import json
import logging
import urllib.parse
import urllib.request

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


def get_prometheus_unit_address(juju: jubilant.Juju, app_name: str = "prometheus") -> str:
    """Return the IP address of the first unit of the Prometheus application."""
    status = juju.status()
    units = status.apps[app_name].units
    unit = next(iter(units.values()))
    return unit.address


def query_prometheus(address: str, promql: str) -> list:
    """Run an instant PromQL query against Prometheus and return the result list."""
    url = f"http://{address}:{PROMETHEUS_PORT}/api/v1/query?query={urllib.parse.quote(promql)}"
    with urllib.request.urlopen(url, timeout=10) as response:
        data = json.loads(response.read().decode())
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
    address = get_prometheus_unit_address(juju, prometheus_app)
    log.info("Polling Prometheus at %s for query: %s", address, promql)

    @retry(
        retry=retry_if_result(lambda result: not result) | retry_if_exception_type(Exception),
        stop=stop_after_delay(timeout),
        wait=wait_fixed(interval),
        before_sleep=before_sleep_log(log, logging.DEBUG),
        retry_error_callback=lambda retry_state: (
            retry_state.outcome.result() if not retry_state.outcome.failed else []
        ),
    )
    def _poll() -> list:
        return query_prometheus(address, promql)

    result = _poll()
    if not result:
        raise AssertionError(
            f"Timed out after {timeout}s waiting for Prometheus results for query: {promql}. "
            f"Last result: {result}"
        )
    log.info("Prometheus returned %d result(s) for: %s", len(result), promql)
    return result
