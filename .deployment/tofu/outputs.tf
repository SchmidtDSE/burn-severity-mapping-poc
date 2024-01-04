output "sftp_server_endpoint" {
  description = "The endpoint of the SFTP server"
  value       = module.sftp.sftp_server_endpoint
}

output "sftp_admin_username" {
  description = "The username of the SFTP admin user"
  value       = module.sftp.sftp_admin_username
}