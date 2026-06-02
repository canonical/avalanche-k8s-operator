variable "model_uuid" {
  type        = string
  description = "UUID of the Juju model to deploy into"
}

variable "app_name" {
  type    = string
  default = "avalanche"
}

variable "channel" {
  type    = string
  default = "dev/edge"
}

variable "charm_name" {
  type    = string
  default = "avalanche-k8s"
}

variable "revision" {
  type    = number
  default = null
}

variable "config" {
  type    = map(string)
  default = {}
}

variable "constraints" {
  type    = string
  default = "arch=amd64"
}

variable "units" {
  type    = number
  default = 1
}

variable "storage_directives" {
  type    = map(string)
  default = {}
}
