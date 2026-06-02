<!-- BEGIN_TF_DOCS -->
## Requirements

| Name | Version |
|------|---------|
| <a name="requirement_terraform"></a> [terraform](#requirement\_terraform) | >= 1.6 |
| <a name="requirement_juju"></a> [juju](#requirement\_juju) | ~> 1.0 |

## Providers

| Name | Version |
|------|---------|
| <a name="provider_juju"></a> [juju](#provider\_juju) | ~> 1.0 |

## Modules

No modules.

## Inputs

| Name | Description | Type | Default | Required |
|------|-------------|------|---------|:--------:|
| <a name="input_app_name"></a> [app\_name](#input\_app\_name) | n/a | `string` | `"avalanche"` | no |
| <a name="input_channel"></a> [channel](#input\_channel) | n/a | `string` | `"dev/edge"` | no |
| <a name="input_charm_name"></a> [charm\_name](#input\_charm\_name) | n/a | `string` | `"avalanche-k8s"` | no |
| <a name="input_config"></a> [config](#input\_config) | n/a | `map(string)` | `{}` | no |
| <a name="input_constraints"></a> [constraints](#input\_constraints) | n/a | `string` | `"arch=amd64"` | no |
| <a name="input_model_uuid"></a> [model\_uuid](#input\_model\_uuid) | UUID of the Juju model to deploy into | `string` | n/a | yes |
| <a name="input_revision"></a> [revision](#input\_revision) | n/a | `number` | `null` | no |
| <a name="input_storage_directives"></a> [storage\_directives](#input\_storage\_directives) | n/a | `map(string)` | `{}` | no |
| <a name="input_units"></a> [units](#input\_units) | n/a | `number` | `1` | no |

## Outputs

| Name | Description |
|------|-------------|
| <a name="output_app_name"></a> [app\_name](#output\_app\_name) | n/a |
| <a name="output_provides"></a> [provides](#output\_provides) | n/a |
| <a name="output_requires"></a> [requires](#output\_requires) | n/a |
<!-- END_TF_DOCS -->