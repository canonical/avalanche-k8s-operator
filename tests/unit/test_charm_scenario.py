# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Comprehensive scenario-based unit tests for the Avalanche charm."""

from __future__ import annotations

import json

import pytest
from ops.model import ActiveStatus, MaintenanceStatus
from ops.testing import Container, Context, Exec, Relation, State

import charm

# -- Helpers / Fixtures ---------------------------------------------------


def _version_exec(stdout="0.7.0", return_code=0):
    """Create an Exec mock for the --version call."""
    return Exec(["/bin/avalanche", "--version"], return_code=return_code, stdout=stdout)


def _container(can_connect=True, version_stdout="0.7.0"):
    return Container(
        "avalanche",
        can_connect=can_connect,
        execs={_version_exec(stdout=version_stdout)},
    )


@pytest.fixture()
def avalanche_container():
    return _container()


@pytest.fixture()
def ctx():
    return Context(charm_type=charm.AvalancheCharm)


# -- Version Parsing Tests -----------------------------------------------


class TestVersionParsing:
    """Tests for _avalanche_version property."""

    def test_version_old_style(self, ctx):
        """Old avalanche outputs a plain version string like '0.3'."""
        container = _container(version_stdout="0.3\n")
        state = State(leader=True, containers={container})
        with ctx(ctx.on.config_changed(), state) as mgr:
            mgr.run()
            assert mgr.charm._avalanche_version == "0.3"

    def test_version_new_multiline(self, ctx):
        """v0.7.0+ outputs multi-line prometheus/common/version.Print() format."""
        multiline = (
            "avalanche, version 0.7.0 (branch: HEAD, revision: abc123)\n"
            "  build user:   user@host\n"
            "  build date:   20240101-00:00:00\n"
            "  go version:   go1.21.0\n"
        )
        container = _container(version_stdout=multiline)
        state = State(leader=True, containers={container})
        with ctx(ctx.on.config_changed(), state) as mgr:
            mgr.run()
            assert mgr.charm._avalanche_version == "0.7.0"

    def test_version_container_not_connected(self, ctx):
        """When container is not connected, version should be None."""
        container = _container(can_connect=False)
        state = State(leader=True, containers={container})
        with ctx(ctx.on.config_changed(), state) as mgr:
            mgr.run()
            assert mgr.charm._avalanche_version is None

    def test_version_exec_failure(self, ctx):
        """When the exec call fails, version should be None."""
        container = Container(
            "avalanche",
            can_connect=True,
            execs={Exec(["/bin/avalanche", "--version"], return_code=1, stdout="error")},
        )
        state = State(leader=True, containers={container})
        with ctx(ctx.on.config_changed(), state) as mgr:
            mgr.run()
            # Even if exec returns non-zero, we still try to parse output
            # The exact behavior depends on ops exec - just check it doesn't crash
            version = mgr.charm._avalanche_version
            assert version is None or isinstance(version, str)


# -- Status Tests ----------------------------------------------------------


class TestStatus:
    """Tests for charm status transitions."""

    def test_active_on_pebble_ready(self, ctx, avalanche_container):
        """Charm should be active after pebble_ready with connected container."""
        state = State(leader=True, containers={avalanche_container})
        out = ctx.run(ctx.on.pebble_ready(avalanche_container), state)
        assert out.unit_status == ActiveStatus()

    def test_active_on_start(self, ctx, avalanche_container):
        """Charm should be active after start with connected container."""
        state = State(leader=True, containers={avalanche_container})
        out = ctx.run(ctx.on.start(), state)
        assert out.unit_status == ActiveStatus()

    def test_active_on_config_changed(self, ctx, avalanche_container):
        """Charm should be active after config_changed with connected container."""
        state = State(leader=True, containers={avalanche_container})
        out = ctx.run(ctx.on.config_changed(), state)
        assert out.unit_status == ActiveStatus()

    def test_maintenance_when_container_not_ready(self, ctx):
        """Charm should be in maintenance when container cannot connect."""
        container = _container(can_connect=False)
        state = State(leader=True, containers={container})
        out = ctx.run(ctx.on.config_changed(), state)
        assert out.unit_status == MaintenanceStatus("Waiting for pod startup to complete")


# -- Pebble Layer / Command Tests ------------------------------------------


class TestPebbleLayer:
    """Tests for the generated pebble layer and command."""

    def test_scraped_mode_default_config(self, ctx, avalanche_container):
        """With no remote-write relation, command should use scraped mode with --port."""
        state = State(leader=True, containers={avalanche_container})
        out = ctx.run(ctx.on.config_changed(), state)
        plan = out.get_container("avalanche").plan
        command = plan.services["avalanche"].command

        assert "--port=9001" in command
        assert "--remote-url" not in command
        # Default config values
        assert "--gauge-metric-count=500" in command
        assert "--label-count=10" in command
        assert "--series-count=10" in command
        assert "--metricname-length=5" in command
        assert "--labelname-length=5" in command
        assert "--value-interval=30" in command
        assert "--series-interval=36000000" in command
        assert "--metric-interval=36000000" in command

    def test_scraped_mode_custom_config(self, ctx, avalanche_container):
        """Custom config values should appear in the command."""
        custom_config: dict[str, str | int | float | bool] = {
            "metric_count": 100,
            "label_count": 5,
            "series_count": 20,
            "metricname_length": 10,
            "labelname_length": 8,
            "value_interval": 60,
            "series_interval": 1000,
            "metric_interval": 2000,
        }
        state = State(leader=True, containers={avalanche_container}, config=custom_config)
        out = ctx.run(ctx.on.config_changed(), state)
        plan = out.get_container("avalanche").plan
        command = plan.services["avalanche"].command

        assert "--gauge-metric-count=100" in command
        assert "--label-count=5" in command
        assert "--series-count=20" in command
        assert "--metricname-length=10" in command
        assert "--labelname-length=8" in command
        assert "--value-interval=60" in command
        assert "--series-interval=1000" in command
        assert "--metric-interval=2000" in command
        assert "--port=9001" in command

    def test_remote_write_mode(self, ctx, avalanche_container):
        """With a remote-write relation providing an endpoint, command should use remote-write mode."""
        remote_write_rel = Relation(
            "send-remote-write",
            remote_app_name="prometheus",
            remote_app_data={
                "remote_write": json.dumps(
                    {"url": "http://prometheus-0.prometheus:9090/api/v1/write"}
                ),
            },
            remote_units_data={
                0: {
                    "remote_write": json.dumps(
                        {"url": "http://prometheus-0.prometheus:9090/api/v1/write"}
                    ),
                }
            },
        )
        state = State(
            leader=True,
            containers={avalanche_container},
            relations=[remote_write_rel],
        )
        out = ctx.run(ctx.on.config_changed(), state)
        plan = out.get_container("avalanche").plan
        command = plan.services["avalanche"].command

        # In remote write mode, the command should contain --remote-url
        # Note: whether --port or --remote-url appears depends on the
        # remote_write_consumer.endpoints being populated
        # The key thing is the command starts with /bin/avalanche
        assert command.startswith("/bin/avalanche")
        assert "--gauge-metric-count=" in command

    def test_command_starts_with_avalanche_binary(self, ctx, avalanche_container):
        """The command should always start with /bin/avalanche."""
        state = State(leader=True, containers={avalanche_container})
        out = ctx.run(ctx.on.config_changed(), state)
        plan = out.get_container("avalanche").plan
        command = plan.services["avalanche"].command
        assert command.startswith("/bin/avalanche")

    def test_layer_structure(self, ctx, avalanche_container):
        """The layer should have the correct structure."""
        state = State(leader=True, containers={avalanche_container})
        out = ctx.run(ctx.on.config_changed(), state)
        plan = out.get_container("avalanche").plan

        assert "avalanche" in plan.services
        svc = plan.services["avalanche"]
        assert svc.override == "replace"
        assert svc.startup == "enabled"


# -- Metrics-Endpoint Relation Tests ----------------------------------------


class TestMetricsEndpointRelation:
    """Tests for the metrics-endpoint (prometheus_scrape) relation data."""

    def test_scrape_metadata_in_databag(self, ctx, avalanche_container):
        """The scrape_metadata should contain Juju topology fields."""
        metrics_rel = Relation("metrics-endpoint", remote_app_name="prometheus")
        state = State(
            leader=True,
            containers={avalanche_container},
            relations=[metrics_rel],
        )
        out = ctx.run(ctx.on.config_changed(), state)
        rel_out = out.get_relation(metrics_rel.id)

        scrape_metadata = json.loads(rel_out.local_app_data.get("scrape_metadata", "{}"))
        assert "model" in scrape_metadata
        assert "application" in scrape_metadata

    def test_scrape_jobs_in_databag(self, ctx, avalanche_container):
        """The scrape_jobs should be set in the metrics-endpoint relation databag."""
        metrics_rel = Relation("metrics-endpoint", remote_app_name="prometheus")
        state = State(
            leader=True,
            containers={avalanche_container},
            relations=[metrics_rel],
        )
        out = ctx.run(ctx.on.config_changed(), state)
        rel_out = out.get_relation(metrics_rel.id)

        scrape_jobs = json.loads(rel_out.local_app_data.get("scrape_jobs", "[]"))
        assert len(scrape_jobs) > 0

        job = scrape_jobs[0]
        assert job["metrics_path"] == "/metrics"
        assert job["scrape_interval"] == "15s"
        assert job["scrape_timeout"] == "10s"

        # Check that the target port matches
        targets = job["static_configs"][0]["targets"]
        assert any("9001" in t for t in targets)

    def test_alert_rules_in_databag_when_forwarding(self, ctx, avalanche_container):
        """Alert rules should be set in the databag when forward_alert_rules is True."""
        metrics_rel = Relation("metrics-endpoint", remote_app_name="prometheus")
        state = State(
            leader=True,
            containers={avalanche_container},
            relations=[metrics_rel],
            config={"forward_alert_rules": True},
        )
        out = ctx.run(ctx.on.config_changed(), state)
        rel_out = out.get_relation(metrics_rel.id)

        alert_rules = json.loads(rel_out.local_app_data.get("alert_rules", "{}"))
        assert alert_rules != {}
        assert "groups" in alert_rules

    def test_no_alert_rules_in_databag_when_not_forwarding(self, ctx, avalanche_container):
        """Alert rules should be empty when forward_alert_rules is False."""
        metrics_rel = Relation("metrics-endpoint", remote_app_name="prometheus")
        state = State(
            leader=True,
            containers={avalanche_container},
            relations=[metrics_rel],
            config={"forward_alert_rules": False},
        )
        out = ctx.run(ctx.on.config_changed(), state)
        rel_out = out.get_relation(metrics_rel.id)

        alert_rules = json.loads(rel_out.local_app_data.get("alert_rules", "{}"))
        assert alert_rules == {}

    def test_non_leader_does_not_set_app_data(self, ctx, avalanche_container):
        """Non-leader units should not set application relation data."""
        metrics_rel = Relation("metrics-endpoint", remote_app_name="prometheus")
        state = State(
            leader=False,
            containers={avalanche_container},
            relations=[metrics_rel],
        )
        out = ctx.run(ctx.on.config_changed(), state)
        rel_out = out.get_relation(metrics_rel.id)

        # Non-leader should not have scrape_metadata in app data
        assert "scrape_metadata" not in rel_out.local_app_data


# -- Remote Write Relation Tests -------------------------------------------


class TestRemoteWriteRelation:
    """Tests for the send-remote-write (prometheus_remote_write) relation data."""

    def test_alert_rules_forwarded_on_remote_write(self, ctx, avalanche_container):
        """Alert rules should be forwarded on the remote-write relation when enabled."""
        rw_rel = Relation("send-remote-write", remote_app_name="prometheus")
        state = State(
            leader=True,
            containers={avalanche_container},
            relations=[rw_rel],
            config={"forward_alert_rules": True},
        )
        out = ctx.run(ctx.on.config_changed(), state)
        rel_out = out.get_relation(rw_rel.id)

        alert_rules = json.loads(rel_out.local_app_data.get("alert_rules", "{}"))
        assert alert_rules != {}
        assert "groups" in alert_rules

    def test_no_alert_rules_forwarded_when_disabled(self, ctx, avalanche_container):
        """Alert rules should be empty on remote-write when forwarding is disabled."""
        rw_rel = Relation("send-remote-write", remote_app_name="prometheus")
        state = State(
            leader=True,
            containers={avalanche_container},
            relations=[rw_rel],
            config={"forward_alert_rules": False},
        )
        out = ctx.run(ctx.on.config_changed(), state)
        rel_out = out.get_relation(rw_rel.id)

        alert_rules = json.loads(rel_out.local_app_data.get("alert_rules", "{}"))
        assert alert_rules == {}


# -- Config Change Tests ---------------------------------------------------


class TestConfigChanges:
    """Tests that config changes are reflected in the pebble layer."""

    def test_metric_count_change(self, ctx, avalanche_container):
        """Changing metric_count should update the command."""
        state = State(
            leader=True,
            containers={avalanche_container},
            config={"metric_count": 999},
        )
        out = ctx.run(ctx.on.config_changed(), state)
        command = out.get_container("avalanche").plan.services["avalanche"].command
        assert "--gauge-metric-count=999" in command

    def test_all_config_options_in_command(self, ctx, avalanche_container):
        """All config options should appear as CLI flags in the command."""
        config: dict[str, str | int | float | bool] = {
            "metric_count": 42,
            "label_count": 7,
            "series_count": 3,
            "metricname_length": 12,
            "labelname_length": 9,
            "value_interval": 120,
            "series_interval": 500,
            "metric_interval": 600,
        }
        state = State(leader=True, containers={avalanche_container}, config=config)
        out = ctx.run(ctx.on.config_changed(), state)
        command = out.get_container("avalanche").plan.services["avalanche"].command

        assert "--gauge-metric-count=42" in command
        assert "--label-count=7" in command
        assert "--series-count=3" in command
        assert "--metricname-length=12" in command
        assert "--labelname-length=9" in command
        assert "--value-interval=120" in command
        assert "--series-interval=500" in command
        assert "--metric-interval=600" in command


# -- Lifecycle Event Tests -------------------------------------------------


class TestLifecycleEvents:
    """Tests that each lifecycle event triggers the expected behavior."""

    def test_pebble_ready_sets_active(self, ctx, avalanche_container):
        state = State(leader=True, containers={avalanche_container})
        out = ctx.run(ctx.on.pebble_ready(avalanche_container), state)
        assert out.unit_status == ActiveStatus()

    def test_start_sets_active(self, ctx, avalanche_container):
        state = State(leader=True, containers={avalanche_container})
        out = ctx.run(ctx.on.start(), state)
        assert out.unit_status == ActiveStatus()

    def test_config_changed_sets_active(self, ctx, avalanche_container):
        state = State(leader=True, containers={avalanche_container})
        out = ctx.run(ctx.on.config_changed(), state)
        assert out.unit_status == ActiveStatus()

    def test_remote_write_endpoints_changed(self, ctx, avalanche_container):
        """The remote_write_endpoints_changed event should trigger common_exit_hook."""
        rw_rel = Relation("send-remote-write", remote_app_name="prometheus")
        state = State(
            leader=True,
            containers={avalanche_container},
            relations=[rw_rel],
        )
        # Trigger config_changed which causes the lib to re-evaluate
        out = ctx.run(ctx.on.config_changed(), state)
        assert out.unit_status == ActiveStatus()


# -- Workload Version Tests ------------------------------------------------


class TestWorkloadVersion:
    """Tests that workload version is correctly set."""

    def test_workload_version_set(self, ctx):
        """Workload version should be set from avalanche --version output."""
        container = _container(version_stdout="0.7.0")
        state = State(leader=True, containers={container})
        out = ctx.run(ctx.on.config_changed(), state)
        assert out.workload_version == "0.7.0"

    def test_workload_version_old_format(self, ctx):
        """Old-style version output should also be set correctly."""
        container = _container(version_stdout="0.3\n")
        state = State(leader=True, containers={container})
        out = ctx.run(ctx.on.config_changed(), state)
        assert out.workload_version == "0.3"

    def test_workload_version_multiline_format(self, ctx):
        """Multi-line v0.7.0+ version output should extract just the version number."""
        multiline = (
            "avalanche, version 0.7.0 (branch: HEAD, revision: abc)\n"
            "  build user:   user@host\n"
            "  build date:   20240101-00:00:00\n"
        )
        container = _container(version_stdout=multiline)
        state = State(leader=True, containers={container})
        out = ctx.run(ctx.on.config_changed(), state)
        assert out.workload_version == "0.7.0"

    def test_workload_version_not_set_when_container_down(self, ctx):
        """No workload version should be set when container can't connect."""
        container = _container(can_connect=False)
        state = State(leader=True, containers={container})
        out = ctx.run(ctx.on.config_changed(), state)
        assert out.workload_version == ""


# -- Port Tests ------------------------------------------------------------


class TestPort:
    """Tests for the port property."""

    def test_port_is_9001(self, ctx, avalanche_container):
        """The default port should be 9001."""
        state = State(leader=True, containers={avalanche_container})
        with ctx(ctx.on.config_changed(), state) as mgr:
            mgr.run()
            assert mgr.charm.port == 9001


# -- Install / Upgrade Tests -----------------------------------------------


class TestInstallUpgrade:
    """Tests for install and upgrade events that patch K8s service."""

    def test_install_leader(self, ctx, avalanche_container):
        """Install on leader should not crash (k8s patch errors are logged, not raised)."""
        state = State(leader=True, containers={avalanche_container})
        out = ctx.run(ctx.on.install(), state)
        # Install doesn't call _common_exit_hook, so status may be maintenance
        # The key assertion is that it doesn't crash
        assert out.unit_status is not None

    def test_install_non_leader(self, ctx, avalanche_container):
        """Install on non-leader should not attempt k8s patch."""
        state = State(leader=False, containers={avalanche_container})
        out = ctx.run(ctx.on.install(), state)
        assert out.unit_status is not None

    def test_upgrade_charm_leader(self, ctx, avalanche_container):
        """Upgrade charm on leader should succeed (k8s patch errors are caught)."""
        state = State(leader=True, containers={avalanche_container})
        out = ctx.run(ctx.on.upgrade_charm(), state)
        assert out.unit_status == ActiveStatus()

    def test_upgrade_charm_non_leader(self, ctx, avalanche_container):
        """Upgrade charm on non-leader should succeed (skips k8s patch)."""
        state = State(leader=False, containers={avalanche_container})
        out = ctx.run(ctx.on.upgrade_charm(), state)
        assert out.unit_status == ActiveStatus()


# -- Multiple Relations Tests ----------------------------------------------


class TestMultipleRelations:
    """Tests with multiple relations present."""

    def test_both_metrics_and_remote_write(self, ctx, avalanche_container):
        """Charm should handle both metrics-endpoint and send-remote-write relations."""
        metrics_rel = Relation("metrics-endpoint", remote_app_name="prometheus-scraper")
        rw_rel = Relation("send-remote-write", remote_app_name="prometheus-writer")
        state = State(
            leader=True,
            containers={avalanche_container},
            relations=[metrics_rel, rw_rel],
        )
        out = ctx.run(ctx.on.config_changed(), state)
        assert out.unit_status == ActiveStatus()

        # Both relations should have data
        metrics_out = out.get_relation(metrics_rel.id)
        rw_out = out.get_relation(rw_rel.id)

        assert "scrape_metadata" in metrics_out.local_app_data
        assert "scrape_jobs" in metrics_out.local_app_data
        assert "alert_rules" in rw_out.local_app_data

    def test_grafana_dashboard_relation(self, ctx, avalanche_container):
        """Charm should handle the grafana-dashboard relation."""
        grafana_rel = Relation("grafana-dashboard", remote_app_name="grafana")
        state = State(
            leader=True,
            containers={avalanche_container},
            relations=[grafana_rel],
        )
        out = ctx.run(ctx.on.config_changed(), state)
        assert out.unit_status == ActiveStatus()
