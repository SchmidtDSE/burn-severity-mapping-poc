terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 4.0"
    }
    gcp = {
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
  project     = "<PROJECT_ID>"
  region      = "<GCP_REGION>"
}

### AWS Transfer - SFTP Server

# First the server itself
resource "aws_transfer_server" "tf-sftp-burn-severity" {
  identity_provider_type = "SERVICE_MANAGED"
  protocols = ["SFTP"]
  domain = "S3"
  structured_log_destinations = [
    "${aws_cloudwatch_log_group.transfer.arn}:*"
  ]
}

# Then, keys for the public and admin users
resource "aws_transfer_ssh_key" "sftp_ssh_key" {
  server_id = aws_transfer_server.sftp_server.id
  user_name = "public"
  body      = file("<PUBLIC_KEY_FILE_PATH>")
}

resource "aws_transfer_ssh_key" "sftp_ssh_key" {
  server_id = aws_transfer_server.sftp_server.id
  user_name = "admin"
  body      = file("<PUBLIC_KEY_FILE_PATH>")
}



# Create a Cloud Run service
resource "google_cloud_run_service" "default" {
  name     = "<CLOUD_RUN_SERVICE_NAME>"
  location = "<GCP_REGION>"

  template {
    spec {
      containers {
        image = "<DOCKER_IMAGE>"
      }
    }
  }

  traffic {
    percent         = 100
    latest_revision = true
  }
}