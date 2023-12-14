terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 4.0"
    }
    google = {
      source  = "hashicorp/google"
      version = "~> 3.0"
    }
  }
}

# Configure providers using berkeley profiles
provider "aws" {
  profile = "UCB-FederatedAdmins-557418946771"
  region = "us-east-2"
}

provider "google" {
  project     = "natl-park-service"
  region      = "us-central1-a"
}

### AWS Transfer - SFTP Server

# First the server itself
resource "aws_transfer_server" "tf-sftp-burn-severity" {
  name = "tf-sftp-burn-severity"
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
  location = "us-central1-a"

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