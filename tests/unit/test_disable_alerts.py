# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.


import pytest
from ops.testing import Container, Context, Exec, Relation, State

import charm


@pytest.fixture(scope="function")
def avalanche_container():
    return Container(
        "avalanche",
        can_connect=True,
        execs={Exec(["/bin/avalanche", "--version"], return_code=0, stdout="0.0")},
    )


@pytest.mark.parametrize("forwarding", (True, False))
def test_forward_alert_rules_scrape(forwarding, avalanche_container):
    # GIVEN these relations
    prometheus_relation = Relation("send-remote-write", remote_app_name="prometheus")
    state = State(
        leader=True,
        containers={avalanche_container},
        relations=[
            prometheus_relation,
        ],
        config={"forward_alert_rules": forwarding},
    )
    # WHEN the charm receives a config-changed event
    ctx = Context(
        charm_type=charm.AvalancheCharm,
    )
    with ctx(ctx.on.config_changed(), state) as mgr:
        output_state = mgr.run()
        # THEN the charm is forwarding the alerts
        prometheus_relation_out = output_state.get_relation(prometheus_relation.id)
        if forwarding:
            assert prometheus_relation_out.local_app_data["alert_rules"] != "{}"
        else:
            assert prometheus_relation_out.local_app_data["alert_rules"] == "{}"


@pytest.mark.parametrize("forwarding", (True, False))
def test_forward_alert_rules(forwarding, avalanche_container):
    # GIVEN these relations
    prometheus_relation = Relation("send-remote-write", remote_app_name="prometheus")
    state = State(
        leader=True,
        containers={avalanche_container},
        relations=[
            prometheus_relation,
        ],
        config={"forward_alert_rules": forwarding},
    )
    # WHEN the charm receives a config-changed event
    ctx = Context(
        charm_type=charm.AvalancheCharm,
    )
    with ctx(ctx.on.config_changed(), state) as mgr:
        output_state = mgr.run()
        # THEN the charm is forwarding the alerts
        prometheus_relation_out = output_state.get_relation(prometheus_relation.id)
        if forwarding:
            assert prometheus_relation_out.local_app_data["alert_rules"] != "{}"
        else:
            assert prometheus_relation_out.local_app_data["alert_rules"] == "{}"


@pytest.mark.parametrize("watchdog_enabled", (True, False))
def test_enable_watchdog_alerts(watchdog_enabled, avalanche_container):
    # GIVEN these relations and forward_alert_rules=True
    prometheus_relation = Relation("send-remote-write", remote_app_name="prometheus")
    state = State(
        leader=True,
        containers={avalanche_container},
        relations=[
            prometheus_relation,
        ],
        config={"forward_alert_rules": True, "enable_watchdog_alerts": watchdog_enabled},
    )
    # WHEN the charm receives a config-changed event
    ctx = Context(
        charm_type=charm.AvalancheCharm,
    )
    with ctx(ctx.on.config_changed(), state) as mgr:
        output_state = mgr.run()
        # THEN the charm forwards watchdog alerts only when enable_watchdog_alerts=True
        prometheus_relation_out = output_state.get_relation(prometheus_relation.id)
        alert_rules_json = prometheus_relation_out.local_app_data["alert_rules"]
        if watchdog_enabled:
            assert "AlwaysFiringDueToNumericValue" in alert_rules_json
            assert "AlwaysFiringDueToAbsentMetric" in alert_rules_json
        else:
            assert "AlwaysFiringDueToNumericValue" not in alert_rules_json
            assert "AlwaysFiringDueToAbsentMetric" not in alert_rules_json


def test_enable_watchdog_alerts_defaults_to_true(avalanche_container):
    # GIVEN forward_alert_rules=True and enable_watchdog_alerts not set (default)
    prometheus_relation = Relation("send-remote-write", remote_app_name="prometheus")
    state = State(
        leader=True,
        containers={avalanche_container},
        relations=[
            prometheus_relation,
        ],
        config={"forward_alert_rules": True},
    )
    # WHEN the charm receives a config-changed event
    ctx = Context(
        charm_type=charm.AvalancheCharm,
    )
    with ctx(ctx.on.config_changed(), state) as mgr:
        output_state = mgr.run()
        # THEN the charm forwards watchdog alerts by default
        prometheus_relation_out = output_state.get_relation(prometheus_relation.id)
        alert_rules_json = prometheus_relation_out.local_app_data["alert_rules"]
        assert "AlwaysFiringDueToNumericValue" in alert_rules_json
        assert "AlwaysFiringDueToAbsentMetric" in alert_rules_json
