variable "project_id" { type = string }
variable "region" {
  type    = string
  default = "us-central1"
}
variable "image" {
  type        = string
  description = "Container image for the API + UI (built from Dockerfile.api and pushed by CI)."
  default     = "us-central1-docker.pkg.dev/grant-capture-agent/grant-capture/app:latest"
}
variable "create_budget" {
  type    = bool
  default = false # the $10 budget already exists (created in M0); set true to manage it here
}
variable "billing_account" {
  type    = string
  default = ""
}
variable "budget_usd" {
  type    = number
  default = 10
}
