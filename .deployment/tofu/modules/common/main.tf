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

# Create the IAM workload identity pool and provider to auth GitHub Actions
resource "google_iam_workload_identity_pool" "pool" {
  workload_identity_pool_id = "github-actions-${terraform.workspace}"
  display_name = "Github Actions Pool"
  description  = "Workload identity pool for GitHub actions"
}

# Create the OIDC provider for GitHub Actions
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
    "principalSet://iam.googleapis.com/projects/${var.google_project_number}/locations/global/workloadIdentityPools/${google_iam_workload_identity_pool.pool.workload_identity_pool_id}/attribute.repository/SchmidtDSE/burn-severity-mapping-poc"
  ]
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

