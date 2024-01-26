output "burn_backend_server_endpoint" {
    description = "The endpoint of the Cloud Run burn-backend service"
    value       = google_cloud_run_v2_service.tf-rest-burn-severity.uri
}

output "google_service_account_s3_email" {
  description = "The email of the service account used by the backend service on GCP Cloud Run"
  value       = google_service_account.burn-backend-service.email
}