resource "juju_application" "avalanche" {
  name               = var.app_name
  model_uuid         = var.model_uuid
  trust              = true
  constraints        = var.constraints
  units              = var.units
  storage_directives = var.storage_directives
  config             = var.config

  charm {
    name     = var.charm_name
    channel  = var.channel
    revision = var.revision
  }
}
