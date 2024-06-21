# Create a Cloud Run service for burn-backend services
resource "google_cloud_run_v2_service" "tf-titiler" {
  name     = "tf-titiler-${terraform.workspace}"
  location = "us-central1"

  template {
    service_account = google_service_account.burn-backend-service.email
    timeout = "3599s" # max timeout is one hour
    containers {
      image = "us-docker.pkg.dev/cloudrun/container/placeholder" # This is a placeholder for first time creation only, replaced by CI/CD in GitHub Actions
      env {
        name  = "ENV"
        value = "CLOUD"
      }
      ## TODO [#24]: self-referential endpoint, will be solved by refactoring out titiler and/or making fully static
      env {
        name  = "GCP_CLOUD_RUN_ENDPOINT_TITILER"
        # value = "${terraform.workspace}" == "prod" ? "https://tf-rest-burn-severity-ohi6r6qs2a-uc.a.run.app" : "https://tf-rest-burn-severity-dev-ohi6r6qs2a-uc.a.run.app"
        value = var.gcp_cloud_run_endpoint_titiler
      }
      env {
        name  = "CPL_VSIL_CURL_ALLOWED_EXTENSIONS"
        value = ".tif,.TIF,.tiff"
      }
      env {
        name  = "GDAL_CACHEMAX"
        value = "200"
      }
      env {
        name  = "CPL_VSIL_CURL_CACHE_SIZE"
        value = "200000000"
      }
      env {
        name  = "GDAL_BAND_BLOCK_CACHE"
        value = "HASHSET"
      }
      env {
        name  = "GDAL_DISABLE_READDIR_ON_OPEN"
        value = "EMPTY_DIR"
      }
      env {
        name  = "GDAL_HTTP_MERGE_CONSECUTIVE_RANGES"
        value = "YES"
      }
      env {
        name  = "GDAL_HTTP_MULTIPLEX"
        value = "YES"
      }
      env {
        name  = "GDAL_HTTP_VERSION"
        value = "2"
      }
      env {
        name  = "VSI_CACHE"
        value = "TRUE"
      }
      env {
        name  = "VSI_CACHE_SIZE"
        value = "5000000"
      }
      resources {
        limits = {
          cpu    = "8"
          memory = "16Gi"
        }
      }
    }
    vpc_access {
      # connector = google_vpc_access_connector.burn_backend_vpc_connector.id
      connector = var.burn_backend_vpc_connector_id
      egress = "ALL_TRAFFIC"
    }
    scaling {
      min_instance_count = 1 # to reduce cold start time
      max_instance_count = 100
    }
  }

  traffic {
    percent         = 100
    type            = "TRAFFIC_TARGET_ALLOCATION_TYPE_LATEST"
  }

  lifecycle { # This helps to not replace the service if it already exists (the placeholder is just for first time creation)
    ignore_changes = [
      template[0].containers[0].image,
    ]
  }
}

# Create an Artifact Registry repo for the container image
resource "google_artifact_registry_repository" "burn-backend" {
  repository_id = "titiler-${terraform.workspace}"
  format        = "DOCKER"
  location      = "us-central1"
}