variable "google_project_number" {
    description = "Google project number"
    type        = string
}

variable "s3_from_gcp_role_arn" {
    description = "Role ARN to assume to access S3 from GCP"
    type        = string
}

variable "s3_bucket_name" {
    description = "S3 bucket name"
    type        = string
}

variable "google_workload_identity_pool_id" {
    description = "The ID of the Google Workload Identity Pool, used to Authenticate Github Actions to GCP"
    type = string
}

variable "burn_backend_vpc_connector_id" {
    description = "The ID of the Burn Backend VPC Connector"
    type = string
}