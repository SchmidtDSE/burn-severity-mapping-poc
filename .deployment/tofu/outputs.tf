output "sftp_server_endpoint" {
  description = "The endpoint of the SFTP server"
  value       = module.sftp.sftp_server_endpoint
}

output "sftp_admin_username" {
  description = "The username of the SFTP admin user"
  value       = module.sftp.sftp_admin_username
}

output "gcp_cloud_run_endpoint" {
    description = "The endpoint of the Cloud Run burn-backend service"
    value       = module.burn_backend.burn_backend_server_endpoint
}