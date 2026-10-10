# Production runtime layer (M4 spec §3.3). Validated and planned only - never applied in M4 (ADR-0021).

data "terraform_remote_state" "foundation" {
  backend = "gcs"
  config  = { bucket = "grant-capture-agent-tfstate", prefix = "foundation" }
}

locals {
  f = data.terraform_remote_state.foundation.outputs
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

# API + built UI on Cloud Run, scaled to zero when idle.
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
    containers {
      image = var.image
      ports { container_port = 8080 }
      resources {
        limits   = { cpu = "1", memory = "1Gi" }
        cpu_idle = true
      }
      env {
        name  = "GOOGLE_CLOUD_PROJECT"
        value = var.project_id
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
