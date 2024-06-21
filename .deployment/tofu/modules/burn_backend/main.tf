# Create a Cloud Run service for burn-backend services
resource "google_cloud_run_v2_service" "tf-rest-burn-severity" {
  name     = "tf-rest-burn-backend-${terraform.workspace}"
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
        name  = "GCP_CLOUD_RUN_ENDPOINT_TITILER"
        # value = "${terraform.workspace}" == "prod" ? "https://tf-rest-burn-severity-ohi6r6qs2a-uc.a.run.app" : "https://tf-rest-burn-severity-dev-ohi6r6qs2a-uc.a.run.app"
        value = var.gcp_cloud_run_endpoint_titiler
      }
      resources {
        limits = {
          cpu    = "4"
          memory = "2Gi"
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
  repository_id = "burn-backend-${terraform.workspace}"
  format        = "DOCKER"
  location      = "us-central1"
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


## TODO [#20]: Harcoded project string and others - now that tofu outputs are setup up, make more general
## Will be helpful as we move to other projects and environments

# Create the IAM service account for GitHub Actions
resource "google_service_account" "github_actions" {
  account_id  = "github-actions-sa-${terraform.workspace}"
  display_name = "Github Actions Service Account"
  description = "This service account is used by GitHub Actions"
  project     = "dse-nps"
}

resource "google_service_account_iam_binding" "workload_identity_user" {
  depends_on = [google_iam_workload_identity_pool_provider.oidc]
  service_account_id = google_service_account.github_actions.name
  role               = "roles/iam.workloadIdentityUser"
  members            = [
    # "principalSet://iam.googleapis.com/projects/${var.google_project_number}/locations/global/workloadIdentityPools/${google_iam_workload_identity_pool.pool.workload_identity_pool_id}/attribute.repository/SchmidtDSE/burn-severity-mapping-poc"
    "principalSet://iam.googleapis.com/projects/${var.google_project_number}/locations/global/workloadIdentityPools/${var.google_workload_identity_pool_id}/attribute.repository/SchmidtDSE/burn-severity-mapping-poc"
  ]
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

