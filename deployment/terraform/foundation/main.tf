locals {
  services = [
    "aiplatform.googleapis.com", "artifactregistry.googleapis.com", "cloudbuild.googleapis.com",
    "iam.googleapis.com", "iamcredentials.googleapis.com", "run.googleapis.com",
    "secretmanager.googleapis.com", "sqladmin.googleapis.com", "storage.googleapis.com",
    "sts.googleapis.com", "cloudscheduler.googleapis.com", "logging.googleapis.com",
    "cloudtrace.googleapis.com", "discoveryengine.googleapis.com",
  ]
}

resource "google_project_service" "enabled" {
  for_each           = toset(local.services)
  service            = each.value
  disable_on_destroy = false
}

resource "google_storage_bucket" "raw" {
  name                        = "${var.project_id}-raw"
  location                    = var.region
  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"
  versioning { enabled = false }
  lifecycle_rule {
    condition {
      age            = 30
      matches_prefix = ["raw/api/sam_gov/"] # the 210 MB daily SAM extract; keep 30 days for replay
    }
    action { type = "Delete" }
  }
  lifecycle_rule {
    condition { age = 365 }
    action {
      type          = "SetStorageClass"
      storage_class = "NEARLINE"
    }
  }
  depends_on = [google_project_service.enabled]
}

resource "google_artifact_registry_repository" "containers" {
  repository_id = "grant-capture"
  location      = var.region
  format        = "DOCKER"
  cleanup_policies {
    id     = "keep-recent"
    action = "KEEP"
    most_recent_versions { keep_count = 5 }
  }
  depends_on = [google_project_service.enabled]
}

resource "google_secret_manager_secret" "secrets" {
  for_each  = toset(["simpler-grants-api-key", "sam-api-key", "db-app-password"])
  secret_id = each.value
  replication {
    auto {}
  }
  depends_on = [google_project_service.enabled]
}
