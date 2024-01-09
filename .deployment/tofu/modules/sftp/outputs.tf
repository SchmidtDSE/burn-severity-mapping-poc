output "sftp_server_endpoint" {
  description = "The endpoint of the SFTP server"
  value       = aws_transfer_server.tf-sftp-burn-severity.endpoint
}

output "sftp_admin_username" {
    description = "The username of the SFTP admin user"
    value       = aws_transfer_user.tf-sftp-burn-severity.user_name
}