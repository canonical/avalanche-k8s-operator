#!/usr/bin/env python3
# Copyright 2021 Canonical Ltd.
# See LICENSE file for licensing details.


import logging
from pathlib import Path

import pytest
import sh
import yaml
from helpers import get_config_values  # type: ignore[import]
from pytest_operator.plugin import OpsTest

logger = logging.getLogger(__name__)

METADATA = yaml.safe_load(Path("./charmcraft.yaml").read_text())
app_name = METADATA["name"]


@pytest.mark.abort_on_fail
async def test_config_values_are_retained_after_pod_upgraded(ops_test: OpsTest, charm_under_test):
    """Deploy from charmhub and then upgrade with the charm-under-test."""
    logger.info("deploy charm from charmhub")
    assert ops_test.model
    resources = {"avalanche-image": METADATA["resources"]["avalanche-image"]["upstream-source"]}
    resources_arg = f"avalanche-image={resources['avalanche-image']}"
    sh.juju.deploy(  # type: ignore
        app_name,
        model=ops_test.model.name,
        channel="1/edge",
        base="ubuntu@20.04",
        resource=resources_arg,
    )

    config = {"metric_count": "33", "value_interval": "99999"}
    sh.juju.config(app_name, "metric_count=33", "value_interval=99999", model=ops_test.model.name)  # type: ignore
    await ops_test.model.wait_for_idle(apps=[app_name], status="active", timeout=1000)

    logger.info("upgrade deployed charm with local charm %s", charm_under_test)
    sh.juju.refresh(  # type: ignore
        app_name, model=ops_test.model.name, path=charm_under_test, resource=resources_arg
    )
    await ops_test.model.wait_for_idle(apps=[app_name], status="active", timeout=1000)

    assert (await get_config_values(ops_test, app_name)).items() >= config.items()
