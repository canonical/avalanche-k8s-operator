#!/usr/bin/env python3
# Copyright 2021 Canonical Ltd.
# See LICENSE file for licensing details.
import jubilant
import pytest

# Cross-base upgrades (e.g. 24.04 -> 26.04) are not supported via juju refresh.
# The charmhub charm is built for 24.04 (Python 3.12), while the local charm
# targets 26.04 (Python 3.14). Juju refresh only replaces charm code, not the
# container image, so the old container's Python cannot load the new venv.
pytestmark = pytest.mark.xfail(reason="Cross-base upgrade from 24.04 to 26.04 not supported")


@pytest.mark.abort_on_fail
def test_upgrade_charm(juju: jubilant.Juju, charm, charm_resources):
    """Deploy the avalanche and deploy it together with related charms."""
    juju.deploy(
        "avalanche-k8s",
        "avalanche",
        channel="dev/edge",
        config={"metric_count": "33", "value_interval": "99999"},
    )
    juju.wait(jubilant.all_active)
    juju.refresh("avalanche", path=charm, resources=charm_resources)
    juju.wait(jubilant.all_active)
