variable "ssh_pairs" {
  description = "SSH private/public key pairs for the normie and admin user"
  type        = any
}

variable "google_project_number" {
    description = "Google project number"
    type        = string
}

variable "sftp_server_endpoint" {
  description = "The endpoint of the SFTP server"
  type        = string
}

variable "sftp_admin_username" {
  description = "The username of the admin user"
  type        = string
}