terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 4.0"
    }
    google = {
      source  = "hashicorp/google"
      version = "5.9.0"
    }
  }
}

# Configure providers using berkeley profiles
provider "aws" {
  profile = "UCB-FederatedAdmins-557418946771"
  region = "us-east-2"
}

provider "google" {
  project     = "dse-nps"
  region      = "us-central1"
}

# Get google project info
data "google_project" "project" {}

### AWS Transfer - SFTP Server

# First the server itself
resource "aws_transfer_server" "tf-sftp-burn-severity" {
  identity_provider_type = "SERVICE_MANAGED"
  protocols = ["SFTP"]
  domain = "S3"
}

# # Then, keys for the public and admin users
# resource "aws_transfer_ssh_key" "sftp_ssh_key_public" {
#   server_id = aws_transfer_server.sftp_server.id
#   user_name = "public"
#   body      = file("<PUBLIC_KEY_FILE_PATH>")
# }

# resource "aws_transfer_ssh_key" "sftp_ssh_key_private" {
#   server_id = aws_transfer_server.sftp_server.id
#   user_name = "admin"
#   body      = file("<PUBLIC_KEY_FILE_PATH>")
# }


# Create a Cloud Run service
resource "google_cloud_run_service" "tf-rest-burn-severity" {
  name     = "tf-rest-burn-severity"
  location = "us-central1"

  template {
    spec {
      containers {
        image = "us-docker.pkg.dev/cloudrun/container/placeholder"
      }
    }
  }

  traffic {
    percent         = 100
    latest_revision = true
  }
}

# Create the IAM workload identity pool and provider to auth GitHub Actions
resource "google_iam_workload_identity_pool" "pool" {
  workload_identity_pool_id = "github"
  display_name = "Github Actions Pool"
  description  = "Workload identity pool for GitHub actions"
}

resource "google_iam_workload_identity_pool_provider" "oidc" {
  workload_identity_pool_provider_id = "oidc-provider"
  workload_identity_pool_id          = google_iam_workload_identity_pool.pool.workload_identity_pool_id

  display_name = "GitHub OIDC Provider"

  oidc {
    issuer_uri        = "https://token.actions.githubusercontent.com"
    allowed_audiences = [google_service_account.default.email]
  }

  attribute_mapping = {
    "google.subject" = "assertion.sub"
    "attribute.actor" = "assertion.actor"
    "attribute.repository" = "assertion.repository"
  }
}

# Create the IAM service account for GitHub Actions
resource "google_service_account" "default" {
  account_id  = "github-actions-service-account"
  display_name = "Github Actions Service Account"
  description = "This service account is used by GitHub Actions"
  project     = "dse-nps"
}


# Give the service account permissions to deploy to Cloud Run, and to Cloud Build, and to the Workload Identity Pool
resource "google_project_iam_member" "run_admin" {
  project  = "dse-nps"
  role     = "roles/run.admin" 
  member   = "serviceAccount:${google_service_account.default.email}"
}

resource "google_project_iam_member" "cloudbuild_builder" {
  project  = "dse-nps"
  role     = "roles/cloudbuild.builds.builder"
  member   = "serviceAccount:${google_service_account.default.email}"
}

resource "google_service_account_iam_binding" "workload_identity_user" {
  service_account_id = google_service_account.default.name
  role               = "roles/iam.workloadIdentityUser"
  members            = [
    "principal://iam.googleapis.com/projects/${google_project.project.number}/locations/global/workloadIdentityPools/${google_iam_workload_identity_pool.pool.workload_identity_pool_id}/subject/${SUBJECT}"
  ]
}

## We will use GitHub Actions to build and deploy the container image, so we actually don't need this
# resource "google_cloudbuild_trigger" "default" {
#   name = "burn-prod-trigger"
#   github {
#     owner = "SchmidtDSE"
#     name  = "burn-severity-mapping-poc"
#     push {
#       branch = "prod"
#     }
#   }
#   filename = "cloudbuild.yaml"
# }