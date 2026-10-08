output "raw_bucket" { value = google_storage_bucket.raw.name }
output "artifact_repo" {
  value = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.containers.repository_id}"
}
output "cloudsql_instance" { value = one(google_sql_database_instance.main[*].name) }
output "cloudsql_connection_name" { value = one(google_sql_database_instance.main[*].connection_name) }
output "ingest_sa_email" { value = google_service_account.sa["ingest"].email }
output "agent_sa_email" { value = google_service_account.sa["agent"].email }
output "api_sa_email" { value = google_service_account.sa["api"].email }
output "ci_sa_email" { value = google_service_account.sa["ci"].email }
output "wif_provider" { value = google_iam_workload_identity_pool_provider.github.name }
