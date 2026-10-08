locals {
  sas = {
    ingest = "Ingestion job: writes raw files and DB rows"
    agent  = "ADK agents on Agent Runtime: reads DB, calls Gemini"
    api    = "FastAPI backend on Cloud Run"
    ci     = "GitHub Actions via Workload Identity Federation"
  }
}

resource "google_service_account" "sa" {
  for_each     = local.sas
  account_id   = "gca-${each.key}"
  display_name = "grant-capture ${each.key}"
  description  = each.value
}

# Ingestion: Cloud SQL client, write raw bucket, read source-API and DB secrets
resource "google_project_iam_member" "ingest_sql" {
  project = var.project_id
  role    = "roles/cloudsql.client"
  member  = "serviceAccount:${google_service_account.sa["ingest"].email}"
}
resource "google_storage_bucket_iam_member" "ingest_raw" {
  bucket = google_storage_bucket.raw.name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${google_service_account.sa["ingest"].email}"
}
resource "google_secret_manager_secret_iam_member" "ingest_secrets" {
  for_each  = toset(["simpler-grants-api-key", "sam-api-key", "db-app-password"])
  secret_id = google_secret_manager_secret.secrets[each.value].id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.sa["ingest"].email}"
}

# Agents: Gemini + Cloud SQL client + read raw bucket + DB password
resource "google_project_iam_member" "agent_roles" {
  for_each = toset(["roles/aiplatform.user", "roles/cloudsql.client"])
  project  = var.project_id
  role     = each.value
  member   = "serviceAccount:${google_service_account.sa["agent"].email}"
}
resource "google_storage_bucket_iam_member" "agent_raw_read" {
  bucket = google_storage_bucket.raw.name
  role   = "roles/storage.objectViewer"
  member = "serviceAccount:${google_service_account.sa["agent"].email}"
}
resource "google_secret_manager_secret_iam_member" "agent_db_secret" {
  secret_id = google_secret_manager_secret.secrets["db-app-password"].id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.sa["agent"].email}"
}

# CI: push images and run the ingestion job; nothing else in M0
resource "google_artifact_registry_repository_iam_member" "ci_push" {
  repository = google_artifact_registry_repository.containers.name
  location   = var.region
  role       = "roles/artifactregistry.writer"
  member     = "serviceAccount:${google_service_account.sa["ci"].email}"
}

resource "google_iam_workload_identity_pool" "github" {
  workload_identity_pool_id = "github"
  display_name              = "GitHub Actions"
}

resource "google_iam_workload_identity_pool_provider" "github" {
  workload_identity_pool_id          = google_iam_workload_identity_pool.github.workload_identity_pool_id
  workload_identity_pool_provider_id = "github-oidc"
  attribute_mapping = {
    "google.subject"       = "assertion.sub"
    "attribute.repository" = "assertion.repository"
    "attribute.ref"        = "assertion.ref"
  }
  attribute_condition = "assertion.repository == \"${var.github_repository}\""
  oidc { issuer_uri = "https://token.actions.githubusercontent.com" }
}

resource "google_service_account_iam_member" "ci_wif" {
  service_account_id = google_service_account.sa["ci"].name
  role               = "roles/iam.workloadIdentityUser"
  member             = "principalSet://iam.googleapis.com/${google_iam_workload_identity_pool.github.name}/attribute.repository/${var.github_repository}"
}
