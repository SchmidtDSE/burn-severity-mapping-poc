output "gcp_cloud_run_endpoint" {
    description = "The endpoint of the Cloud Run burn-backend service"
    value       = module.burn_backend.burn_backend_server_endpoint
}

output "gcp_service_account_s3_email" {
    description = "The email address of the Cloud Run burn-backend service account"
    value       = module.burn_backend.gcp_service_account_s3_email
}

output "s3_from_gcp_role_arn" {
    description = "The ARN of the IAM Role which allows GCP to access S3"
    value       = module.static_io.s3_from_gcp_role_arn
}

output "gcp_cloud_run_uuid" {
    description = "The UUID of the Cloud Run burn-backend service"
    value       = module.burn_backend.burn_backend_server_uuid
}