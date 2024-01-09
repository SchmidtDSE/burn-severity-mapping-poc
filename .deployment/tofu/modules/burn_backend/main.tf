
# Create a VPC access connector, to let the Cloud Run service access the AWS Transfer server
resource "google_vpc_access_connector" "burn_backend_vpc_connector" {
  name          = "vpc-burn2023" # just to match aws naming reqs
  # network       = google_compute_network.burn_backend_network.id
  subnet {
    name = google_compute_subnetwork.burn_backend_subnetwork.name
  }
  region        = "us-central1"
  # ip_cidr_range = "10.3.0.0/28"
  depends_on    = [google_compute_network.burn_backend_network]
}

resource "google_compute_subnetwork" "burn_backend_subnetwork" {
  name          = "run-subnetwork"
  ip_cidr_range = "10.2.0.0/28"
  region        = "us-central1"
  network       = google_compute_network.burn_backend_network.id
  depends_on    = [google_compute_network.burn_backend_network]
}

resource "google_compute_network" "burn_backend_network" {
  name                    = "burn-backend-run-network"
  auto_create_subnetworks = false
}

# Create a Cloud Router
resource "google_compute_router" "burn_backend_router" {
  name    = "burn-backend-router"
  network = google_compute_network.burn_backend_network.name
  region  = "us-central1"
}

# Reserve a static IP address
resource "google_compute_address" "burn_backend_static_ip" {
  name   = "burn-backend-static-ip"
  region = "us-central1"
}

# Set up Cloud NAT
resource "google_compute_router_nat" "burn_backend_nat" {
  name   = "burn-backend-nat"
  router = google_compute_router.burn_backend_router.name
  region = "us-central1"

  nat_ip_allocate_option = "MANUAL_ONLY"
  nat_ips                = [google_compute_address.burn_backend_static_ip.self_link]

  source_subnetwork_ip_ranges_to_nat = "LIST_OF_SUBNETWORKS"
  subnetwork {
    name                    = google_compute_subnetwork.burn_backend_subnetwork.id
    source_ip_ranges_to_nat = ["ALL_IP_RANGES"]
  }
}

# Create a Cloud Run service
# Create a Cloud Run service
resource "google_cloud_run_v2_service" "tf-rest-burn-severity" {
  name     = "tf-rest-burn-severity"
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
      env {
        name  = "SFTP_SERVER_ENDPOINT"
        value = var.sftp_server_endpoint
      }
      env {
        name  = "SFTP_ADMIN_USERNAME"
        value = var.sftp_admin_username
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
      connector = google_vpc_access_connector.burn_backend_vpc_connector.id
      egress = "ALL_TRAFFIC"
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

# Allow unauthenticated invocations
resource "google_cloud_run_service_iam_member" "public" {
  service = google_cloud_run_v2_service.tf-rest-burn-severity.name
  location = google_cloud_run_v2_service.tf-rest-burn-severity.location
  role = "roles/run.invoker"
  member = "allUsers"
}

# Create the IAM workload identity pool and provider to auth GitHub Actions
resource "google_iam_workload_identity_pool" "pool" {
  workload_identity_pool_id = "github-actions"
  display_name = "Github Actions Pool"
  description  = "Workload identity pool for GitHub actions"
}

resource "google_iam_workload_identity_pool_provider" "oidc" {
  depends_on = [google_iam_workload_identity_pool.pool]
  workload_identity_pool_provider_id = "oidc-provider"
  workload_identity_pool_id          = google_iam_workload_identity_pool.pool.workload_identity_pool_id

  display_name = "GitHub OIDC Provider"

  oidc {
    issuer_uri        = "https://token.actions.githubusercontent.com"
  }

  attribute_mapping = {
    "google.subject" = "assertion.sub"
    "attribute.actor" = "assertion.actor"
    "attribute.repository" = "assertion.repository"
  }
}

resource "google_service_account_iam_binding" "workload_identity_user" {
  depends_on = [google_iam_workload_identity_pool_provider.oidc]
  service_account_id = google_service_account.github_actions.name
  role               = "roles/iam.workloadIdentityUser"
  members            = [
    "principalSet://iam.googleapis.com/projects/${var.google_project_number}/locations/global/workloadIdentityPools/${google_iam_workload_identity_pool.pool.workload_identity_pool_id}/attribute.repository/SchmidtDSE/burn-severity-mapping-poc"
  ]
}

# Create the IAM service account for GitHub Actions
resource "google_service_account" "github_actions" {
  account_id  = "github-actions-service-account"
  display_name = "Github Actions Service Account"
  description = "This service account is used by GitHub Actions"
  project     = "dse-nps"
}

# Create the IAM service account for the Cloud Run service
resource "google_service_account" "burn-backend-service" {
  account_id   = "burn-backend-service"
  display_name = "Cloud Run Service Account for burn backend"
  description  = "This service account is used by the Cloud Run service to access GCP Secrets Manager"
  project      = "dse-nps"
}

resource "google_project_iam_member" "secret_accessor" {
  project = "dse-nps"
  role    = "roles/secretmanager.secretAccessor"
  member  = "serviceAccount:${google_service_account.burn-backend-service.email}"
}

resource "google_project_iam_member" "log_writer" {
  project = "dse-nps"
  role    = "roles/logging.logWriter"
  member  = "serviceAccount:${google_service_account.burn-backend-service.email}"
}

# Give the service account permissions to deploy to Cloud Run, and to Cloud Build, and to the Workload Identity Pool
resource "google_project_iam_member" "run_admin" {
  project  = "dse-nps"
  role     = "roles/run.admin" 
  member   = "serviceAccount:${google_service_account.github_actions.email}"
}

resource "google_project_iam_member" "cloudbuild_builder" {
  project  = "dse-nps"
  role     = "roles/cloudbuild.builds.builder"
  member   = "serviceAccount:${google_service_account.github_actions.email}"
}

resource "google_project_iam_member" "SA_get_access_token" {
  project  = "dse-nps"
  role    = "roles/iam.serviceAccountTokenCreator"
  member   = "serviceAccount:${google_service_account.github_actions.email}"
}

resource "google_project_iam_member" "run_service_agent" {
  project  = "dse-nps"
  role    = "roles/run.serviceAgent"
  member   = "serviceAccount:${google_service_account.github_actions.email}"
}

resource "google_project_iam_member" "artifact_registry_writer" {
  project = "dse-nps"
  role    = "roles/artifactregistry.writer"
  member  = "serviceAccount:${google_service_account.github_actions.email}"
}

# Create an Artifact Registry repo for the container image
resource "google_artifact_registry_repository" "burn-backend" {
  repository_id = "burn-backend"
  format        = "DOCKER"
  location      = "us-central1"
}