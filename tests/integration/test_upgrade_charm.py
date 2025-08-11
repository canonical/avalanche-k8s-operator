#!/usr/bin/env python3
# Copyright 2021 Canonical Ltd.
# See LICENSE file for licensing details.
import jubilant
import pytest


@pytest.mark.abort_on_fail
async def test_upgrade_charm(juju: jubilant.Juju, charm):
    """Deploy the avalanche and deploy it together with related charms."""
    juju.deploy(
        "avalanche-k8s",
        "avalanche",
        channel="2/edge",
        config={"metric_count": "33", "value_interval": "99999"},
    )
    juju.wait(jubilant.all_active)
    juju.refresh("avalanche", path=charm)
    juju.wait(jubilant.all_active)
