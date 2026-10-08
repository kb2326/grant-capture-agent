variable "project_id" { type = string }
variable "region" {
  type    = string
  default = "us-central1"
}
variable "github_repository" {
  type        = string
  description = "owner/repo allowed to use Workload Identity Federation"
}
variable "db_tier" {
  type    = string
  default = "db-f1-micro"
}
variable "enable_cloudsql" {
  type        = bool
  default     = true
  description = "false deletes the instance between work sessions (a stopped instance still pays for its IPv4 address)"
}
variable "db_activation_policy" {
  type        = string
  default     = "ALWAYS"
  description = "Initial policy only; the instance must be running for Terraform to create the database and user. scripts/cloudsql.sh toggles it afterwards."
}
