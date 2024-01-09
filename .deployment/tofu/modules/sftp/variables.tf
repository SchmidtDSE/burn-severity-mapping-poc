variable "ssh_pairs" {
  description = "SSH private/public key pairs for the normie and admin user"
  type        = any
}

variable "google_project_number" {
    description = "Google project number"
    type        = string
}