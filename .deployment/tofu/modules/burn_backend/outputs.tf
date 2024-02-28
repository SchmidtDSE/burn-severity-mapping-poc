output "burn_backend_server_endpoint" {
    description = "The endpoint of the Cloud Run burn-backend service"
    value       = google_cloud_run_v2_service.tf-rest-burn-severity.uri
}

output "burn_backend_server_uuid" {
  description = "The UUID of the Cloud Run service"
  value       = google_cloud_run_v2_service.tf-rest-burn-severity.uid
}

output "gcp_service_account_s3_email" {
  description = "The email of the service account used by the backend service on GCP Cloud Run"
  value       = google_service_account.burn-backend-service.email
}

output "gcp_burn_backend_service_account_unique_id" {
  description = "The unique ID of the service account used by the backend service on GCP Cloud Run"
  value       = google_service_account.burn-backend-service.unique_id
}