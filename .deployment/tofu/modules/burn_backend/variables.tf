variable "google_project_number" {
    description = "Google project number"
    type        = string
}

variable "s3_from_gcp_role_arn" {
    description = "Role ARN to assume to access S3 from GCP"
    type        = string
}