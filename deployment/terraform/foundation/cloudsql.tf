resource "random_password" "db_app" {
  length  = 32
  special = false
}

resource "google_sql_database_instance" "main" {
  count            = var.enable_cloudsql ? 1 : 0
  name             = "grant-capture-pg"
  database_version = "POSTGRES_16"
  region           = var.region
  settings {
    tier              = var.db_tier
    edition           = "ENTERPRISE"
    activation_policy = var.db_activation_policy
    disk_type         = "PD_HDD"
    disk_size         = 10
    disk_autoresize   = false
    availability_type = "ZONAL"
    backup_configuration { enabled = false }
    ip_configuration {
      ipv4_enabled = true # no authorized networks; access only via Cloud SQL connectors/proxy with IAM
      ssl_mode     = "ENCRYPTED_ONLY"
    }
    database_flags {
      name  = "cloudsql.iam_authentication"
      value = "on"
    }
  }
  deletion_protection = false # recreated on demand; data is rebuilt by re-running ingestion
  depends_on          = [google_project_service.enabled]
  lifecycle {
    ignore_changes = [settings[0].activation_policy] # toggled by scripts/cloudsql.sh
  }
}

resource "google_sql_database" "app" {
  count    = var.enable_cloudsql ? 1 : 0
  name     = "grant_capture"
  instance = google_sql_database_instance.main[0].name
}

resource "google_sql_user" "app" {
  count    = var.enable_cloudsql ? 1 : 0
  name     = "grant_app"
  instance = google_sql_database_instance.main[0].name
  password = random_password.db_app.result
}

resource "google_secret_manager_secret_version" "db_app_password" {
  secret      = google_secret_manager_secret.secrets["db-app-password"].id
  secret_data = random_password.db_app.result
}
