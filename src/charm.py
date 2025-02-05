#!/usr/bin/env python3
# Copyright 2021 Canonical Ltd.
# See LICENSE file for licensing details.

"""Deploy Avalanche to a Kubernetes environment."""

import hashlib
import logging
from typing import cast

from charms.grafana_k8s.v0.grafana_dashboard import GrafanaDashboardProvider
from charms.prometheus_k8s.v0.prometheus_scrape import MetricsEndpointProvider
from charms.prometheus_k8s.v1.prometheus_remote_write import (
    PrometheusRemoteWriteConsumer,
)
from ops.charm import CharmBase
from ops.framework import StoredState
from ops.main import main
from ops.model import ActiveStatus, BlockedStatus, MaintenanceStatus
from ops.pebble import Layer

from kubernetes_service import K8sServicePatch, PatchFailed

logger = logging.getLogger(__name__)


def sha256(hashable) -> str:
    """Use instead of the builtin hash() for repeatable values."""
    if isinstance(hashable, str):
        hashable = hashable.encode("utf-8")
    return hashlib.sha256(hashable).hexdigest()


class AvalancheCharm(CharmBase):
    """A Juju charm for Avalanche."""

    _container_name = "avalanche"  # automatically determined from charm name
    _layer_name = "avalanche"  # layer label argument for container.add_layer
    _service_name = "avalanche"  # chosen arbitrarily to match charm name
    _peer_relation_name = "replicas"  # must match metadata.yaml peer role name
    _port = 9001  # metrics endpoint

    _stored = StoredState()

    def __init__(self, *args):
        super().__init__(*args)
        self._stored.set_default(servers={}, config_hash=None)

        self.container = self.unit.get_container(self._container_name)
        self.unit.set_ports(self._port)

        self._disable_alerts = cast(bool, self.config["disable_forwarding_alert_rules"])

        self.metrics_endpoint = MetricsEndpointProvider(
            self,
            "metrics-endpoint",
            jobs=[
                {
                    "job_name": self.model.app.name,
                    "metrics_path": "/metrics",
                    "static_configs": [{"targets": [f"*:{self.port}"]}],
                    "scrape_interval": "15s",  # TODO move to config.yaml
                    "scrape_timeout": "10s",
                }
            ],
            disable_forwarding_alert_rules=self._disable_alerts,
            refresh_event=[self.on.config_changed],
        )

        self.remote_write_consumer = PrometheusRemoteWriteConsumer(
            self,
            disable_forwarding_alert_rules=self._disable_alerts,
        )
        self.framework.observe(
            self.remote_write_consumer.on.endpoints_changed,  # pyright: ignore
            self._remote_write_endpoints_changed,
        )

        self.grafana_dashboard_provider = GrafanaDashboardProvider(self)

        # Core lifecycle events
        self.framework.observe(self.on.install, self._on_install)
        self.framework.observe(self.on.config_changed, self._on_config_changed)
        self.framework.observe(self.on.upgrade_charm, self._on_upgrade_charm)
        self.framework.observe(
            self.on.avalanche_pebble_ready,
            self._on_pebble_ready,  # pyright: ignore
        )
        self.framework.observe(self.on.start, self._on_start)
        self.framework.observe(self.on.update_status, self._on_update_status)

    def _common_exit_hook(self) -> None:
        """Event processing hook that is common to all events to ensure idempotency."""
        if not self.container.can_connect():
            self.unit.status = MaintenanceStatus("Waiting for pod startup to complete")
            return

        # Update pebble layer
        layer_changed = self._update_layer()
        service_running = (
            service := self.container.get_service(self._service_name)
        ) and service.is_running()
        if layer_changed or not service_running:
            if not self._restart_service():
                self.unit.status = BlockedStatus("Service restart failed")
                return

        self.unit.status = ActiveStatus()

    def _update_layer(self) -> bool:
        """Update service layer to reflect changes in peers (replicas).

        Args:
          restart: a flag indicating if the service should be restarted if a change was detected.

        Returns:
          True if anything changed; False otherwise
        """
        overlay = self._layer()
        plan = self.container.get_plan()

        is_changed = False

        if self._service_name not in plan.services or overlay.services != plan.services:
            logger.debug(
                "Layer changed; command: %s",
                overlay.services[self._service_name].command,
            )
            is_changed = True
            self.container.add_layer(self._layer_name, overlay, combine=True)
            self.container.replan()
            logger.debug(
                "New layer's command: %s",
                self.container.get_plan().services.get(self._service_name).command,  # pyright: ignore
            )
        else:
            logger.debug("Layer unchanged")

        return is_changed

    @property
    def port(self):
        """Return the default Avalanche port."""
        return self._port

    def _layer(self) -> Layer:
        """Returns the Pebble configuration layer for Avalanche."""

        def _command() -> str:
            if endpoints := self.remote_write_consumer.endpoints:
                # remote-write mode TODO error out / block if both relations present
                # avalanche cli args support only one remote write target; take the first one
                logger.debug(
                    "Going into remote write mode; remote write endpoints: %s",
                    self.remote_write_consumer.endpoints,
                )

                endpoint = endpoints[0]["url"]
                # TODO offer remote-write-interval as config option
                mode_args = f"--remote-url={endpoint} --remote-write-interval=15s"
            else:
                # scraped mode
                logger.debug("Going into scraped mode (no remote write endpoints)")

                mode_args = f"--port={self.port}"

            return " ".join(
                [
                    "/bin/avalanche",
                    f"--metric-count={self.config['metric_count']}",
                    f"--label-count={self.config['label_count']}",
                    f"--series-count={self.config['series_count']}",
                    f"--metricname-length={self.config['metricname_length']}",
                    f"--labelname-length={self.config['labelname_length']}",
                    f"--value-interval={self.config['value_interval']}",
                    f"--series-interval={self.config['series_interval']}",
                    f"--metric-interval={self.config['metric_interval']}",
                    mode_args,
                ]
            )

        return Layer(
            {
                "summary": "avalanche layer",
                "description": "pebble config layer for avalanche",
                "services": {
                    self._service_name: {
                        "override": "replace",
                        "summary": "avalanche service",
                        "startup": "enabled",
                        "command": _command(),
                    },
                },
            }
        )

    def _on_install(self, _):
        """Event handler for the `install` event during which we will update the K8s service."""
        self._patch_k8s_service()

    def _on_upgrade_charm(self, _):
        """Event handler for the upgrade event during which we will update the K8s service."""
        # Ensure that older deployments of Avalanche run the logic to patch the K8s service
        self._patch_k8s_service()

        # After upgrade (refresh), the unit ip address is not guaranteed to remain the same, and
        # the config may need update. Calling the common hook to update.
        self._common_exit_hook()

    def _patch_k8s_service(self):
        """Fix the Kubernetes service that was set up by Juju with correct port numbers."""
        if self.unit.is_leader():
            service_ports = [
                (f"{self.app.name}", self._port, self._port),
            ]
            try:
                K8sServicePatch.set_ports(self.app.name, service_ports)
            except PatchFailed as e:
                logger.error("Unable to patch the Kubernetes service: %s", str(e))
            else:
                logger.debug("Successfully patched the Kubernetes service")

    def _on_pebble_ready(self, _):
        """Event handler for PebbleReadyEvent."""
        self._common_exit_hook()

    def _on_start(self, _):
        """Event handler for StartEvent.

        With Juju 2.9.5 encountered a scenario in which pebble_ready and config_changed fired,
        but IP address was not available and the status was stuck on "Waiting for IP address".
        Adding this hook reduce the likelihood of that scenario.
        """
        self._common_exit_hook()

    def _on_config_changed(self, _):
        """Event handler for ConfigChangedEvent."""
        self._common_exit_hook()

    def _on_alertmanager_config_changed(self, _):
        """Event handler for :class:`AvalancheAlertmanagerConfigChanged`."""
        self._common_exit_hook()

    def _restart_service(self) -> bool:
        """Helper function for restarting the underlying service."""
        logger.info("Restarting service %s", self._service_name)

        if not self.container.can_connect():
            logger.error("Cannot (re)start service: container is not ready.")
            return False

        # Check if service exists, to avoid ModelError from being raised when the service does
        # not yet exist
        if not self.container.get_services().get(self._service_name):
            logger.error("Cannot (re)start service: service does not (yet) exist.")
            return False

        self.container.restart(self._service_name)

        return True

    def _on_update_status(self, _):
        """Event handler for UpdateStatusEvent.

        Logs list of peers, uptime and version info.
        """
        pass

    def _remote_write_endpoints_changed(self, _):
        """Event handler for remote write endpoints_changed."""
        self._common_exit_hook()


if __name__ == "__main__":
    main(AvalancheCharm, use_juju_for_storage=True)
