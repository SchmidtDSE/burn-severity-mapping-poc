
# Create a Cloud Run service
resource "google_cloud_run_service" "tf-rest-burn-severity" {
  name     = "tf-rest-burn-severity"
  location = "us-central1"

  template {
    spec {
      service_account_name = google_service_account.access_aws_secrets.email
      containers {
        image = "us-docker.pkg.dev/cloudrun/container/placeholder"
        env {
          name  = "ENV"
          value = "CLOUD"
        }
        env {
          name  = "SFTP_SSH_KEY_PRIVATE"
          value = var.ssh_pairs["SSH_KEY_ADMIN_PRIVATE"]
        }
      }
    }
  }

  traffic {
    percent         = 100
    latest_revision = true
  }
}

# Allow unauthenticated invocations
resource "google_cloud_run_service_iam_member" "public" {
  service = google_cloud_run_service.tf-rest-burn-severity.name
  location = google_cloud_run_service.tf-rest-burn-severity.location
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

# Create the IAM service account for the Cloud Run service to access AWS
resource "google_service_account" "access_aws_secrets" {
  account_id   = "cloud-run-aws-access"
  display_name = "Cloud Run AWS Access Service Account"
  description  = "This service account is used by the Cloud Run service to access AWS Secrets"
  project      = "dse-nps"
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