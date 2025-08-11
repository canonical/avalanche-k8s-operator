# Copyright 2021 Canonical Ltd.
# See LICENSE file for licensing details.
import os
from pathlib import Path
from typing import Dict

import jubilant
import pytest
import sh
import yaml


@pytest.fixture(scope="module")
async def charm():
    """Charm used for integration testing."""
    if charm_file := os.environ.get("CHARM_PATH"):
        return Path(charm_file)

    charm = sh.charmcraft.pack()  # type: ignore
    assert charm
    return charm


@pytest.fixture(scope="module")
def charm_resources(metadata_file="charmcraft.yaml") -> Dict[str, str]:
    with open(metadata_file, "r") as file:
        metadata = yaml.safe_load(file)
    resources = {}
    for res, data in metadata["resources"].items():
        resources[res] = data["upstream-source"]
    return resources


@pytest.fixture(scope="module")
def juju():
    keep_models: bool = os.environ.get("KEEP_MODELS") is not None
    with jubilant.temp_model(keep=keep_models) as juju:
        yield juju
