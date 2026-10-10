# Production runtime layer (M4 spec §3.3). Validated and planned only - never applied in M4 (ADR-0021).

data "terraform_remote_state" "foundation" {
  backend = "gcs"
  config  = { bucket = "grant-capture-agent-tfstate", prefix = "foundation" }
}

locals {
  f = data.terraform_remote_state.foundation.outputs
  # null outputs are omitted from state, so read the optional one with a default
  sql_conn = lookup(local.f, "cloudsql_connection_name", null)
  agents = {
    "root-agent"    = "Root chat agent (Discover, Analyze, Draft tools)"
    "analyze-agent" = "Analyze agent served as its own A2A service"
  }
}

# One identity per agent (ADR-0014): permissions are granted per agent, not per project.
resource "google_service_account" "agent" {
  for_each     = local.agents
  account_id   = each.key
  display_name = each.value
}

resource "google_project_iam_member" "agent_vertex" {
  for_each = local.agents
  project  = var.project_id
  role     = "roles/aiplatform.user"
  member   = "serviceAccount:${google_service_account.agent[each.key].email}"
}

resource "google_project_iam_member" "agent_trace" {
  for_each = local.agents
  project  = var.project_id
  role     = "roles/cloudtrace.agent"
  member   = "serviceAccount:${google_service_account.agent[each.key].email}"
}

resource "google_secret_manager_secret_iam_member" "agent_db" {
  for_each  = local.agents
  secret_id = "db-app-password"
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.agent[each.key].email}"
}

# The API (gca-api from the foundation) runs the tools in-process: it calls Gemini,
# reads the database through the Cloud SQL connector and reads documents from the raw bucket.
resource "google_project_iam_member" "api_roles" {
  for_each = toset(["roles/aiplatform.user", "roles/cloudsql.client", "roles/cloudtrace.agent"])
  project  = var.project_id
  role     = each.value
  member   = "serviceAccount:${local.f.api_sa_email}"
}

resource "google_secret_manager_secret_iam_member" "api_db" {
  secret_id = "db-app-password"
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${local.f.api_sa_email}"
}

resource "google_storage_bucket_iam_member" "api_raw_read" {
  bucket = local.f.raw_bucket
  role   = "roles/storage.objectViewer"
  member = "serviceAccount:${local.f.api_sa_email}"
}

# API + built UI on Cloud Run, scaled to zero when idle.
# Needs Cloud SQL on (foundation enable_cloudsql=true, runbook step 2) before apply;
# with it off the connector volume is omitted and the service has no database.
resource "google_cloud_run_v2_service" "app" {
  name     = "grant-capture-app"
  location = var.region
  ingress  = "INGRESS_TRAFFIC_ALL"

  template {
    service_account = local.f.api_sa_email
    scaling {
      min_instance_count = 0
      max_instance_count = 2
    }
    dynamic "volumes" {
      for_each = local.sql_conn == null ? [] : [local.sql_conn]
      content {
        name = "cloudsql"
        cloud_sql_instance { instances = [volumes.value] }
      }
    }
    containers {
      image = var.image
      ports { container_port = 8080 }
      dynamic "volume_mounts" {
        for_each = local.sql_conn == null ? [] : [1]
        content {
          name       = "cloudsql"
          mount_path = "/cloudsql"
        }
      }
      resources {
        limits   = { cpu = "1", memory = "1Gi" }
        cpu_idle = true
      }
      env {
        name  = "GOOGLE_CLOUD_PROJECT"
        value = var.project_id
      }
      env {
        name  = "GOOGLE_GENAI_USE_ENTERPRISE"
        value = "true"
      }
      env {
        name  = "BLOB_ROOT"
        value = "gs://${local.f.raw_bucket}"
      }
      env {
        # app/config.py substitutes $(DB_PASSWORD) from the secret below
        name  = "DATABASE_URL"
        value = "postgresql+psycopg://grant_app:$(DB_PASSWORD)@/grant_capture?host=/cloudsql/${coalesce(local.sql_conn, "cloudsql-off")}"
      }
      env {
        name = "DB_PASSWORD"
        value_source {
          secret_key_ref {
            secret  = "db-app-password"
            version = "latest"
          }
        }
      }
    }
  }
}

resource "google_billing_budget" "monthly" {
  count           = var.create_budget ? 1 : 0
  billing_account = var.billing_account
  display_name    = "grant-capture-agent monthly"
  budget_filter { projects = ["projects/${var.project_id}"] }
  amount {
    specified_amount {
      currency_code = "USD"
      units         = tostring(var.budget_usd)
    }
  }
  threshold_rules { threshold_percent = 0.5 }
  threshold_rules { threshold_percent = 0.9 }
  threshold_rules { threshold_percent = 1.0 }
}
