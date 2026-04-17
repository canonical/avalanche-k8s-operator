# Copyright 2021 Canonical Ltd.
# See LICENSE file for licensing details.
"""Prometheus API client for testing."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import requests
from tenacity import (
    retry,
    retry_if_exception_type,
    retry_if_result,
    stop_after_delay,
    wait_exponential,
    wait_fixed,
)


@dataclass
class Prometheus:
    """Client for the Prometheus HTTP API."""

    url: str
    headers: dict[str, str] | None = None
    timeout: int = 60
    session: requests.Session = field(init=False, repr=False)
    _retry_on_error: Any = field(init=False, repr=False)

    def __post_init__(self) -> None:
        """Prepare the API Session with Prometheus.

        Wrap the query methods in tenacity for automatic retry.
        """
        self.session = requests.Session()
        if self.headers:
            self.session.headers.update(self.headers)
        self._retry_on_error = retry(
            retry=retry_if_exception_type((requests.ConnectionError, requests.Timeout)),
            wait=wait_exponential(multiplier=1, max=30),
            stop=stop_after_delay(self.timeout),
            reraise=True,
        )
        self.query = self._retry_on_error(self.query)
        self.query_range = self._retry_on_error(self.query_range)
        self.get_rules = self._retry_on_error(self.get_rules)
        self.get_alerts = self._retry_on_error(self.get_alerts)
        self.get_targets = self._retry_on_error(self.get_targets)

    # --- HTTP methods (public, return parsed data) ---

    def query(self, promql: str) -> dict:
        """Execute an instant PromQL query."""
        resp = self.session.get(f"{self.url}/api/v1/query", params={"query": promql})
        resp.raise_for_status()
        return resp.json()

    def query_range(self, promql: str, start: str, end: str, step: str = "15s") -> dict:
        """Execute a range PromQL query."""
        resp = self.session.get(
            f"{self.url}/api/v1/query_range",
            params={"query": promql, "start": start, "end": end, "step": step},
        )
        resp.raise_for_status()
        return resp.json()

    def get_rules(self) -> dict:
        """Fetch all recording and alerting rules."""
        resp = self.session.get(f"{self.url}/api/v1/rules")
        resp.raise_for_status()
        return resp.json()

    def get_alerts(self) -> dict:
        """Fetch all active alerts."""
        resp = self.session.get(f"{self.url}/api/v1/alerts")
        resp.raise_for_status()
        return resp.json()

    def get_targets(self) -> dict:
        """Fetch all scrape targets."""
        resp = self.session.get(f"{self.url}/api/v1/targets")
        resp.raise_for_status()
        return resp.json()

    # --- Check methods (public, return bool) ---

    def has_metric(self, name: str | None = None, labels: dict[str, str] | None = None) -> bool:
        """Check whether a metric matching the given name regex and/or label regexes has data.

        All matching uses PromQL ``=~`` (regex, fully anchored).
        """
        pairs: list[str] = []
        if name is not None:
            pairs.append(f'__name__=~"{name}"')
        if labels:
            pairs.extend(f'{k}=~"{v}"' for k, v in labels.items())
        if not pairs:
            raise ValueError("At least one of 'name' or 'labels' must be provided")
        promql = "{" + ", ".join(pairs) + "}"
        result = self.query(promql)
        return len(result.get("data", {}).get("result", [])) > 0

    def wait_for_metric(
        self,
        name: str | None = None,
        labels: dict[str, str] | None = None,
        *,
        timeout: int = 300,
        interval: int = 15,
    ) -> None:
        """Poll until ``has_metric`` returns True.

        Raises AssertionError if the metric is not found within *timeout* seconds.
        """

        @retry(
            retry=retry_if_result(lambda r: not r) | retry_if_exception_type(Exception),
            stop=stop_after_delay(timeout),
            wait=wait_fixed(interval),
            reraise=True,
        )
        def _poll() -> bool:
            return self.has_metric(name=name, labels=labels)

        if not _poll():
            raise AssertionError(
                f"Timed out after {timeout}s waiting for metric "
                f"(name={name!r}, labels={labels!r})"
            )

    def has_alert_rule(self, name: str, group: str | None = None) -> bool:
        """Check whether an alerting rule with the given name exists."""
        data = self.get_rules()
        for rule_group in data.get("data", {}).get("groups", []):
            if group and rule_group.get("name") != group:
                continue
            for rule in rule_group.get("rules", []):
                if rule.get("name") == name and rule.get("type") == "alerting":
                    return True
        return False

    def has_alert_rules(self, labels: dict[str, str]) -> bool:
        """Check whether any alerting rule exists whose labels contain all the given key-value pairs."""
        data = self.get_rules()
        for rule_group in data.get("data", {}).get("groups", []):
            for rule in rule_group.get("rules", []):
                if rule.get("type") != "alerting":
                    continue
                rule_labels = rule.get("labels", {})
                if all(rule_labels.get(k) == v for k, v in labels.items()):
                    return True
        return False

    def has_active_alert(self, name: str, labels: dict[str, str] | None = None) -> bool:
        """Check whether an alert with the given name is currently firing."""
        data = self.get_alerts()
        for alert in data.get("data", {}).get("alerts", []):
            alert_labels = alert.get("labels", {})
            if alert_labels.get("alertname") != name:
                continue
            if labels and not all(alert_labels.get(k) == v for k, v in labels.items()):
                continue
            return True
        return False

    def has_target(
        self,
        job: str | None = None,
        url: str | None = None,
        health: str | None = None,
    ) -> bool:
        """Check whether a scrape target exists matching the given criteria."""
        data = self.get_targets()
        for target_group in ("activeTargets", "droppedTargets"):
            for target in data.get("data", {}).get(target_group, []):
                target_labels = target.get("labels", {})
                discovered = target.get("discoveredLabels", {})
                if job and target_labels.get("job") != job and discovered.get("job") != job:
                    continue
                if url and target.get("scrapeUrl") != url:
                    continue
                if health and target.get("health") != health:
                    continue
                return True
        return False
