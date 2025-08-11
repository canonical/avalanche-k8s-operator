#!/usr/bin/env python3
# Copyright 2021 Canonical Ltd.
# See LICENSE file for licensing details.
import jubilant
import pytest


@pytest.mark.abort_on_fail
async def test_avalanche_is_scraped_by_prometheus(juju: jubilant.Juju, charm, charm_resources):
    """Deploy the avalanche and deploy it together with related charms."""
    juju.deploy(charm, "avalanche", resources=charm_resources)
    juju.deploy("prometheus-k8s", "prometheus", channel="2/edge", trust=True)
    juju.integrate("avalanche:metrics-endpoint", "prometheus:metrics-endpoint")
    juju.wait(jubilant.all_active)
