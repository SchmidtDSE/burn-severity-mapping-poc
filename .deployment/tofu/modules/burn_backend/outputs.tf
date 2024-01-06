output "burn_backend_server_endpoint" {
    description = "The endpoint of the Cloud Run burn-backend service"
    value       = google_cloud_run_v2_service.tf-rest-burn-severity.uri
}