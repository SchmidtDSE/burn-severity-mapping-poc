
# Create a VPC access connector, to let the Cloud Run service access the AWS Transfer server
resource "google_vpc_access_connector" "burn_backend_vpc_connector" {
  name          = "vpc-burn2023-${terraform.workspace}" # just to match aws naming reqs
  # network       = google_compute_network.burn_backend_network.id
  subnet {
    name = google_compute_subnetwork.burn_backend_subnetwork.name
  }
  region        = "us-central1"
  # ip_cidr_range = "10.3.0.0/28"
  depends_on    = [google_compute_network.burn_backend_network]
}

resource "google_compute_subnetwork" "burn_backend_subnetwork" {
  name          = "run-subnetwork-${terraform.workspace}"
  ip_cidr_range = "10.2.0.0/28"
  region        = "us-central1"
  network       = google_compute_network.burn_backend_network.id
  depends_on    = [google_compute_network.burn_backend_network]
}

resource "google_compute_network" "burn_backend_network" {
  name                    = "burn-backend-run-network-${terraform.workspace}"
  auto_create_subnetworks = false
}

# Create a Cloud Router
resource "google_compute_router" "burn_backend_router" {
  name    = "burn-backend-router-${terraform.workspace}"
  network = google_compute_network.burn_backend_network.name
  region  = "us-central1"
}

# Reserve a static IP address
resource "google_compute_address" "burn_backend_static_ip" {
  name   = "burn-backend-static-ip-${terraform.workspace}"
  region = "us-central1"
}

# Set up Cloud NAT
resource "google_compute_router_nat" "burn_backend_nat" {
  name   = "burn-backend-nat-${terraform.workspace}"
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

# Create a Cloud Run service for burn-backend services
resource "google_cloud_run_v2_service" "tf-rest-burn-severity" {
  name     = "tf-rest-burn-severity-${terraform.workspace}"
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
        name  = "S3_FROM_GCP_ROLE_ARN"
        value = var.s3_from_gcp_role_arn
      }
      env {
        name  = "S3_BUCKET_NAME"
        value = var.s3_bucket_name
      }
      ## TODO [#24]: self-referential endpoint, will be solved by refactoring out titiler and/or making fully static
      env {
        name  = "GCP_CLOUD_RUN_ENDPOINT"
        value = "${terraform.workspace}" == "prod" ? "https://tf-rest-burn-severity-prod-ohi6r6qs2a-uc.a.run.app" : "https://tf-rest-burn-severity-dev-ohi6r6qs2a-uc.a.run.app"
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

# Create a Cloud Tasks queue for the Cloud Run service
resource "google_cloud_tasks_queue" "tf-rest-burn-severity-queue" {
  name = "tf-rest-burn-severity-queue-${terraform.workspace}"
  location = "us-central1"

  rate_limits {
    max_concurrent_dispatches = 2
  }

  retry_config {
    max_attempts = "2"
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
  workload_identity_pool_id = "github-actions-${terraform.workspace}"
  display_name = "Github Actions Pool"
  description  = "Workload identity pool for GitHub actions"
}

resource "google_iam_workload_identity_pool_provider" "oidc" {
  depends_on = [google_iam_workload_identity_pool.pool]
  workload_identity_pool_provider_id = "oidc-provider-${terraform.workspace}"
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

## TODO [#20]: Harcoded project string and others - now that tofu outputs are setup up, make more general
## Will be helpful as we move to other projects and environments

# Create the IAM service account for GitHub Actions
resource "google_service_account" "github_actions" {
  account_id  = "github-actions-sa-${terraform.workspace}"
  display_name = "Github Actions Service Account"
  description = "This service account is used by GitHub Actions"
  project     = "dse-nps"
}

# Create the IAM service account for the Cloud Run service
resource "google_service_account" "burn-backend-service" {
  account_id   = "burn-backend-service-${terraform.workspace}"
  display_name = "Cloud Run Service Account for burn backend - ${terraform.workspace}"
  description  = "This service account is used by the Cloud Run service to access GCP Secrets Manager and authenticate with OIDC for AWS S3 access"
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

resource "google_project_iam_member" "oidc_token_creator" {
  project = "dse-nps"
  role    = "roles/iam.serviceAccountTokenCreator"
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
  repository_id = "burn-backend-${terraform.workspace}"
  format        = "DOCKER"
  location      = "us-central1"
}