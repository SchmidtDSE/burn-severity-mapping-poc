output "gcp_cloud_run_endpoint" {
    description = "The endpoint of the Cloud Run burn-backend service"
    value       = module.burn_backend.burn_backend_server_endpoint
}