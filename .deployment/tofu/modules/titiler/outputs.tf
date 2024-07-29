output "titiler_server_endpoint" {
    description = "The endpoint of the Cloud Run titiler (map tiling) service"
    value = google_cloud_run_v2_service.tf-titiler.uri
}
