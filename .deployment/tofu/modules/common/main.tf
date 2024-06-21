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