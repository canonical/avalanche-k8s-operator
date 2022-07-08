#!/usr/bin/env python3
# Copyright 2021 Canonical Ltd.
# See LICENSE file for licensing details.


import logging
from pathlib import Path

import pytest
import yaml
from helpers import IPAddressWorkaround  # type: ignore[import]

log = logging.getLogger(__name__)

METADATA = yaml.safe_load(Path("./metadata.yaml").read_text())


@pytest.mark.abort_on_fail
async def test_build_and_deploy(ops_test, charm_under_test):
    """Deploy the charm-under-test and deploy it together with related charms."""
    await ops_test.model.set_config({"logging-config": "<root>=WARNING; unit=DEBUG"})

    # deploy charm from local source folder
    resources = {"avalanche-image": METADATA["resources"]["avalanche-image"]["upstream-source"]}
    await ops_test.model.deploy(charm_under_test, resources=resources, application_name="av")
    # the charm should go into blocked status until related to alertmanager
    await ops_test.model.wait_for_idle(apps=["av"], status="active")


@pytest.mark.abort_on_fail
async def test_charm_successfully_relates_to_prometheus(ops_test):
    # deploy prometheus
    async with IPAddressWorkaround(ops_test):
        await ops_test.model.deploy(
            "ch:prometheus-k8s", application_name="prom", channel="edge", trust=True
        )
        await ops_test.model.wait_for_idle(apps=["prom"], status="active")

    await ops_test.model.add_relation("prom:receive-remote-write", "av:send-remote-write")
    await ops_test.model.wait_for_idle(apps=["av", "prom"], status="active")
