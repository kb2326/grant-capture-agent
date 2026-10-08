variable "ingest_image" {
  type    = string
  default = "us-central1-docker.pkg.dev/grant-capture-agent/grant-capture/ingest:m0"
}

resource "google_cloud_run_v2_job" "ingest" {
  count = var.enable_cloudsql ? 1 : 0
  # Recreated on demand with the database; Terraform must be able to delete it.
  deletion_protection = false
  name                = "grant-capture-ingest"
  location            = var.region
  template {
    task_count = 1
    template {
      service_account = google_service_account.sa["ingest"].email
      timeout         = "3600s"
      max_retries     = 0
      volumes {
        name = "cloudsql"
        cloud_sql_instance { instances = [google_sql_database_instance.main[0].connection_name] }
      }
      containers {
        image = var.ingest_image
        args  = ["run", "--source", "grants_gov", "--limit", "500"] # M2 adds a sam_gov job
        resources { limits = { cpu = "1", memory = "1Gi" } }
        env {
          name  = "GOOGLE_CLOUD_PROJECT"
          value = var.project_id
        }
        env {
          name  = "BLOB_ROOT"
          value = "gs://${google_storage_bucket.raw.name}"
        }
        env {
          name = "DB_PASSWORD"
          value_source {
            secret_key_ref {
              secret  = google_secret_manager_secret.secrets["db-app-password"].secret_id
              version = "latest"
            }
          }
        }
        env {
          name  = "DATABASE_URL"
          value = "postgresql+psycopg://grant_app:$(DB_PASSWORD)@/grant_capture?host=/cloudsql/${google_sql_database_instance.main[0].connection_name}"
        }
        volume_mounts {
          name       = "cloudsql"
          mount_path = "/cloudsql"
        }
      }
    }
  }
  depends_on = [google_project_service.enabled]
}

resource "google_cloud_scheduler_job" "ingest_nightly" {
  count     = var.enable_cloudsql ? 1 : 0
  name      = "grant-capture-ingest-nightly"
  region    = var.region
  schedule  = "0 2 * * *"
  time_zone = "America/Chicago"
  paused    = true # enabled in M2 once Discover needs fresh data
  http_target {
    http_method = "POST"
    uri         = "https://run.googleapis.com/v2/projects/${var.project_id}/locations/${var.region}/jobs/${google_cloud_run_v2_job.ingest[0].name}:run"
    oauth_token { service_account_email = google_service_account.sa["ingest"].email }
  }
}

resource "google_cloud_run_v2_job_iam_member" "ingest_self_invoke" {
  count    = var.enable_cloudsql ? 1 : 0
  name     = google_cloud_run_v2_job.ingest[0].name
  location = var.region
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.sa["ingest"].email}"
}
