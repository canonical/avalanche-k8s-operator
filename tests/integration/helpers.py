# Copyright 2021 Canonical Ltd.
# See LICENSE file for licensing details.

import json
import logging
import time
import urllib.parse
import urllib.request

import jubilant

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

    deadline = time.time() + timeout
    last_result: list = []
    while time.time() < deadline:
        try:
            last_result = query_prometheus(address, promql)
            if last_result:
                log.info("Prometheus returned %d result(s) for: %s", len(last_result), promql)
                return last_result
        except Exception as e:
            log.debug("Prometheus query attempt failed: %s", e)
        time.sleep(interval)

    raise AssertionError(
        f"Timed out after {timeout}s waiting for Prometheus results for query: {promql}. "
        f"Last result: {last_result}"
    )
