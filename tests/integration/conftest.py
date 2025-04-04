# Copyright 2021 Canonical Ltd.
# See LICENSE file for licensing details.
import os
from pathlib import Path

import pytest
from pytest_operator.plugin import OpsTest


@pytest.fixture(scope="module")
async def charm_under_test(ops_test: OpsTest):
    """Charm used for integration testing."""
    if charm_file := os.environ.get("CHARM_PATH"):
        return Path(charm_file)

    charm = await ops_test.build_charm(".")
    return charm
