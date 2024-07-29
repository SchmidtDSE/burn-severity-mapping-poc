variable "google_project_number" {
    description = "Google project number"
    type        = string
}

variable "burn_backend_vpc_connector_id" {
    description = "The ID of the Burn Backend VPC Connector"
    type = string
}

variable "gcp_cloud_run_endpoint_burn_backend" {
    description = "The URL of the Burn Backend Cloud Run service"
    type = string
}
