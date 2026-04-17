#!/usr/bin/env python3
# Copyright 2021 Canonical Ltd.
# See LICENSE file for licensing details.
import jubilant
import pytest
from helpers import Prometheus


@pytest.mark.abort_on_fail
def test_avalanche_remote_writes_to_prometheus(juju: jubilant.Juju, charm, charm_resources):
    """Deploy avalanche and Prometheus, relate via remote-write, and verify metrics land."""
    juju.deploy(charm, "avalanche", resources=charm_resources)
    juju.deploy("prometheus-k8s", "prometheus", channel="2/edge", trust=True)
    juju.integrate("avalanche:send-remote-write", "prometheus:receive-remote-write")
    juju.wait(jubilant.all_active)

    prometheus_address = juju.status().apps["prometheus"].units["prometheus/0"].address
    prometheus_url = f"http://{prometheus_address}:9090"
    prometheus = Prometheus(url=prometheus_url)
    # Remote-written metrics won't have an 'up' target, so query for avalanche-generated metrics
    # directly. Avalanche metric names are auto-generated with the configured metricname_length.
    assert prometheus.has_metric(labels={"juju_application": "avalanche"})
