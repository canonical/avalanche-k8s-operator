output "app_name" {
  value = juju_application.avalanche.name
}

output "provides" {
  value = {
    metrics_endpoint  = "metrics-endpoint"
    grafana_dashboard = "grafana-dashboard"
    provide_cmr_mesh  = "provide-cmr-mesh"
  }
}

output "requires" {
  value = {
    send_remote_write = "send-remote-write"
    service_mesh      = "service-mesh"
    require_cmr_mesh  = "require-cmr-mesh"
  }
}
