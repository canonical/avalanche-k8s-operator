#!/usr/bin/env python3
# Copyright 2021 Canonical Ltd.
# See LICENSE file for licensing details.
import jubilant
import pytest
from helpers import assert_metrics_found


@pytest.mark.abort_on_fail
def test_avalanche_is_scraped_by_prometheus(juju: jubilant.Juju, charm, charm_resources):
    """Deploy avalanche and Prometheus, relate them, and verify metrics land in Prometheus."""
    juju.deploy(charm, "avalanche", resources=charm_resources)
    juju.deploy("prometheus-k8s", "prometheus", channel="2/edge", trust=True)
    juju.integrate("avalanche:metrics-endpoint", "prometheus:metrics-endpoint")
    juju.wait(jubilant.all_active)

    # Verify the scrape target is up
    result = assert_metrics_found(
        juju, 'up{juju_application="avalanche"}', timeout=300
    )
    assert any(
        sample["value"][1] == "1" for sample in result
    ), f"Expected 'up' metric to be 1 for avalanche, got: {result}"

    # Verify actual avalanche-generated metrics are present
    assert_metrics_found(juju, '{juju_application="avalanche", __name__=~".+"}', timeout=60)
