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

terraform {
  backend "gcs" {
    bucket  = "dse-tofu-state"
    prefix  = "terraform/burn-severity-mapping-poc"
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

# Get the one secret we need - ssh key
data "google_secret_manager_secret_version" "burn_sftp_ssh_keys" {
  secret = "burn_sftp_ssh_keys"
}

locals {
  ssh_pairs = jsondecode(
    data.google_secret_manager_secret_version.burn_sftp_ssh_keys.secret_data
  )
}

### AWS ###

# Create the CloudWatch logs policy
data "aws_iam_policy_document" "cloudwatch_logs_policy" {
  statement {
    actions = [
      "logs:CreateLogGroup",
      "logs:CreateLogStream",
      "logs:PutLogEvents",
      "logs:DescribeLogStreams",
    ]

    resources = ["arn:aws:logs:*:*:*"]
  }
}

data "aws_iam_policy_document" "cloudwatch_logs_role" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["transfer.amazonaws.com"]
    }
  }
}

resource "aws_iam_policy" "cloudwatch_logs_policy" {
  name        = "cloudwatch_logs_policy"
  description = "CloudWatch Logs policy for AWS Transfer logging"
  policy      = data.aws_iam_policy_document.cloudwatch_logs_policy.json
}

# Create the IAM role for CloudWatch logging
resource "aws_iam_role" "cloudwatch_logs_role" {
  name = "cloudwatch_logs_role"
  assume_role_policy = data.aws_iam_policy_document.cloudwatch_logs_role.json
}

# Attach the CloudWatch logs policy to the new role
resource "aws_iam_role_policy_attachment" "cloudwatch_logs_policy_attachment" {
  role       = aws_iam_role.cloudwatch_logs_role.name
  policy_arn = aws_iam_policy.cloudwatch_logs_policy.arn
}

resource "aws_cloudwatch_log_group" "transfer_log_group" {
  name = "/aws/transfer/${aws_transfer_server.tf-sftp-burn-severity.id}"
  retention_in_days = 14
}


# First the server itself
resource "aws_transfer_server" "tf-sftp-burn-severity" {
  identity_provider_type = "SERVICE_MANAGED"
  protocols = ["SFTP"]
  domain = "S3"
  logging_role = aws_iam_role.cloudwatch_logs_role.arn
}

# Then, the user for the server, allowing it access to Transfer Family

data "aws_iam_policy_document" "assume_role" {
  statement {
    effect = "Allow"

    principals {
      type        = "Service"
      identifiers = ["transfer.amazonaws.com"]
    }

    actions = ["sts:AssumeRole"]
  }
}

resource "aws_iam_role" "admin" {
  name               = "tf-sftp-admin-iam-role"
  assume_role_policy = data.aws_iam_policy_document.assume_role.json
}

# Then, allow it to actually access the S3 assets themselves
# Define the policy

data "aws_iam_policy_document" "s3_policy" {
  statement {
    sid    = "ReadWriteS3"
    effect = "Allow"
    actions = [
      "s3:ListBucket",
    ]
    resources = [
      "arn:aws:s3:::burn-severity",
    ]
  }

  statement {
    effect = "Allow"
    actions = [
      "s3:PutObject",
      "s3:GetObject",
      "s3:GetObjectTagging",
      "s3:DeleteObject",
      "s3:DeleteObjectVersion",
      "s3:GetObjectVersion",
      "s3:GetObjectVersionTagging",
      "s3:GetObjectACL",
      "s3:PutObjectACL",
    ]
    resources = [
      "arn:aws:s3:::burn-severity/*",
    ]
  }
}

# Create the s3_policy
resource "aws_iam_policy" "s3_admin_policy" {
  name        = "s3_admin_policy"
  description = "S3 policy for admin user"
  policy      = data.aws_iam_policy_document.s3_policy.json
}

# Attach the policy to the role
resource "aws_iam_role_policy_attachment" "s3_policy_attachment" {
  role       = aws_iam_role.admin.name
  policy_arn = aws_iam_policy.s3_admin_policy.arn
}

# Add the necessary session policy to the user
data "aws_iam_policy_document" "session_policy" {
  statement {
    sid    = "AllowListingOfUserFolder"
    effect = "Allow"
    actions = [
      "s3:ListBucket",
    ]
    resources = [
      "arn:aws:s3:::burn-severity",
    ]
    condition {
      test     = "StringLike"
      variable = "s3:prefix"
      values = [
        "/public/*",
        "/public",
        "/"
      ]
    }
  }

  statement {
    sid    = "HomeDirObjectAccess"
    effect = "Allow"
    actions = [
      "s3:PutObject",
      "s3:GetObject",
      "s3:DeleteObject",
      "s3:GetObjectVersion",
    ]
    resources = [
      "arn:aws:s3:::burn-severity/*",
    ]
  }
}

# Finally, create the user within Transfer Family
resource "aws_transfer_user" "tf-sftp-burn-severity" {
  server_id = aws_transfer_server.tf-sftp-burn-severity.id
  user_name = "admin"
  role      = aws_iam_role.admin.arn
  home_directory_mappings {
    entry = "/"
    target = "/burn-severity/public"
  }
  home_directory_type = "LOGICAL"
  policy = data.aws_iam_policy_document.session_policy.json
}

resource "aws_transfer_ssh_key" "sftp_ssh_key_public" {
  depends_on = [aws_transfer_user.tf-sftp-burn-severity]
  server_id = aws_transfer_server.tf-sftp-burn-severity.id
  user_name = "admin"
  body      = local.ssh_pairs["SSH_KEY_ADMIN_PUBLIC"]
}

# Set up STS to allow the GCP server to assume a role for AWS secrets
data "aws_iam_policy_document" "assume_role_policy" {
  statement {
    actions = ["sts:AssumeRoleWithWebIdentity"]
    effect  = "Allow"

    principals {
      type        = "Federated"
      identifiers = ["arn:aws:iam::557418946771:oidc-provider/https://${data.google_project.project.number}"]
    }

    condition {
      test     = "StringEquals"
      variable = "https://${data.google_project.project.number}.svc.id.goog:sub"

      values = [
        "system:serviceaccount:${data.google_project.project.number}.svc.id.goog[default/${google_service_account.access_aws_secrets.account_id}]"
      ]
    }
  }
}

resource "aws_iam_role" "role" {
  name               = "aws_secrets_access_role"
  assume_role_policy = data.aws_iam_policy_document.assume_role_policy.json
}


### GCP ###

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
          value = local.ssh_pairs["SSH_KEY_ADMIN_PRIVATE"]
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
  }

  attribute_mapping = {
    "google.subject" = "assertion.sub"
    "attribute.actor" = "assertion.actor"
    "attribute.repository" = "assertion.repository"
  }
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

resource "google_service_account_iam_binding" "workload_identity_user" {
  service_account_id = google_service_account.github_actions.name
  role               = "roles/iam.workloadIdentityUser"
  members            = [
    "principalSet://iam.googleapis.com/projects/${data.google_project.project.number}/locations/global/workloadIdentityPools/${google_iam_workload_identity_pool.pool.workload_identity_pool_id}/attribute.repository/SchmidtDSE/burn-severity-mapping-poc"
  ]
}

# Create an Artifact Registry repo for the container image
resource "google_artifact_registry_repository" "burn-backend" {
  repository_id = "burn-backend"
  format        = "DOCKER"
  location      = "us-central1"
}