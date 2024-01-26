variable "google_project_number" {
    description = "Google project number"
    type        = string
}

variable "gcp_service_account_s3_email" {
    description = "Google service account email for GCP's access to S3"
    type        = string
}

variable "aws_account_id" {
    description = "AWS account ID"
    type        = string
}

variable "oidc_provider_domain_url" {
    description = "OIDC provider domain URL for GCP"
    type        = string
}