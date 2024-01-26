output "gcp_cloud_run_endpoint" {
    description = "The endpoint of the Cloud Run burn-backend service"
    value       = module.burn_backend.burn_backend_server_endpoint
}

output "s3_from_gcp_arn" {
    description = "The ARN of the IAM Role which allows GCP to access S3"
    value       = module.static_io.s3_from_gcp_arn
}