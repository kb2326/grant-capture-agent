output "app_service" { value = google_cloud_run_v2_service.app.name }
output "agent_service_accounts" { value = { for k, sa in google_service_account.agent : k => sa.email } }
