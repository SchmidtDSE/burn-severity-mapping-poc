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

data "google_project" "project" {}
data "aws_region" "current" {}
data "aws_caller_identity" "current" {}

locals {
  google_project_number = data.google_project.project.number
  aws_account_id = data.aws_caller_identity.current.account_id
  aws_region = data.aws_region.current.name
  # oidc_provider_domain_url = "https://accounts.google.com"
  oidc_provider_domain_url = "accounts.google.com"
  gcp_cloud_run_client_id = "117526146749746854545" ## This is the ClientID of the cloud run instance, and can't be output from terraform!
}

# Initialize the modules
module "static_io" {
  source = "./modules/static_io"
  google_project_number = local.google_project_number
  gcp_service_account_s3_email = module.burn_backend.gcp_service_account_s3_email
  gcp_cloud_run_client_id = local.gcp_cloud_run_client_id
  aws_account_id = local.aws_account_id
  oidc_provider_domain_url = local.oidc_provider_domain_url
}

module "burn_backend" {
  source = "./modules/burn_backend"
  google_project_number = local.google_project_number
}