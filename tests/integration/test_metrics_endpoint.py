#!/usr/bin/env python3
# Copyright 2021 Canonical Ltd.
# See LICENSE file for licensing details.
import jubilant
import pytest
from helpers import Prometheus


@pytest.mark.abort_on_fail
def test_avalanche_is_scraped_by_prometheus(juju: jubilant.Juju, charm, charm_resources):
    """Deploy avalanche and Prometheus, relate them, and verify metrics land in Prometheus."""
    juju.deploy(charm, "avalanche", resources=charm_resources)
    juju.deploy("prometheus-k8s", "prometheus", channel="2/edge", trust=True)
    juju.integrate("avalanche:metrics-endpoint", "prometheus:metrics-endpoint")
    juju.wait(jubilant.all_active)

    # Verify the scrape target is up
    prometheus_url = juju.status().apps["prometheus"].units["prometheus/0"].address
    prometheus = Prometheus(url=prometheus_url)
    assert prometheus.has_metric(name="up", labels={"juju_application": "avalanche"})
    assert prometheus.has_metric(name=".*", labels={"juju_application": "avalanche"})
