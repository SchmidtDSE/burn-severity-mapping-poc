output "google_workload_identity_pool_id" {
    description = "The ID of the Google Workload Identity Pool, used to Authenticate Github Actions to GCP"
    value = google_iam_workload_identity_pool.pool.id
}

output "burn_backend_vpc_connector_id" {
    description = "The ID of the Burn Backend VPC Connector"
    value = google_vpc_access_connector.burn_backend_vpc_connector.id
}