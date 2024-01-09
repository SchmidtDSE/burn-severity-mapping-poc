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

# Get the one secret we need - ssh key
data "google_secret_manager_secret_version" "burn_sftp_ssh_keys" {
  secret = "burn_sftp_ssh_keys"
}

locals {
  ssh_pairs = jsondecode(data.google_secret_manager_secret_version.burn_sftp_ssh_keys.secret_data)
  google_project_number = data.google_project.project.number
}


# Initialize the modules
module "sftp" {
  source = "./modules/sftp"
  ssh_pairs = local.ssh_pairs
  google_project_number = local.google_project_number
}

module "burn_backend" {
  source = "./modules/burn_backend"
  ssh_pairs = local.ssh_pairs
  google_project_number = local.google_project_number
  sftp_server_endpoint = module.sftp.sftp_server_endpoint
  sftp_admin_username = module.sftp.sftp_admin_username
}