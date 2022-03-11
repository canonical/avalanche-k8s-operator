# Copyright 2021 Canonical Ltd.
# See LICENSE file for licensing details.

import unittest

from ops.model import ActiveStatus
from ops.testing import Harness

from charm import AvalancheCharm


class TestCharm(unittest.TestCase):
    def setUp(self):
        self.harness = Harness(AvalancheCharm)
        self.addCleanup(self.harness.cleanup)
        self.harness.begin_with_initial_hooks()

    def test_services_running(self):
        """Check that the supplied service is running and charm is ActiveStatus."""
        service = self.harness.model.unit.get_container(
            AvalancheCharm._container_name
        ).get_service(AvalancheCharm._service_name)
        self.assertTrue(service.is_running())
        self.assertEqual(self.harness.model.unit.status, ActiveStatus())
