# Create a Cloud Run service for burn-backend services
resource "google_cloud_run_v2_service" "tf-titiler" {
  name     = "tf-titiler-${terraform.workspace}"
  location = "us-central1"

  template {
    service_account = google_service_account.titiler-service.email
    timeout = "3599s" # max timeout is one hour
    containers {
      image = "us-docker.pkg.dev/cloudrun/container/placeholder" # This is a placeholder for first time creation only, replaced by CI/CD in GitHub Actions
      env {
        name  = "ENV"
        value = "CLOUD"
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

## TODO: Both this and the burn-backend service should either be require authenticated
## invocations or at least have a rate limit

# Allow unauthenticated invocations
resource "google_cloud_run_service_iam_member" "public" {
  service = google_cloud_run_v2_service.tf-titiler.name
  location = google_cloud_run_v2_service.tf-titiler.location
  role = "roles/run.invoker"
  member = "allUsers"
}


# Create the IAM service account for the Cloud Run service
resource "google_service_account" "titiler-service" {
  account_id   = "titiler-service-${terraform.workspace}"
  display_name = "Cloud Run Service Account for titiler - ${terraform.workspace}"
  description  = "This service account is used by the titiler service - doesn't need too much, since it retrieves public images from https"
  project      = "dse-nps"
}

resource "google_project_iam_member" "log_writer" {
  project = "dse-nps"
  role    = "roles/logging.logWriter"
  member  = "serviceAccount:${google_service_account.titiler-service.email}"
}
