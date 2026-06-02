output "app_name" {
  value = juju_application.avalanche.name
}

output "provides" {
  value = {
    metrics_endpoint  = "metrics-endpoint"
    grafana_dashboard = "grafana-dashboard"
  }
}

output "requires" {
  value = {
    send_remote_write = "send-remote-write"
  }
}
